import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CulturalFeedback, InspirationImage, TasteAnalysisRun
from test_api import database, headers, USER_A
from test_onboarding import client
from test_enrichment import saved_profile


def products():
    data = [('101', 'Cream floral A-line midi dress', 'Dresses', 'Cream', 'CultureBrand', 900),
            ('102', 'Red solid bodycon dress', 'Dresses', 'Red', 'Other', 800),
            ('103', 'Blue formal cotton shirt', 'Shirts', 'Blue', 'Other', 1200),
            ('104', 'Cream floral midi dress', 'Dresses', 'Cream', 'Other', 4000)]
    return [{'product_id': id, 'name': name, 'brand': brand, 'category': category, 'color': color,
             'gender': 'Women', 'price': price, 'mrp': price + 500, 'currency': 'INR',
             'product_url': f'https://www.myntra.com/clothing/brand/name/{id}/buy',
             'image_url': f'https://assets.myntassets.com/{id}.jpg', 'collected_at': '2026-10-25T09:00:00Z',
             'listing_style_terms': ['floral'] if color == 'Cream' else ['solid']} for id, name, category, color, brand, price in data]


def setup(client, tmp_path):
    path = tmp_path / 'catalog.json'; path.write_text(json.dumps(products()), encoding='utf-8')
    client.app.state.settings.myntra_catalog_path = str(path)


def search(client, query='dress under 1500', token='user-a', **extra):
    return client.post('/api/shop/search', headers=headers(token), json={'query': query, **extra})


def test_budget_category_color_and_negative_constraints_are_hard_filters(client, tmp_path):
    from app.myntra_shopping import intent
    setup(client, tmp_path)
    assert [p['product_id'] for p in search(client, 'floral midi dress under ₹1000').json()['products']] == ['101']
    assert [p['product_id'] for p in search(client, 'dress under 1000 without red').json()['products']] == ['101']
    assert [p['product_id'] for p in search(client, 'red dress under 1000').json()['products']] == ['102']
    assert search(client, 'men shirts under 2000').json()['products'] == []
    assert search(client, 'kids dress').json()['products'] == []
    assert search(client, 'dress under $100').status_code == 422
    assert client.post('/api/shop/search', json={'query': 'dress'}).status_code == 401
    assert intent('t-shirts, my budget is 2k')['categories'] == ['Tshirts']
    assert intent('t-shirts, my budget is 2k')['max_price'] == 2000
    assert intent('an outfit within 1500')['max_price'] == 1500


def test_feedback_persists_is_private_and_only_accepts_real_catalog_ids(client, tmp_path):
    setup(client, tmp_path)
    assert client.post('/api/shop/feedback', headers=headers(), json={'product_id': '999', 'choice': 'like'}).status_code == 404
    assert client.post('/api/shop/feedback', headers=headers(), json={'product_id': '102', 'choice': 'dislike'}).status_code == 200
    assert '102' not in [p['product_id'] for p in search(client).json()['products']]
    assert client.get('/api/shop/feedback', headers=headers()).json()['choices'] == {'102': 'dislike'}
    assert client.get('/api/shop/feedback', headers=headers('user-b')).json()['choices'] == {}
    assert client.post('/api/shop/feedback', headers=headers(), json={'product_id': '101', 'choice': 'like'}).status_code == 200
    assert [p['product_id'] for p in search(client, liked_only=True).json()['products']] == ['101']
    assert client.post('/api/shop/feedback', headers=headers(), json={'product_id': '102', 'choice': 'clear'}).status_code == 200
    assert '102' in [p['product_id'] for p in search(client).json()['products']]


def seed_cultural_link(client, database):
    saved_profile(client)
    with Session(database[0]) as db:
        image = db.scalar(select(InspirationImage).where(InspirationImage.user_id == UUID(USER_A)))
        entity_id = uuid4()
        db.add(CulturalFeedback(user_id=UUID(USER_A), entity_id=entity_id,
            entity={'entity_id': str(entity_id), 'name': 'Little Women', 'domain': 'movie'}, preference='like',
            fashion_inspiration=True, reference_image_ids=[str(image.id)]))
        db.add(TasteAnalysisRun(id=uuid4(), user_id=UUID(USER_A), source_hash='fixture', model='fixture',
            prompt_version='fixture', status='succeeded', sources={'images': [{'id': str(image.id), 'updated_at': image.updated_at.isoformat()}]},
            result={'images': [{'image_id': str(image.id), 'colors': ['Cream'], 'patterns': ['Floral print'], 'silhouettes': ['A-line']}]},
            created_at=datetime.now(timezone.utc)))
        db.commit()
    return str(entity_id)


def test_qloo_connections_and_confirmed_looks_change_rank_with_traceable_reasons(client, database, tmp_path):
    setup(client, tmp_path)
    seed = seed_cultural_link(client, database)
    calls = []
    class Qloo:
        def get(self, settings, path, params, **kwargs):
            calls.append(params)
            return [{'entity_id': str(uuid4()), 'name': 'CultureBrand', 'type': 'urn:entity:brand'}]
    client.app.state.qloo = Qloo()
    result = search(client).json()
    assert result['products'][0]['product_id'] == '101'
    assert result['taste'] == {'qloo_status': 'ready', 'qloo_brands': 1, 'linked_discoveries': 1}
    assert calls[0]['signal.interests.entities'] == seed
    assert result['products'][0]['connections'][0]['name'] == 'Little Women'
    assert 'floral' in result['products'][0]['connections'][0]['matched_attributes']
    assert any('Qloo' in reason for reason in result['products'][0]['why'])
    other = search(client, token='user-b').json()
    assert other['taste']['linked_discoveries'] == 0 and other['products'][0]['product_id'] == '102'
    assert len(calls) == 1


