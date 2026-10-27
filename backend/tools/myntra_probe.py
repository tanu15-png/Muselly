"""Offline hackathon catalog verification. No application or shopping integration.

Run from the repository root with backend/.venv-win/Scripts/python.exe.
Token stays in backend/.env; only product data and run IDs are written to data/.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from io import BytesIO
import json
import math
from pathlib import Path
import ssl
import time
from urllib.parse import urlparse

import httpx
from dotenv import dotenv_values
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'backend/data/myntra-verification'
ACTOR = 'shahidirfan~myntra-product-scraper'
GROUPS = [('dresses', 'women-dresses', 40), ('tops-filtered', 'women-tops?f=Categories%3ATops', 40),
          ('trousers', 'women-trousers', 30), ('kurtas', 'women-kurtas', 30),
          ('co-ords', 'women-co-ords', 30), ('jackets', 'women-jackets', 30)]


def write(name, value):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')
    temporary.replace(path)


def read(name):
    return json.loads((OUT / name).read_text(encoding='utf-8'))


def normalize(raw, group):
    group = group.removesuffix('-filtered')
    product_id = str(raw.get('productId') or '')
    price = raw.get('price')
    url = raw.get('productUrl') or ''
    parsed = urlparse(url)
    image = raw.get('imageUrl') or raw.get('searchImage') or ''
    if image.startswith('http://assets.myntassets.com/'):
        image = 'https://' + image.removeprefix('http://')
    picture = urlparse(image)
    errors = []
    if not product_id.isdigit(): errors.append('invalid_product_id')
    if not isinstance(price, (int, float)) or isinstance(price, bool) or not math.isfinite(price) or price <= 0: errors.append('invalid_price')
    if parsed.scheme != 'https' or parsed.hostname not in ('www.myntra.com', 'myntra.com') or not parsed.path.endswith(f'/{product_id}/buy'): errors.append('invalid_product_link')
    if picture.scheme != 'https' or picture.hostname != 'assets.myntassets.com': errors.append('invalid_image_link')
    if str(raw.get('gender', '')).lower() != 'women': errors.append('not_womens_product')
    expected = {'dresses': 'Dresses', 'tops': 'Tops', 'trousers': 'Trousers', 'kurtas': 'Kurtas', 'co-ords': 'Co-Ords', 'jackets': 'Jackets'}
    if group in expected and raw.get('category') != expected[group]: errors.append('wrong_category')
    if not raw.get('name') or not raw.get('brand') or not raw.get('scrapedAt'): errors.append('missing_metadata')
    # Listing-level size names are not evidence of availability for every size.
    inventory = raw.get('inventoryInfo') or []
    if not isinstance(inventory, list): inventory = []
    available = sorted({str(row.get('label')) for row in inventory if isinstance(row, dict)
                        and row.get('label') and (row.get('available') is True or row.get('available') is None and
                        isinstance(row.get('inventory'), (int, float)) and row['inventory'] > 0)})
    return {'product_id': product_id, 'name': raw.get('name'), 'brand': raw.get('brand'),
            'price': price, 'currency': 'INR', 'mrp': raw.get('mrp'), 'product_url': url,
            'image_url': image, 'gender': raw.get('gender'), 'color': raw.get('primaryColour'),
            'category': raw.get('category'), 'catalog_group': group, 'listed_sizes': raw.get('sizes') or [],
            'available_sizes_observed': available, 'stock_status': 'available_in_listing' if available else 'unknown',
            'collector_stock_flag': raw.get('inStock'), 'collected_at': raw.get('scrapedAt'),
            'source_url': raw.get('sourceUrl'), 'price_status': 'listing_snapshot',
            'validation_errors': errors}


def image_check(client, row):
    try:
        deadline = time.monotonic() + 25
        with client.stream('GET', row['image_url']) as response:
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_bytes():
                if time.monotonic() > deadline: raise TimeoutError('image_download_deadline')
                size += len(chunk)
                if size > 8_000_000: raise ValueError('image_too_large')
                chunks.append(chunk)
        with Image.open(BytesIO(b''.join(chunks))) as image:
            width, height = image.size
            image.verify()
        return {'product_id': row['product_id'], 'ok': width > 0 and height > 0, 'width': width, 'height': height}
    except Exception as failure:
        return {'product_id': row['product_id'], 'ok': False, 'error_type': type(failure).__name__}


def validate(rows, prefix):
    ids = [row['product_id'] for row in rows]
    with httpx.Client(verify=ssl.create_default_context(), timeout=20, follow_redirects=False) as client:
        with ThreadPoolExecutor(max_workers=4) as pool:
            checks = list(pool.map(lambda row: image_check(client, row), rows))
    good = {row['product_id'] for row in checks if row['ok']}
    valid = [row for row in rows if not row['validation_errors'] and row['product_id'] in good]
    report = {'checked_at': datetime.now(timezone.utc).isoformat(), 'records': len(rows),
              'unique_products': len(set(ids)), 'valid_products': len(valid),
              'image_successes': len(good), 'image_failures': [row for row in checks if not row['ok']],
              'invalid_records': [{'product_id': row['product_id'], 'errors': row['validation_errors']} for row in rows if row['validation_errors']],
              'stock_flag_conflicts': sum(row['collector_stock_flag'] is False and bool(row['available_sizes_observed']) for row in rows),
              'price_verification': 'Fresh collector listing snapshots; not independently confirmed checkout prices.',
              'availability_scope': 'Only inventory entries returned by listing; other sizes and postcode delivery are unknown.'}
    write(prefix + '-image-checks.json', checks)
    write(prefix + '-validation.json', report)
    write(prefix + '-products.json', valid)
    print(json.dumps(report), flush=True)
    return report


def collect(client, name, slug, count):
    record_path = OUT / (name + '-run.json')
    if record_path.exists():
        run = read(name + '-run.json')
    else:
        payload = {'startUrls': [{'url': 'https://www.myntra.com/' + slug}], 'results_wanted': count,
                   'proxyConfiguration': {'useApifyProxy': True, 'apifyProxyGroups': ['RESIDENTIAL'], 'apifyProxyCountry': 'IN'}}
        response = client.post(f'/v2/acts/{ACTOR}/runs', params={'timeout': 180, 'maxTotalChargeUsd': .10}, json=payload)
        if response.status_code not in (200, 201):
            raise RuntimeError(f'Actor start failed: HTTP {response.status_code}; not retried to prevent duplicate charges.')
        data = response.json()['data']
        run = {'id': data['id'], 'dataset_id': data['defaultDatasetId'], 'input': payload, 'max_charge_usd': .10}
        write(name + '-run.json', run)
    for _ in range(45):
        response = client.get('/v2/actor-runs/' + run['id'], params={'waitForFinish': 15})
        response.raise_for_status()
        status = response.json()['data']
        write(name + '-status.json', status)
        if status['status'] in ('SUCCEEDED', 'FAILED', 'ABORTED', 'TIMED-OUT'):
            break
        time.sleep(2)
    else:
        raise RuntimeError('Actor still running. Re-run to resume polling; no duplicate run will be created.')
    result = client.get('/v2/datasets/' + run['dataset_id'] + '/items', params={'clean': 'true', 'format': 'json', 'limit': count + 10})
    result.raise_for_status()
    rows = result.json()
    write(name + '-raw.json', rows)
    print(json.dumps({'group': name, 'status': status['status'], 'records': len(rows), 'reported_charge_usd': status.get('usageTotalUsd')}), flush=True)
    if status['status'] != 'SUCCEEDED' or len(rows) != count:
        raise RuntimeError(f'{name} did not return the requested {count} products; collection paused.')
    return [normalize(row, name) for row in rows]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['validate-pilot', 'collect-200'])
    args = parser.parse_args()
    if args.phase == 'validate-pilot':
        report = validate([normalize(row, 'dresses') for row in read('pilot-raw.json')], 'pilot')
        if report['valid_products'] != 20 or report['unique_products'] != 20: raise SystemExit(1)
        return
    report = read('pilot-validation.json')
    if report['valid_products'] != 20 or report['unique_products'] != 20:
        raise SystemExit('The 20-product pilot must pass first.')
    token = dotenv_values(ROOT / 'backend/.env').get('APIFY_API_TOKEN')
    if not token: raise SystemExit('APIFY_API_TOKEN is missing from backend/.env.')
    rows = []
    with httpx.Client(base_url='https://api.apify.com', verify=ssl.create_default_context(),
                      headers={'Authorization': 'Bearer ' + token}, timeout=35) as client:
        for name, slug, count in GROUPS:
            rows.extend(collect(client, name, slug, count))
    if len({row['product_id'] for row in rows}) != 200:
        write('catalog-candidates.json', rows)
        raise SystemExit('Duplicate products found across categories; catalog not accepted.')
    report = validate(rows, 'catalog')
    if report['valid_products'] != 200: raise SystemExit('Catalog contains invalid records; see catalog-validation.json.')


if __name__ == '__main__':
    main()
