"""Authenticated product search. Public catalogs are shared; taste ranking is owner-scoped."""
from collections import OrderedDict
from datetime import datetime, timezone
from decimal import Decimal
import re
from threading import Lock
from time import monotonic
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from .analysis import labeled_answers, source_hash
from .auth import AuthUser, get_current_user
from .catalog import SOURCES, BY_ID, CatalogError, external_search
from .database import get_db
from .enrichment import snapshot, dismissed_for, latest_run as latest_enrichment
from .models import TasteAnalysisRun, TasteTest
from .onboarding import images_for

router = APIRouter(prefix='/api/search', tags=['Shopping search'])
CATEGORIES = {
    'dresses': ['dress', 'dresses', 'gown', 'gowns', 'jumpsuit'],
    'tops': ['shirt', 'shirts', 'blouse', 'blouses', 'tee', 't-shirt', 'top', 'tops', 'polo', 'tunic', 'tunics', 'kurta', 'kurtas', 'kurti', 'kurtis'],
    'bottoms': ['trouser', 'trousers', 'pant', 'pants', 'jeans', 'skirt', 'skirts', 'shorts', 'leggings'],
    'shoes': ['shoe', 'shoes', 'sneaker', 'sneakers', 'footwear', 'trainer', 'trainers', 'boot', 'boots', 'sandal', 'sandals'],
    'outerwear': ['coat', 'coats', 'jacket', 'jackets', 'cardigan', 'blazer', 'blazers', 'sweater'],
    'bags': ['bag', 'bags', 'handbag', 'handbags', 'tote', 'backpack', 'clutch'],
    'accessories': ['jewelry', 'jewellery', 'earring', 'earrings', 'necklace', 'bracelet', 'ring', 'scarf', 'belt'],
}
COLORS = {
    'black': ['black'], 'white': ['white', 'ivory'], 'cream': ['cream', 'ivory', 'ecru'],
    'blue': ['blue', 'navy', 'azure'], 'pink': ['pink', 'blush'], 'red': ['red', 'burgundy', 'scarlet', 'maroon'],
    'green': ['green', 'sage', 'olive', 'mint'], 'purple': ['purple', 'lavender', 'lilac'],
    'brown': ['brown', 'tan', 'chocolate'], 'beige': ['beige', 'sand', 'nude'], 'grey': ['grey', 'gray', 'silver'],
    'yellow': ['yellow', 'gold'], 'orange': ['orange', 'peach'],
    'pastels': ['pastel', 'blush', 'lavender', 'lilac', 'mint', 'pale pink', 'light blue', 'powder blue', 'pale yellow'],
    'neutrals': ['black', 'white', 'ivory', 'cream', 'beige', 'grey', 'gray', 'tan'],
}
OCCASIONS = {'party': ['party', 'farewell', 'evening', 'cocktail'],
             'wedding': ['wedding', 'bridal', 'bridesmaid', 'ceremony'],
             'work': ['work', 'office', 'business', 'tailored'],
             'casual': ['casual', 'everyday', 'weekend', 'relaxed'],
             'active': ['sport', 'running', 'walking', 'training', 'athletic', 'gym']}
FITS = ['relaxed', 'fitted', 'oversized', 'tailored', 'bodycon', 'a-line', 'wide-leg', 'slim', 'straight']
DETAILS = ['floral', 'striped', 'linen', 'cotton', 'silk', 'denim', 'lace', 'satin', 'sequin', 'sequins', 'midi', 'maxi', 'mini', 'leather', 'knit', 'chiffon']
GARMENTS = {
    'blouse': ['blouse', 'blouses'], 'tunic': ['tunic', 'tunics'],
    'kurta': ['kurta', 'kurtas', 'kurti', 'kurtis'], 't-shirt': ['t-shirt', 't-shirts', 'tee', 'tees'],
    'shirt': ['shirt', 'shirts'], 'jumpsuit': ['jumpsuit', 'jumpsuits'],
    'skirt': ['skirt', 'skirts'], 'jeans': ['jeans'], 'shorts': ['shorts'],
    'trousers': ['trouser', 'trousers', 'pant', 'pants'], 'gown': ['gown', 'gowns'],
    'cardigan': ['cardigan', 'cardigans'], 'blazer': ['blazer', 'blazers'],
}
DETAIL_ALIASES = {
    'wrap': ['wrap', 'wrap-front', 'wrap front', 'crossover', 'cross-over'],
    'ruched': ['ruched', 'ruching', 'ruche'], 'smocked': ['smocked', 'smocking'],
    'v-neck': ['v-neck', 'v neck', 'vneck'], 'square-neck': ['square-neck', 'square neck'],
    'long sleeve': ['long sleeve', 'long sleeves', 'long-sleeve', 'long-sleeved', 'full sleeve', 'full sleeves'],
    'short sleeve': ['short sleeve', 'short sleeves', 'short-sleeve', 'short-sleeved'],
    'sleeveless': ['sleeveless'], 'tie-front': ['tie-front', 'tie front', 'front tie'],
    'peplum': ['peplum'], 'cropped': ['cropped', 'crop top'],
}
STOP = {'find','show','me','a','an','the','some','something','for','in','with','and','my','i','want','need','looking','look','outfit','outfits','please','to','wear'}


