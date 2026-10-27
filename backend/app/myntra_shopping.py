"""Local retailer snapshot search with confirmed cultural fashion preferences."""
from collections import Counter
from datetime import datetime, timezone
from functools import lru_cache
import json
import math
from pathlib import Path
import re
from time import monotonic
from typing import Literal
from types import SimpleNamespace
from urllib.parse import urlparse
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .analysis import labeled_answers
from .auth import AuthUser, get_current_user
from .cultural_analytics import timestamp
from .database import get_db
from .models import CulturalFeedback, CulturalDiscoveryRun, TasteAnalysisRun, TasteTest, ProductFeedback
from .onboarding import images_for, locked_profile
from .shopping import SearchRequest, parse_request, mentions, COLORS
from .retailers import valid_source

router = APIRouter(prefix='/api/shop', tags=['Catalog shopping'])
CATEGORIES = {'Dresses': ['dress', 'dresses', 'gown', 'gowns'], 'Tops': ['top', 'tops', 'blouse', 'blouses'],
              'Shirts': ['shirt', 'shirts'], 'Tshirts': ['t-shirt', 'tshirt', 'tee', 't-shirts', 'tshirts', 'tees'],
              'Jeans': ['jeans'], 'Trousers': ['trousers', 'trouser', 'pants', 'pant'],
              'Skirts': ['skirt', 'skirts'], 'Shorts': ['shorts'], 'Kurtas': ['kurta', 'kurtas', 'kurti', 'kurtis'],
              'Kurta Sets': ['kurta set', 'kurta sets'], 'Co-Ords': ['co-ord', 'co-ords', 'coord', 'co ord'],
              'Sweaters': ['sweater', 'sweaters', 'cardigan', 'cardigans', 'knitwear'],
              'Sweatshirts': ['sweatshirt', 'sweatshirts', 'hoodie', 'hoodies'], 'Jackets': ['jacket', 'jackets', 'coat', 'coats'],
              'Blazers': ['blazer', 'blazers']}
DETAILS = {'floral': ['floral', 'flower'], 'striped': ['striped', 'stripes'], 'checked': ['checked', 'plaid'],
           'solid': ['solid', 'plain'], 'embroidered': ['embroidered', 'embroidery'], 'ribbed': ['ribbed'],
           'lace': ['lace'], 'satin': ['satin'], 'cotton': ['cotton'], 'linen': ['linen'], 'denim': ['denim'],
           'a-line': ['a-line', 'a line'], 'bodycon': ['bodycon'], 'wide leg': ['wide leg', 'wide-leg'],
           'straight': ['straight'], 'oversized': ['oversized'], 'relaxed': ['relaxed'], 'fitted': ['fitted', 'slim fit'],
           'flared': ['flared', 'fit and flare'], 'wrap': ['wrap'], 'pleated': ['pleated'],
           'mini': ['mini'], 'midi': ['midi'], 'maxi': ['maxi'], 'sequinned': ['sequin', 'sequinned', 'sequins'],
           'tailored': ['tailored'], 'structured': ['structured']}
OCCASIONS = {'work': ['formal', 'tailored', 'straight', 'cotton', 'linen'],
             'party': ['satin', 'sequinned', 'lace', 'ruched', 'embroidered'],
             'wedding': ['embroidered', 'sequinned', 'flared', 'anarkali'],
             'casual': ['cotton', 'relaxed', 'denim', 'casual'],
             'vacation': ['cotton', 'linen', 'relaxed', 'floral', 'casual']}


def key(value):
    return re.sub(r'[^\w]+', '', str(value).casefold())


def words(value):
    return ' '.join(re.sub(r'[-_/]', ' ', str(value)).casefold().split())


def has(text, value):
    return mentions(words(text), words(value))


