"""Public, tokenless Shopify Storefront queries for a fixed set of verified shops."""
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeout
from copy import deepcopy
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
from threading import Lock
from time import monotonic
from urllib.parse import quote, urlencode, urlsplit
import xml.etree.ElementTree as ET

import httpx

SOURCES = json.loads((Path(__file__).resolve().parents[2] / 'shared/shopping-sources.json').read_text())
BY_ID = {s['id']: s for s in SOURCES}
SHOPIFY_VERSION = '2026-10'
ECB_URL = 'https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml'
QUERY = """query MusellyProducts($query: String!) {
  search(first: 12, query: $query, types: [PRODUCT], unavailableProducts: HIDE) {
    pageInfo { hasNextPage }
    nodes { ... on Product {
      id title handle vendor availableForSale productType description
      featuredImage { url altText }
      variants(first: 32) {
        nodes { id title availableForSale selectedOptions { name value } price { amount currencyCode } }
        pageInfo { hasNextPage }
      }
    } }
  }
}"""


class CatalogError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message
        super().__init__(message)


def amount(value):
    try:
        result = Decimal(str(value))
        if not result.is_finite() or result < 0 or result > 100000000:
            raise ValueError()
        return result
    except (InvalidOperation, TypeError, ValueError):
        raise CatalogError('invalid_response', 'The store returned an invalid price.') from None


def public_image(value):
    if not isinstance(value, str) or len(value) > 2048:
        return None
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    host = (parsed.hostname or '').lower()
    if parsed.scheme == 'https' and not parsed.username and not parsed.password and (host == 'cdn.shopify.com' or host.endswith('.shopify.com') or host.endswith('.shopifycdn.com')):
        return value
    return None


def normalize_product(node, source):
    try:
        if not isinstance(node, dict) or not node.get('availableForSale'):
            return None
        handle, title = node['handle'], node['title']
        if not isinstance(title, str) or not title.strip() or len(title) > 500:
            return None
        if not isinstance(handle, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,200}', handle):
            return None
        product_id = node['id'].removeprefix('gid://shopify/Product/')
        if not product_id.isdigit():
            return None
        variants = []
        rows = node['variants']['nodes']
        if not isinstance(rows, list) or len(rows) > 32:
            return None
        for row in rows:
            if row.get('availableForSale') is not True:
                continue
            id = row['id'].removeprefix('gid://shopify/ProductVariant/')
            money = row['price']
            if not id.isdigit() or money['currencyCode'] not in ('USD', 'INR', 'EUR', 'GBP', 'CAD', 'AUD'):
                continue
            options = row.get('selectedOptions', [])
            if not isinstance(options, list):
                continue
            selected = {o['name'].strip().casefold(): o['value'].strip() for o in options
                        if isinstance(o, dict) and isinstance(o.get('name'), str) and isinstance(o.get('value'), str)}
            variants.append({'id': id, 'price': amount(money['amount']), 'currency': money['currencyCode'], 'options': selected})
        if not variants:
            return None
        image = node.get('featuredImage') or {}
        image_url = public_image(image.get('url'))
        if not image_url:
            return None  # A product card needs an actual store-supplied image.
        return {'id': source['id'] + ':' + product_id, 'title': title.strip(),
                'brand': str(node.get('vendor') or source['name'])[:200],
                'product_type': str(node.get('productType') or '')[:200],
                'description': str(node.get('description') or '')[:6000],
                'url': source['website'] + '/products/' + quote(handle, safe=''),
                'image': image_url, 'variants': variants,
                'variants_truncated': bool(node['variants'].get('pageInfo', {}).get('hasNextPage')),
                'source_id': source['id'], 'source_name': source['name'],
                'qloo_entity_id': source['qloo_entity_id']}
    except (KeyError, TypeError, AttributeError, CatalogError):
        return None


def external_search(source, query):
    if 'query_slug' in source.get('search_path', ''):
        slug = re.sub(r'[^\w-]+', '-', query.casefold()).strip('-') or 'clothing'
        return source['website'] + source['search_path'].replace('{query_slug}', quote(slug, safe=''))
    params = {source['query_key']: query, **source.get('extra_query', {})}
    return source['website'] + source['search_path'] + '?' + urlencode(params)