def clean(value):
    return ' '.join(value.casefold().replace('’', "'").split())


def mentions(text, term):
    # Negated product text ("no sequins") is not evidence of that attribute.
    pattern = r'(?<![a-z0-9])' + re.escape(clean(term)) + r'(?![a-z0-9])'
    for match in re.finditer(pattern, clean(text)):
        if not re.search(r'(?:no|not|without|non)[ -]?(?:\w+\s+)?$', clean(text)[:match.start()]):
            return True
    return False


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    query: str = Field(min_length=2, max_length=300)
    source_ids: list[str] = Field(default_factory=lambda: list(BY_ID), min_length=1, max_length=10)
    category: Literal['all', 'dresses', 'tops', 'bottoms', 'shoes', 'outerwear', 'bags', 'accessories'] | None = None
    color: str = Field(default='', max_length=40)
    size: str = Field(default='', max_length=30)
    fit: str = Field(default='', max_length=40)
    occasion: Literal['party', 'wedding', 'work', 'casual', 'active'] | None = None
    min_price: Decimal | None = Field(default=None, ge=0, le=10000000)
    max_price: Decimal | None = Field(default=None, gt=0, le=10000000)
    currency: Literal['INR', 'USD'] | None = None
    sort: Literal['personalized', 'relevance', 'price_asc', 'price_desc'] = 'personalized'

    @field_validator('source_ids')
    @classmethod
    def known_sources(cls, values):
        if len(set(values)) != len(values) or set(values) - BY_ID.keys():
            raise ValueError('Choose valid, unique shopping sources.')
        return values

    @field_validator('query', 'color', 'fit', 'size')
    @classmethod
    def no_control_characters(cls, value):
        if any(ord(c) < 32 for c in value):
            raise ValueError('Use plain text for your search.')
        return value


