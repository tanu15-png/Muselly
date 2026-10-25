"""Authenticated Qloo discovery, personalized ranking, corrections, and bookmarks."""
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import unicodedata
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID, uuid4
from zipfile import ZipFile, ZIP_DEFLATED

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import AuthUser, get_current_user
from .catalog import SOURCES, CatalogError, external_search
from .database import get_db
from .enrichment import latest_run
from .models import SavedProduct, ProductFeedback
from .onboarding import locked_profile
from .shopping import SearchRequest, parse_request, ranked_product, taste_context, mentions, COLORS, FITS, DETAIL_ALIASES, CATEGORIES

router = APIRouter(prefix='/api/extension', tags=['Browser extension'])
ROOT = Path(__file__).resolve().parents[2] / 'extension'
HOSTS = {urlsplit(s['website']).hostname.removeprefix('www.') for s in SOURCES}


def product_url(value):
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or '').removeprefix('www.')
        if parsed.scheme != 'https' or host not in HOSTS or parsed.username or parsed.password or parsed.port not in (None, 443):
            raise ValueError()
    except ValueError:
        raise ValueError('Choose a product URL from a supported store.') from None
    return value


class Candidate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=500)
    url: str = Field(max_length=2048)
    image: str = Field(default='', max_length=2048)
    brand: str = Field(default='', max_length=200)
    description: str = Field(default='', max_length=5000)
    price: Decimal | None = Field(default=None, ge=0, le=100000000)
    currency: str = Field(default='INR', pattern='^(INR|USD|EUR|GBP|CAD|AUD)$')
    sold_out: bool = False

    _url = field_validator('url')(product_url)

    @field_validator('image')
    @classmethod
    def safe_image(cls, value):
        if not value: return value
        try:
            url = urlsplit(value)
            if url.scheme != 'https' or not url.hostname or url.username or url.password: raise ValueError()
        except ValueError:
            raise ValueError('Use an HTTPS product image.') from None
        return value


class RankRequest(SearchRequest):
    items: list[Candidate] = Field(max_length=100)


def brand_key(value):
    return ''.join(char for char in unicodedata.normalize('NFKC', value).casefold() if char.isalnum())


def current_brands(db, user, taste):
    run = latest_run(db, user, succeeded=True)
    if not run:
        return []
    result = run.result or {}
    inputs = list(dict.fromkeys(r['input'] for r in result.get('resolutions', []) if r.get('status') == 'resolved'))
    return [{**a, 'based_on': inputs[:4]} for a in result.get('affinities', []) if a['entity_id'] in taste['qloo']]


def attributes(item, vocabulary):
    text = item.get('title', '') + ' ' + item.get('description', '')
    return {key for key, aliases in vocabulary.items() if any(mentions(text, term) for term in aliases)}


SHAPES = {**DETAIL_ALIASES, **{fit: [fit] for fit in FITS}}
FEEDBACK_COLORS = {name: aliases for name, aliases in COLORS.items() if name not in ('pastels', 'neutrals')}


def correction_score(item, rows):
    score, reasons = 0, []
    for row in rows:
        previous = row.product
        if row.kind == 'more_like_this':
            overlap = (attributes(item, FEEDBACK_COLORS) & attributes(previous, FEEDBACK_COLORS)) | (attributes(item, SHAPES) & attributes(previous, SHAPES))
            same_brand = bool(item.get('brand') and brand_key(item['brand']) == brand_key(previous.get('brand', '')))
            if overlap or same_brand:
                score += min(4, len(overlap) + int(same_brand))
                reasons.append('Shares listed details or brand with a product you liked.')
        elif row.kind in ('wrong_color', 'wrong_shape'):
            vocabulary = FEEDBACK_COLORS if row.kind == 'wrong_color' else SHAPES
            if attributes(item, vocabulary) & attributes(previous, vocabulary):
                score -= 4
                reasons.append('Lower priority because it shares a listed ' + ('color' if row.kind == 'wrong_color' else 'shape') + ' you rejected.')
        elif (row.kind == 'too_expensive' and item.get('currency') == previous.get('currency')
              and attributes(item, CATEGORIES) & attributes(previous, CATEGORIES)):
            if previous.get('price') is not None and Decimal(str(item['price'])) >= Decimal(str(previous['price'])):
                score -= 4
                reasons.append('Lower priority after your price feedback; your budget remains unchanged.')
    return max(-12, min(8, score)), list(dict.fromkeys(reasons))


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    item: Candidate
    kind: Literal['more_like_this', 'not_my_style', 'too_expensive', 'wrong_shape', 'wrong_color']