@lru_cache(maxsize=3)
def read_catalog(path, mtime, size):
    try:
        if size > 25_000_000: raise ValueError()
        rows = json.loads(Path(path).read_text(encoding='utf-8'))
        if not isinstance(rows, list) or not 1 <= len(rows) <= 10000: raise ValueError()
        result, ids = [], set()
        for row in rows:
            product_id, price = row['product_id'], row['price']
            if (not valid_source(row) or product_id in ids or
                row['gender'] != 'Women' or row['category'] not in CATEGORIES or
                row.get('currency') != 'INR' or
                not isinstance(price, (int, float)) or isinstance(price, bool) or not math.isfinite(price) or price <= 0 or
                not row.get('name') or not row.get('brand')):
                raise ValueError()
            ids.add(product_id); result.append(row)
        return tuple(result)
    except (ValueError, TypeError, KeyError, OSError):
        raise HTTPException(503, 'The clothing catalog could not be loaded. Please try again later.') from None


def catalog(request):
    path = Path(request.app.state.settings.myntra_catalog_path)
    try: stat = path.stat()
    except OSError: raise HTTPException(503, 'The clothing catalog is not available yet.') from None
    return read_catalog(str(path), stat.st_mtime_ns, stat.st_size)


@router.get('/images/{product_id}')
def catalog_image(product_id: str, request: Request):
    # Only a known public H&M catalog image is eligible. Never accept a URL or
    # forward customer credentials; this endpoint exposes no taste/profile data.
    row = next((row for row in catalog(request) if row['product_id'] == product_id and row.get('retailer') == 'H&M'), None)
    if not row: raise HTTPException(404,'Catalog image not found.')
    data, media_type = request.app.state.retailer_images.get(row['image_url'])
    return Response(content=data,media_type=media_type)


class OutfitRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    query: str = Field(min_length=2, max_length=280)
    offset: int = Field(default=0, ge=0, le=10000)
    limit: int = Field(default=24, ge=1, le=48)
    liked_only: bool = False


def intent(query):
    text = ' '.join(query.split())
    budget_text = re.sub(r'\bbudget\s+(?:is|of)\s+', 'budget ', text, flags=re.I)
    budget_text = re.sub(r'\bupto\b', 'up to', budget_text, flags=re.I)
    budget_text = re.sub(r'\bwithin\s+', 'under ', budget_text, flags=re.I)
    parsed = parse_request(SearchRequest(query=budget_text + ' clothing'))
    if parsed['currency'] != 'INR': raise HTTPException(422, 'This catalog uses INR. Please give your budget in rupees.')
    categories = {name for name, aliases in CATEGORIES.items() if any(has(text, alias) for alias in aliases)}
    if 'Kurta Sets' in categories: categories.discard('Kurtas')
    if 'Tshirts' in categories:
        without_tees = re.sub(r'\bt[ -]?shirts?\b|\btees?\b', ' ', text, flags=re.I)
        if not any(has(without_tees, alias) for alias in CATEGORIES['Shirts']): categories.discard('Shirts')
    positives, negatives, colors = [], [], []
    for label, aliases in DETAILS.items():
        if any(has(text, alias) for alias in aliases): positives.append(label)
        if any(re.search(r'\b(?:no|not|without|avoid)\s+' + re.escape(words(alias)) + r'\b', words(text)) for alias in aliases): negatives.append(label)
    # A specific color such as navy stays specific; blue can still mean its color family.
    for label, aliases in COLORS.items():
        # Palette aliases overlap specific colors; "cream" must not broaden to
        # every neutral, nor "pink" to every pastel.
        if label in ('pastels', 'neutrals'):
            aliases = ['pastel', 'pastels'] if label == 'pastels' else ['neutral', 'neutrals']
        for alias in aliases:
            if has(text, alias): colors.append(alias if label not in ('pastels', 'neutrals') else label)
            if re.search(r'\b(?:no|not|without|avoid)\s+' + re.escape(words(alias)) + r'\b', words(text)): negatives.append(alias)
    unsupported = bool(re.search(r"\b(?:men|mens|men's|boys?|girls?|kids?|children|husband)\b", text.casefold()))
    unsupported |= any(has(text, term) for term in ['shoes', 'sneakers', 'handbag', 'handbags', 'bags', 'jumpsuit', 'jumpsuits', 'saree', 'sarees', 'footwear', 'sandals', 'jewellery', 'jewelry'])
    occasion = parsed['occasion']
    if any(has(text, term) for term in ['vacation', 'holiday', 'travel', 'trip']): occasion = 'vacation'
    if any(has(text, term) for term in ['formal', 'interview', 'presentation', 'meeting']): occasion = 'work'
    if not categories and occasion in ('work', 'party', 'wedding'):
        categories = {'Dresses', 'Tops', 'Shirts', 'Trousers', 'Skirts', 'Blazers', 'Co-Ords', 'Kurtas', 'Kurta Sets'} if occasion == 'work' else {'Dresses', 'Tops', 'Skirts', 'Co-Ords', 'Kurtas', 'Kurta Sets'}
    return {'categories': sorted(categories), 'min_price': float(parsed['min_price']) if parsed['min_price'] is not None else None,
            'max_price': float(parsed['max_price']) if parsed['max_price'] is not None else None,
            'required': sorted(set(positives)), 'colors': sorted(set(colors)), 'excluded': sorted(set(negatives)), 'occasion': occasion, 'unsupported': unsupported}