def parse_request(request):
    text = clean(request.query)
    number = r'(\d[\d,]*(?:\.\d+)?\s*[kK]?)'
    def money(value):
        value = value.replace(',', '').replace(' ', '').casefold()
        return Decimal(value.rstrip('k')) * (1000 if value.endswith('k') else 1)
    minimum, maximum = None, None
    currency = request.currency or ('USD' if '$' in text or 'usd' in text else 'INR')
    interval = re.search(r'between\s*(?:₹|rs\.?|inr|usd|\$)?\s*' + number + r'\s*(?:and|to|-)\s*(?:₹|rs\.?|inr|usd|\$)?\s*' + number, text)
    ceiling = re.search(r'(?:under|below|less than|at most|up to|budget(?: of)?)\s*(?:₹|rs\.?|inr|usd|\$)?\s*' + number, text)
    floor = re.search(r'(?:over|above|at least)\s*(?:₹|rs\.?|inr|usd|\$)?\s*' + number, text)
    if re.search(r'(?:under|below|budget|between|above|over)\s*(?:₹|\$)?\s*-\d', text):
        raise HTTPException(422, 'Use a positive budget.')
    if interval:
        minimum, maximum = money(interval[1]), money(interval[2])
        text = text.replace(interval[0], ' ')
    else:
        if ceiling:
            maximum = money(ceiling[1]); text = text.replace(ceiling[0], ' ')
        if floor:
            minimum = money(floor[1]); text = text.replace(floor[0], ' ')
    minimum = request.min_price if request.min_price is not None else minimum
    maximum = request.max_price if request.max_price is not None else maximum
    if (minimum is not None and minimum > 10000000) or (maximum is not None and (maximum <= 0 or maximum > 10000000)):
        raise HTTPException(422, 'Choose a budget between 0 and 10,000,000.')
    if minimum is not None and maximum is not None and minimum > maximum:
        raise HTTPException(422, 'Minimum price must not exceed maximum price.')
    category = next((key for key, terms in CATEGORIES.items() if any(mentions(text, term) for term in terms)), None)
    if request.category is not None:
        category = None if request.category == 'all' else request.category
    color = request.color or next((key for key in COLORS if mentions(text, key) or (key == 'pastels' and mentions(text, 'pastel'))), '')
    if color == 'any': color = ''
    fit = request.fit or next((fit for fit in FITS if mentions(text, fit)), '')
    occasion = request.occasion or next((key for key, terms in OCCASIONS.items() if any(mentions(text, term) for term in terms)), None)
    size_match = re.search(r'\bsize\s+(xxs|xs|xxl|xl|s|m|l|small|medium|large|\d{1,2}(?:\.\d)?)\b', text)
    size = request.size or (size_match[1] if size_match else '')
    size = {'small':'S','medium':'M','large':'L'}.get(clean(size), size)
    if size_match: text = text.replace(size_match[0], ' ')
    # Send only shopping terms to stores, not profile data or an LLM prompt.
    ignored = STOP | {w for terms in OCCASIONS.values() for t in terms for w in t.split()}
    if category:
        ignored |= {w for terms in CATEGORIES.values() for t in terms for w in t.split()}
    ignored |= {clean(color)} | set(FITS) | {'pastel'}
    words = [w for w in re.findall(r"[a-zA-Z0-9'-]+", text) if w not in ignored]
    garment = next((name for name, aliases in GARMENTS.items() if any(mentions(text, alias) for alias in aliases)), None)
    # Preserve a requested garment instead of broadening blouse/shirt/tunic to top.
    noun = garment or {'dresses':'dress','tops':'top','bottoms':'pants','shoes':'shoes','outerwear':'jacket','bags':'bag','accessories':'accessories'}.get(category)
    catalog_query = ' '.join(dict.fromkeys([*(words[:8]), *([noun] if noun else [])])).strip()
    if not catalog_query:
        raise HTTPException(422, 'Include a product type or a shopping keyword, such as dress or shoes.')
    return {'query': request.query, 'catalog_query': catalog_query, 'category': category,
            'color': color, 'size': size, 'fit': fit, 'occasion': occasion,
            'min_price': minimum, 'max_price': maximum, 'currency': currency,
            'garment': garment,
            'details': [detail for detail in DETAILS if mentions(request.query, detail)] +
                       [name for name, aliases in DETAIL_ALIASES.items() if any(mentions(request.query, alias) for alias in aliases)],
            'sort': request.sort}


def taste_context(db, user, settings):
    profile = db.get(TasteTest, user.id)
    rows = labeled_answers(profile.answers if profile else {})
    answers = {r['question_id']: [v for v in [*r['choices'], r['other']] if v and v != 'Other'] for r in rows}
    analysis = db.scalar(select(TasteAnalysisRun).where(TasteAnalysisRun.user_id == user.id, TasteAnalysisRun.status == 'succeeded')
                         .order_by(TasteAnalysisRun.created_at.desc(), TasteAnalysisRun.id.desc()).limit(1))
    visual = []
    if analysis and analysis.source_hash == source_hash(profile, images_for(db, user)):
        visual = (analysis.result or {}).get('recurring_visual_signals', [])
    run = latest_enrichment(db, user, succeeded=True)
    affinities = set()
    if run:
        _, fingerprint = snapshot(db, user, settings)
        if run.source_hash == fingerprint:
            dismissed = dismissed_for(db, user)
            affinities = {a['entity_id'] for a in (run.result or {}).get('affinities', []) if a['entity_id'] not in dismissed}
    return {'answers': answers, 'visual': visual, 'qloo': affinities, 'has_profile': bool(profile)}


def disliked(text, values):
    aliases = {'Neon colors':['neon','fluorescent'], 'Loud prints':['loud print','bold print','leopard print','animal print'],
               'Bodycon fits':['bodycon','body-con'], 'Oversized fits':['oversized','oversize'],
               'Crop tops':['crop top','cropped top'], 'High heels':['high heel','heels','stiletto']}
    for value in values:
        if value in ('No strong dislikes','Expensive items'): continue
        custom = re.sub(r'^(?:no|avoid|without)\s+', '', clean(value))
        terms = aliases.get(value, [custom])
        if value not in aliases and custom.isalpha() and len(custom) > 3:
            terms = [custom, custom[:-1] if custom.endswith('s') else custom + 's']
        if any(mentions(text, term) for term in terms):
            return value
    return None


