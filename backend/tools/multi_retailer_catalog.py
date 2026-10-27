"""Normalize and verify saved source snapshots; never fetch listings during search."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from io import BytesIO
import json
import math
from pathlib import Path
import re
import ssl
import sys

import httpx
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from app.retailers import valid_source
from tools import myntra_probe, myntra_expand
from tools.multi_retailer_collect import OUT, write

CATEGORY_TERMS = [
    ('Kurta Sets', r'kurta.*(?:set|pant|trouser|dupatta)|suit set'),
    ('Co-Ords', r'co.?ord|coord set'), ('Tshirts', r't.?shirts?|\btees?\b'),
    ('Sweatshirts', r'sweatshirt|hoodie'), ('Blazers', r'blazer'),
    ('Jackets', r'jacket|\bcoat\b'), ('Sweaters', r'sweater|cardigan|jumper'),
    ('Dresses', r'dress|gown'), ('Kurtas', r'kurta|kurti|kurtis'),
    ('Jeans', r'jeans'), ('Trousers', r'trouser|palazzo|\bpants?\b'),
    ('Skirts', r'skirt'), ('Shorts', r'shorts'), ('Shirts', r'shirt'),
    ('Tops', r'\btop\b|tops|blouse|tunic'),
]
CATEGORY_NAMES = {c for _, _, c in myntra_expand.CATEGORIES}
EXCLUDED = r"\b(?:men|man|mens|boys?|girls?|kids?|children|unisex|dog|pet|baby|bra|lingerie|nightdress|jumpsuit|saree)\b"


def normalize(raw, retailer, observed_at=None):
    if retailer == 'AJIO':
        identifier = str(raw.get('product_id') or '')
        name, brand = raw.get('name'), raw.get('brand')
        image, url = raw.get('main_image'), raw.get('canonical_url') or raw.get('url')
        price, mrp = raw.get('price'), raw.get('regular_price')
        color = raw.get('color')
        women = any(str(v).lower() in ('women', "women's") for v in raw.get('breadcrumbs', []))
        prefix = 'ajio:'
    elif retailer == 'Nykaa Fashion':
        identifier = str(raw.get('id') or '')
        name, brand = raw.get('sub_title'), raw.get('title')
        image = raw.get('image_url')
        action = raw.get('action_url') or ''
        url = 'https://www.nykaafashion.com' + action if action.startswith('/') else action
        price, mrp = raw.get('discounted_price'), raw.get('price')
        siblings = (raw.get('plp_pdp_bridge') or {}).get('siblings_colour') or []
        color = next((v.get('color_name') for v in siblings if str(v.get('id')) == identifier), None)
        women = '6557' in {str(v) for v in raw.get('category_id', [])} or bool(re.search(r'\bwomen\b', str(name), re.I))
        prefix = 'nykaa:'
    elif retailer == 'H&M':
        identifier = str(raw.get('id') or '')
        name, brand = raw.get('productName'), raw.get('brandName')
        image, url = raw.get('imageModelSrc') or raw.get('imageProductSrc'), raw.get('productUrl')
        price, mrp, color = raw.get('price'), None, raw.get('colorName')
        women = str(raw.get('mainCatCode') or '').startswith('ladies_') and raw.get('locale') == 'en_in'
        prefix = 'hm:'
    else:
        raise ValueError('Unsupported source adapter')
    text = str(name or '') + ' ' + str(raw.get('category') or '') + ' ' + str(raw.get('mainCatCode') or '').replace('_', ' ')
    category = next((category for category, pattern in CATEGORY_TERMS if re.search(pattern, text, re.I)), None)
    numeric = lambda v: isinstance(v, (float, int)) and not isinstance(v, bool) and math.isfinite(v) and v > 0
    if not women or re.search(EXCLUDED, str(name), re.I) or not category or not name or not brand or not numeric(price): return None
    if mrp is not None and (not numeric(mrp) or price > mrp): return None
    if raw.get('currency', 'INR') != 'INR': return None
    row = {'product_id': prefix + identifier, 'source_product_id': identifier,
           'retailer': retailer, 'name': name, 'brand': brand, 'gender': 'Women',
           'category': category, 'color': color, 'price': price, 'mrp': mrp, 'currency': 'INR',
           'image_url': image, 'product_url': url, 'listing_description': '',
           'listing_style_terms': [label for label, pattern in myntra_expand.STYLE_PATTERNS.items() if re.search(pattern, str(name), re.I)],
           'collected_at': raw.get('scraped_at') or observed_at,
           'source_url': raw.get('from_url') or raw.get('url'),
           'listed_sizes': [], 'available_sizes_observed': [], 'stock_status': 'unknown',
           'price_status': 'listing_snapshot', 'product_link_status': 'structure_validated_live_access_not_confirmed'}
    if retailer == 'Nykaa Fashion':
        variants = ((raw.get('plp_pdp_bridge') or {}).get('variants') or {}).get('size', [])
        row['listed_sizes'] = [v['name'] for v in variants if v.get('name')]
        row['available_sizes_observed'] = [v['name'] for v in variants if v.get('name') and str(v.get('in_stock')) == '1']
        if row['available_sizes_observed']: row['stock_status'] = 'available_in_listing'
        if raw.get('is_out_of_stock') in (True, 1, '1'): return None
    if retailer == 'H&M':
        row['listed_sizes'] = raw.get('allSizes') or []
        row['available_sizes_observed'] = raw.get('availableSizes') or []
        if raw.get('stockState') == 'Available': row['stock_status'] = 'available_in_listing'
        elif raw.get('stockState'): return None
    return row if valid_source(row) else None


def candidates():
    old = ROOT / 'backend/data/myntra-1500'
    rows = {r['product_id']: {**r, 'retailer': 'Myntra'} for r in json.loads((old/'catalog-products.json').read_text(encoding='utf-8'))}
    for path in old.glob('*-raw.json'):
        for raw in json.loads(path.read_text(encoding='utf-8')):
            row = myntra_probe.normalize(raw, 'mixed')
            if not row['validation_errors'] and row['category'] in CATEGORY_NAMES:
                row.update(retailer='Myntra', listing_description=str(raw.get('additionalInfo') or ''),
                           listing_style_terms=[k for k,p in myntra_expand.STYLE_PATTERNS.items() if re.search(p,str(raw.get('name')),re.I)])
                rows.setdefault(row['product_id'], row)
    for path in sorted(OUT.glob('*-raw.json')):
        status_path = path.with_name(path.name.replace('-raw.json','-status.json'))
        observed_at = json.loads(status_path.read_text(encoding='utf-8')).get('startedAt') if status_path.exists() else None
        retailer = 'AJIO' if path.name.startswith('ajio-') else 'Nykaa Fashion' if path.name.startswith('nykaa-') else 'H&M' if path.name.startswith('hm-') else None
        for raw in json.loads(path.read_text(encoding='utf-8')):
            if path.name.startswith('myntra-'):
                row = myntra_probe.normalize(raw, 'mixed')
                if row['validation_errors'] or row['category'] not in CATEGORY_NAMES: continue
                row.update(retailer='Myntra', listing_description=str(raw.get('additionalInfo') or ''),
                           listing_style_terms=[k for k,p in myntra_expand.STYLE_PATTERNS.items() if re.search(p,str(raw.get('name')),re.I)])
            elif retailer:
                row = normalize(raw, retailer, observed_at=observed_at)
            else: continue
            if row: rows.setdefault(row['product_id'], row)
    return [row for row in rows.values() if valid_source(row) and row.get('currency') == 'INR'
            and (row.get('mrp') is None or isinstance(row['mrp'], (int,float))
                 and not isinstance(row['mrp'],bool) and math.isfinite(row['mrp']) and row['mrp'] >= row['price'])]


def validate_images(rows):
    path = OUT/'image-checks.json'
    cache = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    old = json.loads((ROOT/'backend/data/myntra-1500/image-checks.json').read_text(encoding='utf-8'))
    for row in rows:
        identifier = row['product_id']
        if identifier not in cache and identifier in old and old[identifier].get('ok') and old[identifier].get('image_url') == row['image_url']:
            cache[identifier] = old[identifier]
    missing = [r for r in rows if r['product_id'] not in cache or cache[r['product_id']].get('image_url') != r['image_url']
               or cache[r['product_id']].get('error_type') in ('ReadTimeout','ConnectTimeout') and not cache[r['product_id']].get('retried')]
    print(json.dumps({'stage':'image_validation','candidates':len(rows),'checks_needed':len(missing)}),flush=True)
    with httpx.Client(verify=ssl.create_default_context(), timeout=httpx.Timeout(12,read=8,connect=8)) as c:
        with ThreadPoolExecutor(max_workers=12) as pool:
            futures = {pool.submit(myntra_probe.image_check,c,r):r for r in missing}
            for count, f in enumerate(as_completed(futures), 1):
                row = futures[f]; retried = row['product_id'] in cache
                cache[row['product_id']] = {**f.result(), 'retried':retried, 'image_url':row['image_url'], 'checked_at':datetime.now(timezone.utc).isoformat()}
                if count % 25 == 0:
                    write('image-checks.json',cache)
                    print(json.dumps({'stage':'image_validation','checked_new':count,'remaining':len(missing)-count}),flush=True)
    write('image-checks.json',cache)
    return [dict(row, image_validation=cache[row['product_id']]) for row in rows if cache[row['product_id']].get('ok')]


def export():
    # Only exact source ID/URL duplicates are removed. Distinct retailer offers remain
    # separate; similar garment names are not proof that two products are identical.
    rows = candidates()
    validated = validate_images(rows)
    selected, counts, urls = [], Counter(), set()
    for row in validated:
        if counts[row['retailer']] >= 2500 or row['product_url'] in urls: continue
        selected.append(row); counts[row['retailer']] += 1; urls.add(row['product_url'])
    write('catalog-products.json',selected)
    for retailer, slug in [('Myntra','myntra'),('AJIO','ajio'),('Nykaa Fashion','nykaa-fashion'),('SHEIN India','shein-india'),('H&M','hm-india')]:
        write(slug+'-products.json',[r for r in selected if r['retailer']==retailer])
    report = {'checked_at':datetime.now(timezone.utc).isoformat(),'products':len(selected),
              'retailers':dict(counts),'categories':dict(Counter(r['category'] for r in selected)),
              'brands':len({str(r['brand']).casefold() for r in selected}),
              'retailer_brands':{site:len({str(r['brand']).casefold() for r in selected if r['retailer']==site}) for site in counts},
              'price_bands':dict(Counter('under_1000' if r['price'] < 1000 else '1000_to_2499' if r['price'] < 2500 else '2500_and_above' for r in selected)),
              'candidate_records':len(rows),'images_passed':len(validated),'image_failures':len(rows)-len(validated),
              'deduplication':'Exact retailer-scoped ID and canonical URL; cross-store offers retained without guessing equivalence.',
              'prices':'Positive INR listing snapshots; coupon-only offers excluded. Current checkout prices not confirmed.',
              'unavailable_sources':['SHEIN India']}
    write('validation-summary.json',report)
    print(json.dumps(report,ensure_ascii=True),flush=True)


if __name__ == '__main__':
    export()