def product_text(row):
    return ' '.join(str(row.get(field) or '') for field in ['name', 'listing_description', 'color', 'category'])


@lru_cache(maxsize=30000)
def matches(text, label):
    aliases = DETAILS.get(label, COLORS.get(label, [label]))
    return any(has(text, alias) for alias in aliases)


def reference_labels(labels):
    terms = set()
    for label in labels:
        found = {term for term, aliases in DETAILS.items() if any(has(label, alias) for alias in aliases)}
        found.update(alias for aliases in COLORS.values() for alias in aliases if has(label, alias))
        terms.update(found or {label})
    return sorted(terms)


def evidence(db, user):
    profile = db.get(TasteTest, user.id)
    answers = {row['question_id']: row for row in labeled_answers(profile.answers if profile else {})}
    feedback = list(db.scalars(select(CulturalFeedback).where(CulturalFeedback.user_id == user.id)
        .order_by(CulturalFeedback.updated_at.desc(), CulturalFeedback.entity_id)))
    rejected = {str(row.entity_id) for row in feedback if row.preference in ('dislike', 'known')}
    seeds = [str(row.entity_id) for row in feedback if row.preference == 'like' or row.fashion_inspiration and str(row.entity_id) not in rejected]
    run = db.scalar(select(CulturalDiscoveryRun).where(CulturalDiscoveryRun.user_id == user.id,
        CulturalDiscoveryRun.status == 'succeeded').order_by(CulturalDiscoveryRun.created_at.desc()).limit(1))
    if run:
        for resolution in (run.result or {}).get('resolutions', []):
            match = resolution.get('match', {})
            answer = answers.get(resolution.get('question_id'), {})
            current = [*answer.get('choices', []), *answer.get('names', []), answer.get('other', '')]
            if words(resolution.get('input', '')) not in {words(value) for value in current if value}: continue
            if resolution.get('status') == 'resolved' and match.get('entity_id') and match.get('type') in (
                    'urn:entity:artist', 'urn:entity:movie', 'urn:entity:tv_show', 'urn:entity:book'):
                if match['entity_id'] not in rejected: seeds.append(match['entity_id'])
    seeds = list(dict.fromkeys(seeds))[:20]
    images = list(images_for(db, user))
    analysis = db.scalar(select(TasteAnalysisRun).where(TasteAnalysisRun.user_id == user.id,
        TasteAnalysisRun.status == 'succeeded').order_by(TasteAnalysisRun.created_at.desc()).limit(1))
    observations = {}
    if analysis:
        sources = {str(row['id']): row for row in analysis.sources.get('images', [])}
        valid = {str(image.id) for image in images if str(image.id) in sources and
                 timestamp(sources[str(image.id)].get('updated_at')) == timestamp(image.updated_at)}
        observations = {row['image_id']: row for row in (analysis.result or {}).get('images', []) if row['image_id'] in valid}
    bridges = []
    for row in feedback:
        if not row.fashion_inspiration or str(row.entity_id) in rejected: continue
        selected = [observations[id] for id in (row.reference_image_ids or []) if id in observations]
        note = (row.fashion_note or '').strip()
        if note:
            parsed_note = intent(note)
            labels = sorted(set(parsed_note['required'] + parsed_note['colors']) - set(parsed_note['excluded']))
            if labels or parsed_note['excluded']:
                bridges.append({'name': row.entity.get('name', 'Saved discovery'), 'entity_id': str(row.entity_id),
                                'image_ids': [], 'labels': labels, 'excluded': parsed_note['excluded'], 'source': 'note'})
            continue  # The customer's explanation replaces older image-derived assumptions.
        if not selected: continue
        labels = sorted({str(label).casefold() for item in selected for field in ('colors', 'patterns', 'silhouettes', 'garments', 'possible_materials') for label in item.get(field, [])})
        bridges.append({'name': row.entity.get('name', 'Saved discovery'), 'entity_id': str(row.entity_id),
                        'image_ids': [item['image_id'] for item in selected], 'labels': reference_labels(labels)})
    palettes = {'Neutrals': ['neutrals'], 'Earthy tones': ['brown', 'beige', 'olive', 'rust', 'mustard'],
                'Pastels': ['pastels'], 'Dark tones': ['black', 'navy', 'burgundy', 'charcoal'],
                'Bright colors': ['red', 'yellow', 'orange', 'hot pink'], 'Monochrome': ['black', 'white', 'grey']}
    stated = [term for value in answers.get('q10', {}).get('choices', []) for term in palettes.get(value, [value])]
    stated += [part.strip() for value in answers.get('q11', {}).get('choices', []) for part in value.split('/')]
    stated += reference_labels([answers[id]['other'] for id in ('q10', 'q11') if answers.get(id, {}).get('other')])
    avoid_map = {'Neon colors': 'neon', 'Bodycon fits': 'bodycon', 'Oversized fits': 'oversized', 'Crop tops': 'cropped'}
    avoided = [avoid_map[value] for value in answers.get('q15', {}).get('choices', []) if value in avoid_map]
    return seeds, bridges, stated, avoided