def color_matches(color, text):
    return any(mentions(text, term) for term in COLORS.get(clean(color), [color]))


def ranked_product(product, filters, taste, exchange):
    title = product['title'] + ' ' + product['product_type']
    text = title + ' ' + product['description']
    category = filters['category']
    if category and not any(mentions(title, term) for term in CATEGORIES[category]):
        return None, 'category'
    if filters.get('garment') and not any(mentions(title, term) for term in GARMENTS[filters['garment']]):
        return None, 'garment'
    if filters['fit'] and not mentions(text, filters['fit']):
        return None, 'fit'
    if any(not any(mentions(text, alias) for alias in DETAIL_ALIASES.get(detail, [detail])) for detail in filters['details']):
        return None, 'details'
    audience = 'women' if re.search(r"\b(women|woman|women's|female)\b", clean(filters['query'])) else 'men' if re.search(r"\b(men|man|men's|male)\b", clean(filters['query'])) else None
    if audience and (mentions(title, "men's") or mentions(title, 'men')) and audience == 'women': return None, 'audience'
    if audience and (mentions(title, "women's") or mentions(title, 'women')) and audience == 'men': return None, 'audience'
    variants = []
    for variant in product['variants']:
        options = variant['options']
        sizes = [value for key, value in options.items() if 'size' in key]
        if filters['size'] and not any(clean(size) == clean(filters['size']) for size in sizes): continue
        colors = [value for key, value in options.items() if 'color' in key or 'colour' in key]
        color_text = ' '.join(colors) if colors else (text if product.get('page_metadata') else product['title'])
        if filters['color'] and not color_matches(filters['color'], color_text): continue
        if disliked(text + ' ' + ' '.join(colors), taste['answers'].get('q15', [])): continue
        value = variant['price']
        if variant['currency'] != filters['currency']:
            rates = exchange['rates']
            if variant['currency'] not in rates or filters['currency'] not in rates: continue
            value = value / rates[variant['currency']] * rates[filters['currency']]
        # Compare full precision before rounding a converted display price.
        if filters['min_price'] is not None and value < filters['min_price']: continue
        if filters['max_price'] is not None and value > filters['max_price']: continue
        variants.append((value, variant))
    if not variants: return None, 'variant_or_preferences'
    value, variant = min(variants, key=lambda row: row[0])
    options_text = ' '.join(variant['options'].values())
    metadata = text + ' ' + options_text
    words = set(re.findall(r'[a-z]{3,}', clean(filters['catalog_query'])))
    relevance = sum(1 for word in words if mentions(metadata, word))
    if not category and not relevance:
        return None, 'keywords'
    boost, why = 0, []
    if filters['color']: why.append('Matches your ' + filters['color'] + ' color filter.')
    if filters['size']: why.append('Size ' + filters['size'] + ' is available in this variant.')
    if filters['max_price'] is not None: why.append('Within your selected budget at the displayed conversion rate.' if variant['currency'] != filters['currency'] else 'Within your selected budget.')
    if filters['occasion'] and any(mentions(metadata, t) for t in OCCASIONS[filters['occasion']]):
        relevance += 2; why.append('The store description includes ' + filters['occasion'] + '-related details.')
    if filters['sort'] == 'personalized':
        for preference in taste['answers'].get('q9', []):
            terms = re.findall(r'[a-z-]{4,}', clean(preference))
            if any(mentions(metadata, term) for term in terms):
                boost += 2; why.append('Matches an aesthetic you selected in your taste test.'); break
        for preference in taste['answers'].get('q10', []):
            family = {'Pastels':'pastels','Neutrals':'neutrals','Earthy tones':'brown','Dark tones':'black'}.get(preference, preference)
            color_text = ' '.join(value for key, value in variant['options'].items() if 'color' in key or 'colour' in key) or product['title']
            if color_matches(family, color_text):
                boost += 3; why.append('Matches your saved ' + preference.lower() + ' color preference.'); break
        for preference in taste['answers'].get('q11', []):
            terms = re.findall(r'[a-z-]{4,}', clean(preference))
            if any(mentions(metadata, term) for term in terms):
                boost += 3; why.append('Matches a fit you selected in your taste test.'); break
        visual_matches = [s['attribute'] for s in taste['visual'] if len(s['attribute']) <= 100 and mentions(metadata, s['attribute'])]
        if visual_matches:
            boost += 2; why.append('Shares ' + ', '.join(visual_matches[:2]) + ' with your saved inspirations.')
        if product['qloo_entity_id'] in taste['qloo']:
            boost += 1; why.append(product['source_name'] + ' is in your saved Qloo brand affinities.')
    if not why: why.append('Matches your search in the store’s current product catalog.')
    converted = variant['currency'] != filters['currency']
    result = {key: product[key] for key in ('id','title','brand','url','image','source_id','source_name','fetched_at')}
    result.update(url=product['url'] + '?variant=' + variant['id'],
                  price={'amount':str(value.quantize(Decimal('0.01'))),'currency':filters['currency'],'estimated':converted},
                  original_price={'amount':str(variant['price']),'currency':variant['currency']},
                  available=True, selected_options=variant['options'], why=why[:5],
                  match_label='Matches your taste' if boost else 'Matches your search',
                  variants_truncated=product['variants_truncated'],
                  _score=relevance + boost, _price=value)
    return result, None


