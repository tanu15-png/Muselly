"""Collect a separate, resumable 1,500-product research catalog, never app data."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import shutil
import ssl
from urllib.parse import urlencode, urlparse

import httpx
from dotenv import dotenv_values
try:
    from . import myntra_probe as probe
except ImportError:
    import myntra_probe as probe

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'backend/data/myntra-1500'
CATEGORIES = [
    ('dresses', 'women-dresses', 'Dresses'), ('tops', 'women-tops', 'Tops'),
    ('shirts', 'women-shirts', 'Shirts'), ('tshirts', 'women-tshirts', 'Tshirts'),
    ('jeans', 'women-jeans', 'Jeans'), ('trousers', 'women-trousers', 'Trousers'),
    ('skirts', 'women-skirts', 'Skirts'), ('shorts', 'women-shorts', 'Shorts'),
    ('kurtas', 'women-kurtas', 'Kurtas'), ('kurta-sets', 'women-kurta-sets', 'Kurta Sets'),
    ('co-ords', 'women-co-ords', 'Co-Ords'), ('sweaters', 'women-sweaters', 'Sweaters'),
    ('sweatshirts', 'women-sweatshirts', 'Sweatshirts'), ('jackets', 'women-jackets', 'Jackets'),
    ('blazers', 'women-blazers', 'Blazers')]
# Targets total 100 per category. Extra candidates absorb ads, duplicates and bad images.
BANDS = [('budget', 200, 999, 50, 65), ('midrange', 1000, 2499, 30, 45),
         ('premium', 2500, 10000, 20, 35)]
STYLE_PATTERNS = {
    'floral': r'floral', 'striped': r'strip', 'checked': r'check|plaid', 'solid': r'solid',
    'printed': r'print', 'embroidered': r'embroider', 'ribbed': r'ribbed', 'lace': r'lace',
    'sequinned': r'sequin', 'satin': r'satin', 'denim': r'denim', 'cotton': r'cotton',
    'linen': r'linen', 'knitted': r'knit', 'velvet': r'velvet', 'leather': r'leather',
    'oversized': r'oversiz', 'relaxed': r'relaxed', 'fitted': r'fitted|slim fit',
    'wide leg': r'wide.leg', 'straight': r'straight', 'flared': r'flar', 'pleated': r'pleat',
    'a-line': r'a.line', 'bodycon': r'bodycon', 'wrap': r'wrap', 'anarkali': r'anarkali',
    'mini': r'\bmini\b', 'midi': r'\bmidi\b', 'maxi': r'\bmaxi\b',
    'formal': r'formal', 'casual': r'casual', 'cropped': r'crop', 'puff sleeve': r'puff',
    'sleeveless': r'sleeveless', 'ruffled': r'ruffl', 'ruched': r'ruch'}


def setup():
    OUT.mkdir(parents=True, exist_ok=True)
    probe.OUT = OUT


def jobs():
    return [{'id': f'{group}-{band}', 'group': group, 'slug': slug, 'category': category,
             'band': band, 'min_price': low, 'max_price': high, 'target': target, 'take': take}
            for group, slug, category in CATEGORIES for band, low, high, target, take in BANDS]


def source(job, alternative=False):
    params = {'f': 'Categories:' + job['category'],
              'rf': f'Price:{job["min_price"]}.0_{job["max_price"]}.0_{job["min_price"]}.0 TO {job["max_price"]}.0'}
    if alternative:
        params['sort'] = 'new'
    return job['slug'] + '?' + urlencode(params)


def normalized(raw, job):
    row = probe.normalize(raw, job['group'])
    if row['category'] != job['category'] and 'wrong_category' not in row['validation_errors']:
        row['validation_errors'].append('wrong_category')
    if 'invalid_price' not in row['validation_errors'] and not job['min_price'] <= row['price'] <= job['max_price']:
        row['validation_errors'].append('outside_price_band')
    mrp = row['mrp']
    if mrp is not None and (not isinstance(mrp, (int, float)) or isinstance(mrp, bool) or not math.isfinite(mrp) or 'invalid_price' not in row['validation_errors'] and mrp < row['price']):
        row['validation_errors'].append('invalid_mrp')
    parsed = urlparse(row['product_url'])
    if parsed.username or parsed.password or parsed.port not in (None, 443) or parsed.query or parsed.fragment:
        row['validation_errors'].append('noncanonical_product_link')
    description = str(raw.get('additionalInfo') or '')
    text = (str(row['name']) + ' ' + description).lower()
    row.update(price_band=job['band'], listing_description=description,
               listing_style_terms=[label for label, pattern in STYLE_PATTERNS.items() if re.search(pattern, text)],
               season=raw.get('season'), listing_rating=raw.get('rating'),
               product_link_status='structure_validated_live_access_not_checked')
    return row


def fetch(client, job, alternative=False):
    name = job['id'] + ('-new' if alternative else '')
    raw_path = OUT / (name + '-raw.json')
    if not raw_path.exists():
        try:
            probe.collect(client, name, source(job, alternative), job['take'])
        except RuntimeError:
            # A successful short result set is usable if it supplies enough valid candidates.
            status_path = OUT / (name + '-status.json')
            if not raw_path.exists() or not status_path.exists() or probe.read(name + '-status.json')['status'] != 'SUCCEEDED':
                raise
    raw = probe.read(name + '-raw.json')
    candidates = [normalized(row, job) for row in raw]
    return candidates


def balanced(candidates, count, used):
    remaining = {row['product_id']: row for row in candidates if not row['validation_errors'] and row['product_id'] not in used}
    selected, brands, colors, styles = [], Counter(), Counter(), Counter()
    while remaining and len(selected) < count:
        def score(row):
            return (6 / (1 + brands[row['brand']]) + 3 / (1 + colors[row['color']]) +
                    sum(1 / (1 + styles[term]) for term in row['listing_style_terms']) / max(1, len(row['listing_style_terms'])))
        row = max(remaining.values(), key=score)
        selected.append(row); del remaining[row['product_id']]
        brands[row['brand']] += 1; colors[row['color']] += 1; styles.update(row['listing_style_terms'])
    return selected


def checked_selection(client, job, candidates, cache, used):
    selected = []
    excluded = set(used)
    for _ in range(3):
        picks = balanced(candidates, job['target'] - len(selected), excluded)
        if not picks: break
        pending = [row for row in picks if not cache.get(row['product_id'], {}).get('ok') or cache[row['product_id']].get('image_url') != row['image_url']]
        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = {pool.submit(probe.image_check, client, row): row for row in pending}
            for future in as_completed(futures):
                row = futures[future]
                cache[row['product_id']] = {**future.result(), 'image_url': row['image_url'],
                                          'checked_at': datetime.now(timezone.utc).isoformat()}
        probe.write('image-checks.json', cache)
        for row in picks:
            excluded.add(row['product_id'])
            if cache[row['product_id']]['ok']:
                row['image_validation'] = {k: cache[row['product_id']][k] for k in ('width', 'height', 'checked_at')}
                selected.append(row)
        if len(selected) == job['target']: break
    return selected


def export(rows):
    assert len(rows) == len({row['product_id'] for row in rows}) == 1500
    assert all(not row['validation_errors'] for row in rows)
    assert Counter(row['category'] for row in rows) == Counter({category: 100 for _, _, category in CATEGORIES})
    probe.write('catalog-products.json', rows)
    fields = ['product_id', 'name', 'brand', 'price', 'currency', 'mrp', 'price_band', 'category',
              'gender', 'color', 'listing_description', 'listing_style_terms', 'image_url', 'product_url',
              'listed_sizes', 'available_sizes_observed', 'stock_status', 'collected_at', 'price_status', 'product_link_status']
    with (OUT / 'catalog-products.csv').open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction='ignore'); writer.writeheader()
        for row in rows:
            flat = dict(row)
            for key in fields:
                if isinstance(flat.get(key), list): flat[key] = ' | '.join(map(str, flat[key]))
                if isinstance(flat.get(key), str) and flat[key].startswith(('=', '+', '-', '@')): flat[key] = "'" + flat[key]
            writer.writerow(flat)
    report = {'checked_at': datetime.now(timezone.utc).isoformat(), 'products': len(rows),
              'unique_products': len({row['product_id'] for row in rows}), 'categories': dict(Counter(row['category'] for row in rows)),
              'price_bands': dict(Counter(row['price_band'] for row in rows)), 'brands': len({row['brand'] for row in rows}),
              'colors': len({row['color'] for row in rows}), 'minimum_price_inr': min(row['price'] for row in rows),
              'maximum_price_inr': max(row['price'] for row in rows),
              'listing_style_terms': dict(Counter(term for row in rows for term in row['listing_style_terms'])),
              'images_decoded': len(rows), 'product_url_structure_valid': len(rows),
              'price_validation': 'Finite positive INR listing price, within requested band, not above supplied MRP. Checkout price not independently verified.',
              'style_provenance': 'Keywords explicitly present in listing name/description; not AI-verified visual attributes.',
              'stock_scope': 'Only explicit inventory evidence; size names alone do not imply availability.',
              'reported_run_charges_usd': round(sum(probe.read(path.name).get('usageTotalUsd', 0) for path in OUT.glob('*-status.json')), 6)}
    probe.write('validation-summary.json', report)
    print(json.dumps(report), flush=True)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--export-only', action='store_true'); args = parser.parse_args()
    setup()
    if args.export_only:
        export(probe.read('selected-products.json')); return
    token = dotenv_values(ROOT / 'backend/.env').get('APIFY_API_TOKEN')
    if not token: raise SystemExit('APIFY_API_TOKEN missing from backend/.env.')
    cache = probe.read('image-checks.json') if (OUT / 'image-checks.json').exists() else {}
    all_jobs = jobs()
    probe.write('collection-plan.json', {'target': 1500, 'jobs': all_jobs, 'max_actor_charge_per_run_usd': .10})
    # Seed the premium dress batch with the successful price-filter probe.
    old = ROOT / 'backend/data/myntra-verification'
    for suffix in ('run', 'status', 'raw'):
        src, dst = old / f'expand-dresses-premium-probe-{suffix}.json', OUT / f'dresses-premium-{suffix}.json'
        if src.exists() and not dst.exists(): shutil.copyfile(src, dst)
    rows, used = [], set()
    with httpx.Client(base_url='https://api.apify.com', verify=ssl.create_default_context(),
                      headers={'Authorization': 'Bearer ' + token}, timeout=35) as api:
        # Two independent category batches at a time stay below the Free plan concurrency limit.
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = {pool.submit(fetch, api, job): job for job in all_jobs}
            for future in as_completed(futures):
                job = futures[future]; candidates = future.result()
                good = sum(not row['validation_errors'] for row in candidates)
                print(json.dumps({'batch': job['id'], 'candidates': len(candidates), 'eligible': good, 'target': job['target']}), flush=True)
    with httpx.Client(verify=ssl.create_default_context(), timeout=15, follow_redirects=False) as image_client:
        with httpx.Client(base_url='https://api.apify.com', verify=ssl.create_default_context(),
                          headers={'Authorization': 'Bearer ' + token}, timeout=35) as api:
            for job in all_jobs:
                candidates = fetch(api, job)
                selected = checked_selection(image_client, job, candidates, cache, used)
                if len(selected) < job['target']:
                    candidates.extend(fetch(api, job, alternative=True))
                    selected = checked_selection(image_client, job, candidates, cache, used)
                if len(selected) < job['target']:
                    probe.write('partial-products.json', rows + selected)
                    raise SystemExit(f'{job["id"]} supplied only {len(selected)} verified products; target {job["target"]}. Stopped without publishing incomplete catalog.')
                rows.extend(selected); used.update(row['product_id'] for row in selected)
                probe.write('selected-products.json', rows)
                print(json.dumps({'verified_batch': job['id'], 'accepted': len(selected), 'total': len(rows)}), flush=True)
    export(rows)


if __name__ == '__main__':
    main()