class ProductCatalog:
    def __init__(self, client):
        self.client = client
        self.pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix='muselly-catalog')
        self.lock = Lock()
        self.cache = OrderedDict()
        self.exchange = None

    def close(self):
        self.pool.shutdown(wait=False, cancel_futures=True)

    def search_store(self, source, query):
        key = (source['id'], SHOPIFY_VERSION, query)
        with self.lock:
            cached = self.cache.get(key)
            if cached and cached[0] > monotonic():
                self.cache.move_to_end(key)
                return deepcopy(cached[1])
        try:
            response = self.client.post('https://' + source['shop'] + '/api/' + SHOPIFY_VERSION + '/graphql.json',
                json={'query': QUERY, 'variables': {'query': query}}, timeout=10)
        except httpx.RequestError:
            raise CatalogError('unavailable', 'The store could not be reached. Please retry.') from None
        if response.status_code == 429:
            raise CatalogError('rate_limited', 'The store is busy. Please try again shortly.')
        if not response.is_success:
            raise CatalogError('unavailable', 'The store is temporarily unavailable.')
        try:
            if len(response.content) > 2000000:
                raise ValueError()
            data = response.json()
            if data.get('errors'):
                raise ValueError()
            nodes = data['data']['search']['nodes']
            if not isinstance(nodes, list) or len(nodes) > 12:
                raise ValueError()
        except (ValueError, KeyError, TypeError, AttributeError):
            raise CatalogError('invalid_response', 'The store could not provide product results.') from None
        products = [product for node in nodes if (product := normalize_product(node, source))]
        result = {'products': products, 'has_more': bool(data['data']['search'].get('pageInfo', {}).get('hasNextPage')),
                  'fetched_at': datetime.now(timezone.utc).isoformat()}
        with self.lock:
            self.cache[key] = (monotonic() + 300, deepcopy(result))
            self.cache.move_to_end(key)
            while len(self.cache) > 128:
                self.cache.popitem(last=False)
        return result

    def search(self, sources, query):
        futures = {self.pool.submit(self.search_store, source, query): source for source in sources}
        products, statuses = [], []
        finished = set()
        try:
            for future in as_completed(futures, timeout=15):
                finished.add(future)
                source = futures[future]
                try:
                    result = future.result()
                    products.extend({**p, 'fetched_at': result['fetched_at']} for p in result['products'])
                    statuses.append({'id': source['id'], 'name': source['name'], 'status': 'ok', 'count': len(result['products']), 'has_more': result['has_more'], 'fetched_at': result['fetched_at']})
                except CatalogError as failure:
                    statuses.append({'id': source['id'], 'name': source['name'], 'status': failure.status, 'message': failure.message})
        except FuturesTimeout:
            pass
        for future, source in futures.items():
            if future not in finished:
                future.cancel()
                statuses.append({'id': source['id'], 'name': source['name'], 'status': 'timeout', 'message': 'The store took too long. Please retry.'})
        return products, sorted(statuses, key=lambda s: s['id'])

    def rates(self):
        with self.lock:
            if self.exchange and self.exchange[0] > monotonic():
                return self.exchange[1]
        try:
            response = self.client.get(ECB_URL, timeout=8)
            response.raise_for_status()
            if len(response.content) > 50000:
                raise ValueError()
            root = ET.fromstring(response.content)
            values = {'EUR': Decimal('1')}
            rate_date = None
            for item in root.iter():
                if 'time' in item.attrib:
                    rate_date = date.fromisoformat(item.attrib['time'])
                if 'currency' in item.attrib:
                    rate = Decimal(item.attrib['rate'])
                    if not rate.is_finite() or rate <= 0:
                        raise ValueError()
                    values[item.attrib['currency']] = rate
            age = (datetime.now(timezone.utc).date() - rate_date).days if rate_date else 999
            if age < 0 or age > 7 or not {'USD', 'INR'} <= values.keys():
                raise ValueError()
            result = {'rates': values, 'date': rate_date.isoformat(), 'source': 'ECB'}
            with self.lock:
                self.exchange = (monotonic() + 21600, result)
            return result
        except (httpx.HTTPError, ET.ParseError, ValueError, KeyError, InvalidOperation, TypeError):
            raise CatalogError('currency_unavailable', 'Currency conversion is temporarily unavailable. Choose the store currency (USD) or try again later.') from None