class SearchLimiter:
    def __init__(self): self.lock, self.entries = Lock(), OrderedDict()
    def check(self, user):
        with self.lock:
            now = monotonic()
            times = [t for t in self.entries.get(str(user.id), []) if t > now - 60]
            if len(times) >= 10:
                raise HTTPException(429, 'Please wait before searching again.', headers={'Retry-After':'60'})
            self.entries[str(user.id)] = [*times, now]
            self.entries.move_to_end(str(user.id))
            while len(self.entries) > 2048: self.entries.popitem(last=False)


@router.get('/sources')
def get_sources(request: Request, user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)):
    taste = taste_context(db, user, request.app.state.settings)
    return {'sources': [{'id':s['id'],'name':s['name'],'kind':s['kind'],'website':s['website'],
                         'mode':'catalog' if s.get('shop') else 'website',
                         'qloo_affinity':s.get('qloo_entity_id') in taste['qloo']} for s in SOURCES],
            'default_source_ids':list(BY_ID)}


@router.post('/products')
def search_products(body: SearchRequest, request: Request, user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)):
    request.app.state.search_limiter.check(user)
    filters = parse_request(body)
    taste = taste_context(db, user, request.app.state.settings)
    sources = [BY_ID[id] for id in body.source_ids]
    connected = [s for s in sources if s.get('shop')]
    external_query = ' '.join(dict.fromkeys([term for term in (filters['color'], filters['fit'], filters['catalog_query']) if term]))
    links = [{'id':s['id'],'name':s['name'],'url':external_search(s, external_query)} for s in sources if not s.get('shop')]
    products, statuses = request.app.state.catalog.search(connected, filters['catalog_query']) if connected else ([], [])
    if connected and not any(s['status'] == 'ok' for s in statuses):
        raise HTTPException(503, 'The selected brand stores could not be reached. Please retry or choose another source.')
    exchange = None
    if any(v['currency'] != filters['currency'] for p in products for v in p['variants']):
        try: exchange = request.app.state.catalog.rates()
        except CatalogError as failure: raise HTTPException(503, failure.message) from None
    ranked, excluded = [], {}
    for product in products:
        result, reason = ranked_product(product, filters, taste, exchange)
        if result:
            ranked.append(result)
        else:
            excluded[reason] = excluded.get(reason, 0) + 1
    # Store/product identities are stable across repeated search responses.
    ranked = list({p['id']:p for p in ranked}.values())
    if filters['sort'].startswith('price_'):
        ranked.sort(key=lambda p:(p['_price'],p['id']), reverse=filters['sort']=='price_desc')
    else:
        ranked.sort(key=lambda p:(-p['_score'],p['source_id'],p['id']))
    for product in ranked:
        product.pop('_score'); product.pop('_price')
    applied = {k:(str(v) if isinstance(v,Decimal) else v) for k,v in filters.items() if k != 'details'}
    return {'products':ranked,'applied_filters':applied,'source_statuses':statuses,'retailer_links':links,
            'status':'external_only' if not connected else 'partial' if any(s['status']!='ok' for s in statuses) else 'ok',
            'profile_used':taste['has_profile'],'excluded_count':sum(excluded.values()),
            'exchange':{'source':exchange['source'],'date':exchange['date']} if exchange else None,
            'searched_at':datetime.now(timezone.utc).isoformat()}
