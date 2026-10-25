from copy import deepcopy

from tools.myntra_probe import normalize


def product():
    return {'productId': '123', 'name': 'Floral dress', 'brand': 'Example', 'price': 799, 'mrp': 1299,
            'productUrl': 'https://www.myntra.com/dresses/example/floral/123/buy',
            'imageUrl': 'http://assets.myntassets.com/assets/image.jpg', 'gender': 'Women',
            'category': 'Dresses', 'scrapedAt': '2026-10-25T09:00:00Z', 'sizes': ['S', 'M'],
            'inStock': False, 'inventoryInfo': [{'label': 'S', 'available': True, 'inventory': 5}]}


def test_snapshot_normalizes_https_and_uses_inventory_evidence():
    raw = product()
    original = deepcopy(raw)
    row = normalize(raw, 'dresses')
    assert row['validation_errors'] == []
    assert row['image_url'].startswith('https://assets.myntassets.com/')
    assert row['stock_status'] == 'available_in_listing'
    assert row['available_sizes_observed'] == ['S']
    assert row['collector_stock_flag'] is False
    assert row['listed_sizes'] == ['S', 'M']
    assert raw == original


def test_size_names_without_inventory_do_not_imply_stock():
    raw = product(); raw.pop('inventoryInfo')
    row = normalize(raw, 'dresses')
    assert row['available_sizes_observed'] == [] and row['stock_status'] == 'unknown'


def test_explicit_unavailable_size_is_not_claimed_available():
    raw = product(); raw['inventoryInfo'][0]['available'] = False
    assert normalize(raw, 'dresses')['available_sizes_observed'] == []


def test_rejects_wrong_gender_category_and_untrusted_links():
    raw = product(); raw.update(gender='Kids', category='Thermal Tops',
        productUrl='https://www.myntra.com.evil.example/123/buy', imageUrl='https://example.com/image.jpg')
    assert set(normalize(raw, 'dresses')['validation_errors']) == {
        'not_womens_product', 'wrong_category', 'invalid_product_link', 'invalid_image_link'}


def test_rejects_non_numeric_or_nonfinite_prices():
    for price in [True, 0, -1, '799', float('nan'), float('inf')]:
        raw = product(); raw['price'] = price
        assert 'invalid_price' in normalize(raw, 'dresses')['validation_errors']