def qloo_brands(request, seeds, rows, take=50):
    if not seeds: return {}, 'no_saved_interests'
    if not request.app.state.settings.qloo_api_key: return {}, 'unavailable'
    # `take` is our total exploration budget; Qloo allows at most 50 per page.
    # Keep the original first-page cache key so expansion reuses that lookup.
    budget = max(1, min(int(take), 150))
    page_size = min(budget, 50)
    deadline = monotonic() + 25
    brands, seen, succeeded = [], set(), False
    for page in range(1, (budget + page_size - 1) // page_size + 1):
        params = {'filter.type': 'urn:entity:brand', 'signal.interests.entities': ','.join(seeds), 'take': page_size}
        if page > 1: params['page'] = page
        try:
            batch = request.app.state.qloo.get(request.app.state.settings, '/v2/insights', params,
                deadline=deadline, timeout_seconds=12, ttl=900)
        except HTTPException:
            break  # A later-page failure must not discard successful pages.
        succeeded = True
        added = 0
        for brand in batch:
            identity = brand.get('entity_id') or key(brand.get('name', ''))
            if identity not in seen:
                seen.add(identity); brands.append(brand); added += 1
        if len(batch) < page_size or not added or len(brands) >= budget: break
    if not succeeded: return {}, 'unavailable'
    supported = {key(row['brand']) for row in rows}
    return {key(brand['name']): {'name': brand['name'], 'entity_id': brand['entity_id']} for brand in brands[:budget]
            if key(brand.get('name', '')) in supported}, 'ready'


def score_product(row, wanted, bridges, brands, corrections, stated):
    text, score, why, connections = product_text(row), 0.0, [], []
    occasion_matches = [label for label in OCCASIONS.get(wanted['occasion'], []) if matches(text, label)]
    if occasion_matches:
        score += min(12, len(occasion_matches) * 4); why.append('Listed ' + ', '.join(occasion_matches[:2]) + ' details fit your request')
    for bridge in bridges:
        score -= min(6, sum(matches(text, label) for label in bridge.get('excluded', [])) * 2)
        overlap = [label for label in bridge['labels'] if matches(text, label)]
        if overlap:
            score += min(10, len(overlap) * 2.5)
            connections.append({**bridge, 'matched_attributes': overlap})
    score = min(score, 26)
    if connections:
        connection = max(connections, key=lambda link: len(link['matched_attributes']))
        source = 'the fashion note you saved for' if connection.get('source') == 'note' else 'the looks you linked to'
        why.insert(0, f"Matches {', '.join(connection['matched_attributes'][:2])} in {source} {connection['name']}")
    brand = brands.get(key(row['brand']))
    if brand:
        score += 5; why.insert(0, 'Qloo connects this brand to your saved cultural interests')
    for label in stated:
        if matches(text, label): score += .5
    likes = [previous for previous in corrections if previous.kind == 'more_like_this']
    if any(previous.url == row['product_url'] for previous in likes): score += 8; why.insert(0, 'You liked this')
    similar, adjustment = False, 0
    for previous in likes[:50]:
        product = previous.product
        overlap = set(row.get('listing_style_terms', [])) & set(product.get('listing_style_terms', []))
        if overlap or product.get('color') == row.get('color') and product.get('category') == row['category']:
            adjustment += min(3, len(overlap) * .5 + .5); similar = True
    score += min(6, adjustment)
    negative = 0
    for previous in [item for item in corrections if item.kind == 'not_my_style'][:50]:
        if previous.product.get('category') == row['category']:
            overlap = set(row.get('listing_style_terms', [])) & set(previous.product.get('listing_style_terms', []))
            if len(overlap) >= 2: negative += .5
    score -= min(3, negative)  # A dismissal is ambiguous; do not turn it into a blanket color/brand ban.
    if similar: why.append('Shares listed details with your liked items')
    return score, list(dict.fromkeys(why))[:2], connections, brand


def public_product(row, preference=None):
    result = {field: row.get(field) for field in ('product_id', 'name', 'brand', 'price', 'mrp', 'currency', 'image_url', 'product_url', 'category', 'collected_at')} | {'feedback': preference, 'retailer': row.get('retailer') or 'Myntra'}
    if result['retailer'] == 'H&M': result['image_url'] = '/api/shop/images/' + row['product_id']
    return result


def taste_match(row, bridges, brands, corrections, stated, preferred=(), avoided_soft=()):
    """Weighted agreement with available taste signals, not a probability.

    Unavailable signals contribute no weight. Prices and hard request eligibility
    are deliberately separate from taste. No evidence means no invented score.
    """
    text = product_text(row)
    signals = []
    if brands:
        signals.append((30, float(key(row['brand']) in brands)))
    usable_bridges = [bridge for bridge in bridges if bridge['labels'] or bridge.get('excluded')]
    if usable_bridges:
        fits = []
        for bridge in usable_bridges:
            labels, excluded = bridge['labels'], bridge.get('excluded', [])
            fit = sum(matches(text, label) for label in labels) / len(labels) if labels else 1.0
            if excluded: fit -= sum(matches(text, label) for label in excluded) / len(excluded)
            fits.append(max(0, fit))
        signals.append((30, max(fits)))
    if stated:
        signals.append((15, float(any(matches(text, label) for label in stated))))
    likes = [item.product for item in corrections if item.kind == 'more_like_this']
    if likes:
        fit = 0.0
        for item in likes:
            if item.get('product_id') == row['product_id']: fit = 1.0; break
            if item.get('category') != row['category']: continue
            terms = set(item.get('listing_style_terms', []))
            overlap = len(terms & set(row.get('listing_style_terms', []))) / len(terms) if terms else 0
            fit = max(fit, overlap, .5 if item.get('color') == row.get('color') else 0)
        signals.append((15, fit))
    if preferred or avoided_soft:
        fit = sum(matches(text, label) for label in preferred) / len(preferred) if preferred else 1.0
        if avoided_soft: fit -= sum(matches(text, label) for label in avoided_soft) / len(avoided_soft)
        signals.append((20, max(0, fit)))
    if not signals: return None
    negative = [item.product for item in corrections if item.kind == 'not_my_style']
    penalty = min(.15, sum(.05 for item in negative if item.get('category') == row['category'] and
        len(set(item.get('listing_style_terms', [])) & set(row.get('listing_style_terms', []))) >= 2))
    agreement = sum(weight * fit for weight, fit in signals) / sum(weight for weight, _ in signals)
    return round(100 * max(0, min(1, agreement - penalty)))


def preference_group(term):
    if term in COLORS or any(term in aliases for aliases in COLORS.values()): return 'color'
    if term in ('floral', 'striped', 'checked', 'solid', 'embroidered', 'sequinned'): return 'pattern'
    if term in ('mini', 'midi', 'maxi'): return 'length'
    if term in ('cotton', 'linen', 'satin', 'denim', 'lace', 'knitted'): return 'material'
    if term in ('a-line', 'bodycon', 'wide leg', 'straight', 'oversized', 'relaxed', 'fitted',
                'flared', 'wrap', 'pleated', 'tailored', 'structured'): return 'shape'
    return term


def preference_agreement(text, positive, negative):
    # Colors and other alternatives within one attribute are OR preferences.
    groups = {}
    for term in positive: groups.setdefault(preference_group(term), []).append(term)
    values = [any(matches(text, term) for term in terms) for terms in groups.values()]
    values += [not matches(text, term) for term in negative]
    return sum(values), len(values)


def contextual_match(priority, personal):
    """Monotone priority bands: lower tiers cannot compensate for intent misses.

    Personalization orders items inside each intent tier. Rounded ties preserve
    the exact priority order in the stable frontend sort. This remains a heuristic.
    """
    value, bands = 0, 1
    for matched, possible in priority:
        value = value * (possible + 1) + matched
        bands *= possible + 1
    if bands == 1: return personal
    return round(100 * (value + (personal or 0) / 101) / bands)


def rank_catalog(rows, wanted, corrections, bridges, brands, stated, liked_only=False,
                 preferred=(), avoided_soft=(), cheaper=False, request_first=False,
                 focus_preferred=(), focus_avoided=()):
    preferences = {row.url: row.kind for row in corrections}
    results = []
    for row in rows:
        if wanted['unsupported'] or preferences.get(row['product_url']) == 'not_my_style': continue
        if liked_only and preferences.get(row['product_url']) != 'more_like_this': continue
        if wanted['categories'] and row['category'] not in wanted['categories']: continue
        if wanted['min_price'] is not None and row['price'] < wanted['min_price']: continue
        if wanted['max_price'] is not None and row['price'] > wanted['max_price']: continue
        text = product_text(row)
        if any(not matches(text, label) for label in wanted['required']): continue
        if wanted['colors'] and not any(matches(text, color) for color in wanted['colors']): continue
        if any(matches(text, label) for label in wanted['excluded']): continue
        score, why, connections, brand = score_product(row, wanted, bridges, brands, corrections, stated)
        soft_matches = [term for term in preferred if matches(text, term)]
        score += min(12, len(soft_matches) * 4)
        if soft_matches: why.append('Fits your preference for ' + ', '.join(soft_matches[:2]))
        score -= min(8, sum(matches(text, term) for term in avoided_soft) * 4)
        if cheaper: score += 8 / (1 + row['price'] / 500)
        results.append({**public_product(row, preferences.get(row['product_url'])), 'why': why,
                        'connections': connections[:2], 'qloo_brand': brand, '_score': score,
                        'taste_match': taste_match(row, bridges, brands, corrections, stated, preferred, avoided_soft)})
    if request_first:
        highest_price = max((row['price'] for row in results), default=1)
        source_by_id = {row['product_id']: row for row in rows}
        for item in results:
            # Public product fields retain the listing name; use the full source
            # record for metadata matching just as the eligibility checks do.
            row = source_by_id[item['product_id']]
            text = product_text(row)
            priority = [preference_agreement(text, focus_preferred, focus_avoided)]
            if cheaper:
                priority.append((min(4, int(5 * (1 - row['price'] / highest_price))), 4))
            occasion = OCCASIONS.get(wanted['occasion'], [])
            if occasion: priority.append((int(any(matches(text, term) for term in occasion)), 1))
            priority.append(preference_agreement(text, preferred, avoided_soft))
            personal = taste_match(row, bridges, brands, corrections, stated)
            item['_request_priority'] = tuple(matched for matched, _ in priority)
            item['taste_match'] = contextual_match(priority, personal)
            focus_matches = [term for term in focus_preferred if matches(text, term)]
            requested = [term for term in preferred if matches(text, term)]
            if focus_matches:
                item['why'].insert(0, 'Matches your correction: ' + ', '.join(focus_matches[:2]))
            elif requested:
                item['why'].insert(0, 'Matches your request: ' + ', '.join(requested[:2]))
            elif occasion and any(matches(text, term) for term in occasion):
                item['why'].insert(0, 'Listed details fit your ' + wanted['occasion'] + ' request')
        results.sort(key=lambda row: (tuple(-value for value in row['_request_priority']),
            -(row['taste_match'] if row['taste_match'] is not None else -1),
            row['price'] if cheaper else 0, -row['_score'], row['price'], row['product_id']))
        return results
    results.sort(key=lambda row: (-(row['taste_match'] if row['taste_match'] is not None else -1),
                                 -row['_score'], row['price'], row['product_id']))
    return results


@router.post('/search')
def search(body: OutfitRequest, request: Request, user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)):
    request.app.state.search_limiter.check(user)
    rows, wanted = catalog(request), intent(body.query)
    corrections = [SimpleNamespace(url=row.url, kind=row.kind, product=row.product) for row in db.scalars(
        select(ProductFeedback).where(ProductFeedback.user_id == user.id).order_by(ProductFeedback.updated_at.desc()))]
    preferences = {row.url: row.kind for row in corrections}
    seeds, bridges, stated, avoided = evidence(db, user)
    wanted['excluded'] = sorted(set(wanted['excluded'] + [label for label in avoided if label not in wanted['required']]))
    # Do not keep a DB transaction open while waiting for Qloo.
    db.commit()
    brands, qloo_status = qloo_brands(request, seeds, rows) if not wanted['unsupported'] else ({}, 'not_requested')
    results = rank_catalog(rows, wanted, corrections, bridges, brands, stated, body.liked_only)
    page = results[body.offset:body.offset + body.limit]
    for row in page: row.pop('_score')
    return {'products': page, 'total': len(results), 'offset': body.offset, 'catalog_count': len(rows),
            'filters': wanted, 'taste': {'qloo_status': qloo_status, 'qloo_brands': len(brands),
                'linked_discoveries': len(bridges)}, 'notice': 'This catalog contains women’s clothing only; try a supported clothing request.' if wanted['unsupported'] else None}


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    product_id: str = Field(pattern=r'^(?:(?:ajio|nykaa|shein-india|hm):)?\d{1,20}(?:_[a-zA-Z0-9-]{1,35})?$')
    choice: Literal['like', 'dislike', 'clear']


