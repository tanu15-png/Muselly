"""Conservative independent reachability sample; does not bypass Myntra access controls."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import ssl

import httpx

OUT = Path(__file__).resolve().parents[1] / 'data/myntra-1500'


def check(client, row):
    result = {'product_id': row['product_id'], 'category': row['category'],
              'url': row['product_url'], 'checked_at': datetime.now(timezone.utc).isoformat()}
    try:
        # HEAD avoids downloading retailer pages or using proxy/access-control workarounds.
        response = client.head(row['product_url'])
        result.update(http_status=response.status_code,
                      status='reachable_headers_only' if response.status_code == 200 else 'not_confirmed')
        if 300 <= response.status_code < 400:
            result['redirect_location'] = response.headers.get('location')
    except httpx.RequestError as failure:
        result.update(status='not_confirmed', error_type=type(failure).__name__)
    return result


def main():
    rows = json.loads((OUT / 'catalog-products.json').read_text(encoding='utf-8'))
    seen, sample = set(), []
    for row in rows:
        if row['category'] not in seen:
            seen.add(row['category']); sample.append(row)
    with httpx.Client(verify=ssl.create_default_context(), timeout=6, follow_redirects=False) as client:
        with ThreadPoolExecutor(max_workers=3) as pool:
            checks = list(pool.map(lambda row: check(client, row), sample))
    report = {'checked_at': datetime.now(timezone.utc).isoformat(), 'catalog_url_structure_checks': len(rows),
              'independent_http_sample_size': len(checks),
              'sample_http_200': sum(row.get('http_status') == 200 for row in checks),
              'checks': checks,
              'scope': 'One ordinary HEAD request per category; no redirect following, retries or access-control bypass. HTTP 200 confirms headers only, not product identity, price, stock or checkout.'}
    (OUT / 'link-reachability.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'link_sample': len(checks), 'http_200': report['sample_http_200'],
                      'not_confirmed': len(checks) - report['sample_http_200']}), flush=True)


if __name__ == '__main__':
    main()