@router.post('/feedback')
def feedback(body: FeedbackRequest, user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)):
    locked_profile(db, user)
    row = db.scalar(select(ProductFeedback).where(ProductFeedback.user_id == user.id, ProductFeedback.url == body.item.url))
    if not row:
        row = ProductFeedback(id=uuid4(), user_id=user.id, url=body.item.url)
        db.add(row)
    row.kind, row.product = body.kind, body.item.model_dump(mode='json')
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {'saved': True, 'note': 'Preference saved. Refining your loaded products.'}


@router.delete('/feedback')
def clear_feedback(user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)):
    for row in db.scalars(select(ProductFeedback).where(ProductFeedback.user_id == user.id)):
        db.delete(row)
    db.commit()
    return {'cleared': True}


@router.get('/profile')
def profile(request: Request, user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)):
    taste = taste_context(db, user, request.app.state.settings)
    return {'user': {'id': str(user.id), 'name': user.display_name},
            'has_profile': taste['has_profile'], 'preferences': taste['answers'],
            'qloo_affinities': len(taste['qloo']), 'brands': current_brands(db, user, taste)}


@router.post('/rank')
def rank(body: RankRequest, request: Request, user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)):
    request.app.state.search_limiter.check(user)
    filters = parse_request(body)
    taste = taste_context(db, user, request.app.state.settings)
    affinities = current_brands(db, user, taste)
    brands = {brand_key(a['name']): a for a in affinities}
    brand_ids = {a['entity_id']: a for a in affinities}
    corrections = db.scalars(select(ProductFeedback).where(ProductFeedback.user_id == user.id)
                            .order_by(ProductFeedback.updated_at.desc()).limit(50)).all()
    rejected = set(db.scalars(select(ProductFeedback.url).where(ProductFeedback.user_id == user.id, ProductFeedback.kind != 'more_like_this')))
    exchange = None
    if any(item.price is not None and item.currency != filters['currency'] for item in body.items):
        try: exchange = request.app.state.catalog.rates()
        except CatalogError as failure: raise HTTPException(503, failure.message) from None
    results, unknown, seen, excluded = [], 0, set(), {}
    for item in body.items:
        if item.url in rejected:
            excluded['feedback'] = excluded.get('feedback', 0) + 1
            continue
        if item.url in seen or item.sold_out: continue
        seen.add(item.url)
        if item.price is None:
            unknown += 1
            continue  # Never invent a price or claim an unknown item fits a budget.
        host = urlsplit(item.url).hostname
        source = next(s for s in SOURCES if urlsplit(s['website']).hostname.removeprefix('www.') == host.removeprefix('www.'))
        product = {'id': sha256(item.url.encode()).hexdigest()[:24], 'title': item.title, 'brand': item.brand,
                   'product_type': '', 'description': item.description, 'url': item.url, 'image': item.image, 'page_metadata': True,
                   'source_id': source['id'], 'source_name': source['name'], 'qloo_entity_id': None,
                   'fetched_at': datetime.now(timezone.utc).isoformat(), 'variants_truncated': False,
                   'variants': [{'id': '0', 'price': item.price, 'currency': item.currency, 'options': {}}]}
        result, reason = ranked_product(product, filters, taste, exchange)
        if not result:
            excluded[reason] = excluded.get(reason, 0) + 1
            continue
        affinity = brands.get(brand_key(item.brand)) or brand_ids.get(source.get('qloo_entity_id'))
        if affinity:
            # Qloo selects discovery brands; local garment evidence still matters.
            result['_score'] += max(2, 6 - min(int(affinity.get('rank', 20)), 20) // 5)
            result['why'].insert(0, affinity['name'] + ' is a Qloo brand discovery based on your saved interests.')
            result['qloo_brand'] = affinity['name']
        adjustment, explanations = correction_score(item.model_dump(), corrections)
        result['_score'] += adjustment
        result['why'] = explanations[:1] + result['why']
        result['feedback_item'] = item.model_dump(mode='json')
        result.update(url=item.url, availability='Check sizes and stock on the store', variant_verified=False)
        result.pop('available', None)
        results.append(result)
    results.sort(key=(lambda r: r['_price']) if body.sort.startswith('price_') else (lambda r: -r['_score']), reverse=body.sort == 'price_desc')
    for result in results:
        result.pop('_score'); result.pop('_price')
    return {'products': results, 'scanned': len(body.items), 'unknown_prices': unknown, 'excluded': excluded,
            'applied_filters': {k: str(v) if isinstance(v, Decimal) else v for k, v in filters.items()},
            'exchange': {'source': exchange['source'], 'date': exchange['date']} if exchange else None,
            'scope': 'Products loaded on the current page; stock and sizes require store confirmation.',
            'qloo_matched': sum(bool(p.get('qloo_brand')) for p in results),
            'ranked_at': datetime.now(timezone.utc).isoformat()}


class DiscoveryRequest(SearchRequest):
    explore: bool = False


@router.post('/search')
def search_links(body: DiscoveryRequest, request: Request, user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)):
    filters = parse_request(body)
    terms = ' '.join(t for t in (filters['color'], filters['fit'], filters['catalog_query']) if t)
    taste = taste_context(db, user, request.app.state.settings)
    affinities = current_brands(db, user, taste)
    preferred = {brand_key(name) for name in taste['answers'].get('q16', [])}
    retailers = sorted([s for s in SOURCES if s['kind'] == 'retailer'], key=lambda s: brand_key(s['name']) not in preferred)
    selected = affinities[3:6] if body.explore else affinities[:3]
    discoveries = [{'name': a['name'], 'entity_id': a['entity_id'], 'source': 'Qloo', 'based_on': a.get('based_on', []),
                    'links': [{'name': s['name'], 'url': external_search(s, a['name'] + ' ' + terms)}
                              for s in retailers],
                    'note': 'Search this brand at a retailer. Stock, delivery and price are not verified.'} for a in selected]
    return {'discoveries': discoveries, 'explore': body.explore,
            'links': [{'id': s['id'], 'name': s['name'], 'url': external_search(s, terms)} for s in retailers],
            'query': terms, 'budget': str(filters['max_price']) if filters['max_price'] else None,
            'note': 'Open a store, then rank its loaded products in the extension. Budget is enforced during ranking.'}


class SaveRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=500)
    url: str = Field(max_length=2048)
    image: str = Field(default='', max_length=2048)
    _url = field_validator('url')(product_url)
    _image = field_validator('image')(Candidate.safe_image.__func__)


@router.get('/saved')
def saved(user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(SavedProduct).where(SavedProduct.user_id == user.id).order_by(SavedProduct.created_at.desc()).limit(200)).all()
    return {'items': [{'id': str(r.id), 'title': r.title, 'url': r.url, 'image': r.image, 'created_at': r.created_at} for r in rows]}


@router.post('/saved')
def save(body: SaveRequest, user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)):
    locked_profile(db, user)
    row = db.scalar(select(SavedProduct).where(SavedProduct.user_id == user.id, SavedProduct.url == body.url))
    if not row:
        row = SavedProduct(id=uuid4(), user_id=user.id, title=body.title, url=body.url, image=body.image)
        db.add(row)
    db.commit()
    return {'id': str(row.id), 'saved': True}


@router.delete('/saved/{item_id}')
def remove_saved(item_id: UUID, user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.scalar(select(SavedProduct).where(SavedProduct.id == item_id, SavedProduct.user_id == user.id))
    if not row: raise HTTPException(404, 'Saved product not found.')
    db.delete(row); db.commit()
    return {'deleted': str(item_id)}


@router.get('/download')
def download(request: Request):
    origin = request.app.state.settings.app_origin.rstrip('/')
    url = urlsplit(origin)
    if url.scheme not in ('https', 'http') or not url.hostname or url.username or url.password:
        raise HTTPException(503, 'Configure APP_ORIGIN before downloading the extension.')
    manifest = json.loads((ROOT / 'manifest.json').read_text())
    manifest['externally_connectable'] = {'matches': [origin + '/*']}
    manifest['host_permissions'] = [f'{url.scheme}://{url.hostname}/*']
    output = BytesIO()
    with ZipFile(output, 'w', ZIP_DEFLATED) as package:
        for file in sorted(ROOT.rglob('*')):
            if file.is_file() and file.suffix in ('.js', '.json', '.html', '.css', '.md', '.png', '.svg') and 'tests' not in file.parts:
                name = file.relative_to(ROOT).as_posix()
                if name == 'manifest.json': package.writestr(name, json.dumps(manifest, indent=2))
                elif name == 'config.js': package.writestr(name, 'export const WEB_ORIGIN = ' + json.dumps(origin) + ';\n')
                else: package.write(file, name)
    return Response(output.getvalue(), media_type='application/zip', headers={'Content-Disposition': 'attachment; filename="muselly-extension.zip"'})