@router.post('/feedback')
def feedback(body: FeedbackRequest, request: Request, user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)):
    item = next((row for row in catalog(request) if row['product_id'] == body.product_id), None)
    if not item: raise HTTPException(404, 'Product not found in the catalog.')
    locked_profile(db, user)
    row = db.scalar(select(ProductFeedback).where(ProductFeedback.user_id == user.id, ProductFeedback.url == item['product_url']))
    if body.choice == 'clear':
        if row: db.delete(row)
    else:
        if not row:
            row = ProductFeedback(id=uuid4(), user_id=user.id, url=item['product_url']); db.add(row)
        row.kind = 'more_like_this' if body.choice == 'like' else 'not_my_style'
        row.product = {field: item.get(field) for field in ('product_id', 'name', 'brand', 'category', 'color', 'listing_style_terms')}
        row.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {'product_id': body.product_id, 'choice': body.choice}


@router.get('/feedback')
def saved_feedback(request: Request, user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)):
    choices = {row.url: row.kind for row in db.scalars(select(ProductFeedback).where(ProductFeedback.user_id == user.id))}
    return {'choices': {row['product_id']: 'like' if choices[row['product_url']] == 'more_like_this' else 'dislike'
                        for row in catalog(request) if choices.get(row['product_url']) in ('more_like_this', 'not_my_style')}}