def test_qloo_outage_retains_linked_visual_ranking_but_deleted_images_do_not(client, database, tmp_path):
    from fastapi import HTTPException
    setup(client, tmp_path); seed_cultural_link(client, database)
    class Qloo:
        def get(self, *args, **kwargs): raise HTTPException(503, 'Unavailable')
    client.app.state.qloo = Qloo()
    result = search(client).json()
    assert result['taste']['qloo_status'] == 'unavailable'
    assert result['products'][0]['product_id'] == '101' and result['products'][0]['connections']
    with Session(database[0]) as db:
        db.delete(db.scalar(select(InspirationImage).where(InspirationImage.user_id == UUID(USER_A)))); db.commit()
    result = search(client).json()
    assert result['taste']['linked_discoveries'] == 0
    assert all(not row['connections'] for row in result['products'])


def test_missing_catalog_fails_cleanly(client, tmp_path):
    client.app.state.settings.myntra_catalog_path = str(tmp_path / 'missing.json')
    assert search(client).status_code == 503


def test_fashion_note_is_private_persistent_and_changes_ranking(client, database, tmp_path):
    setup(client, tmp_path)
    seed = seed_cultural_link(client, database)
    url = f'/api/onboarding/culture/feedback/{seed}/fashion-note'
    assert client.patch(url, headers=headers('user-b'), json={'note': 'Red'}).status_code == 404
    assert client.patch(url, headers=headers(), json={'note': 'x' * 501}).status_code == 422
    assert client.patch(url, headers=headers(), json={'note': 'Red solid bodycon, without floral'}).status_code == 200
    with Session(database[0]) as db:
        row = db.get(CulturalFeedback, (UUID(USER_A), UUID(seed)))
        assert row.fashion_note == 'Red solid bodycon, without floral'
        assert row.preference == 'like' and row.reference_image_ids
    result = search(client).json()['products']
    assert result[0]['product_id'] == '102'
    assert any('fashion note' in reason for reason in result[0]['why'])
    assert search(client, 'cream floral dress under 1000').json()['products'][0]['product_id'] == '101'
    assert client.patch(url, headers=headers(), json={'note': ''}).status_code == 200


def test_taste_percentage_uses_evidence_not_price_or_relative_position():
    from app.myntra_shopping import taste_match, rank_catalog, intent
    rows = products()
    bridges = [{'name': 'A saved film', 'entity_id': 'film', 'labels': ['cream', 'floral'], 'image_ids': []}]
    assert taste_match(rows[0], [], {}, [], []) is None
    assert taste_match(rows[0], [{'labels': []}], {}, [], []) is None
    assert taste_match(rows[0], bridges, {}, [], []) == 100
    assert taste_match(rows[1], bridges, {}, [], []) == 0
    assert taste_match({**rows[0], 'price': 9999}, bridges, {}, [], []) == 100
    brands = {'other': {'name': 'Other'}}
    assert taste_match(rows[1], bridges, brands, [], []) == 50
    ranked = rank_catalog(rows, intent('dress under 1500'), [], bridges, brands, [])
    percentages = [row['taste_match'] for row in ranked]
    assert percentages == sorted(percentages, reverse=True)
    assert all(0 <= value <= 100 for value in percentages)


def test_qloo_expansion_paginates_deduplicates_and_keeps_partial_results():
    from types import SimpleNamespace
    from fastapi import HTTPException
    from app.myntra_shopping import qloo_brands
    calls = []
    first = [{'name': 'CultureBrand', 'entity_id': 'brand-0'}] + [
        {'name': f'Unsupported {i}', 'entity_id': f'brand-{i}'} for i in range(1, 50)]
    class Qloo:
        def get(self, settings, path, params, **kwargs):
            calls.append((dict(params), kwargs['deadline']))
            assert 1 <= params['take'] <= 50
            if params.get('page', 1) == 1: return first
            if params['page'] == 2:
                return first[:1] + [{'name': 'Other', 'entity_id': 'new-other'}] + [
                    {'name': f'New unsupported {i}', 'entity_id': f'new-{i}'} for i in range(48)]
            raise HTTPException(503, 'Temporary failure')
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
        settings=SimpleNamespace(qloo_api_key='test-key'), qloo=Qloo())))
    brands, status = qloo_brands(request, ['seed'], products(), take=150)
    assert status == 'ready' and set(brands) == {'culturebrand', 'other'}
    assert [params.get('page', 1) for params, _ in calls] == [1, 2, 3]
    assert len({deadline for _, deadline in calls}) == 1
    assert 'page' not in calls[0][0]  # Reuse the original first-page cache key.


def test_qloo_expansion_stops_at_short_or_repeated_pages():
    from types import SimpleNamespace
    from app.myntra_shopping import qloo_brands
    calls = []
    class Qloo:
        batch = [{'name': f'Brand {i}', 'entity_id': str(i)} for i in range(50)]
        def get(self, settings, path, params, **kwargs):
            calls.append(params.get('page', 1))
            return self.batch
    service = Qloo()
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
        settings=SimpleNamespace(qloo_api_key='test-key'), qloo=service)))
    qloo_brands(request, ['seed'], products(), take=150)
    assert calls == [1, 2]  # No new entities; do not keep requesting duplicates.
    calls.clear(); service.batch = service.batch[:2]
    qloo_brands(request, ['seed'], products(), take=150)
    assert calls == [1]
