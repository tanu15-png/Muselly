from tools.myntra_expand import balanced, jobs, normalized, source


def raw(product_id='123', **extra):
    return {'productId': product_id, 'name': 'Floral cotton A-line dress', 'brand': 'Example',
            'price': 799, 'mrp': 1299, 'category': 'Dresses', 'gender': 'Women',
            'imageUrl': 'https://assets.myntassets.com/example.jpg',
            'productUrl': f'https://www.myntra.com/dresses/example/{product_id}/buy',
            'scrapedAt': '2026-10-25T09:00:00Z', **extra}


def test_plan_has_exact_category_and_price_band_quotas():
    plan = jobs()
    assert len(plan) == 45 and sum(job['target'] for job in plan) == 1500
    assert sum(job['target'] for job in plan if job['band'] == 'budget') == 750
    assert len({job['category'] for job in plan}) == 15
    assert 'Categories%3ADresses' in source(plan[0]) and 'rf=' in source(plan[0])


def test_filtering_checks_actual_price_even_when_search_promises_a_band():
    job = jobs()[2]  # premium dresses
    assert 'outside_price_band' in normalized(raw(), job)['validation_errors']
    row = normalized(raw(price=2999, mrp=3999), job)
    assert row['validation_errors'] == []
    assert {'floral', 'cotton', 'a-line'} <= set(row['listing_style_terms'])
    assert row['price_status'] == 'listing_snapshot'


def test_exact_category_and_mrp_validation():
    job = jobs()[0]
    assert 'wrong_category' in normalized(raw(category='Tops'), job)['validation_errors']
    assert 'invalid_mrp' in normalized(raw(mrp=500), job)['validation_errors']
    assert 'invalid_price' in normalized(raw(price='799'), job)['validation_errors']


def test_balancing_excludes_invalid_and_already_used_products_and_diversifies_brands():
    job = jobs()[0]
    candidates = [normalized(raw(str(i), brand='Same' if i < 4 else 'Different'), job) for i in range(1, 6)]
    candidates += [normalized(raw('9', price=9999), job)]
    picks = balanced(candidates, 3, {'1'})
    assert len(picks) == 3 and len({row['product_id'] for row in picks}) == 3
    assert not {'1', '9'} & {row['product_id'] for row in picks}
    assert {row['brand'] for row in picks} == {'Same', 'Different'}
