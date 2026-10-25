import base64
from io import BytesIO
import json
from uuid import UUID
from zipfile import ZipFile

import httpx
from PIL import Image
import pytest
from sqlalchemy.orm import Session

from app.models import TasteTest
from test_api import client, database, headers, USER_A


def item(**changes):
    value = {'title': 'Cream midi dress', 'url': 'https://www.myntra.com/dresses/cream/1/buy',
             'image': 'https://assets.myntassets.com/dress.jpg', 'brand': 'Example', 'price': '1500', 'currency': 'INR'}
    value.update(changes)
    return value


def rank(client, items=None, **changes):
    return client.post('/api/extension/rank', headers=headers(), json={'query': 'midi dress under 2000', 'items': items if items is not None else [item()], **changes})


def test_authenticated_extension_routes(client):
    for path in ('profile', 'saved'):
        assert client.get('/api/extension/' + path).status_code == 401
    for path in ('rank', 'search', 'saved', 'feedback'):
        assert client.post('/api/extension/' + path, json={}).status_code == 401
    assert client.get('/api/extension/profile', headers=headers()).status_code == 200


def test_store_search_links_do_not_request_catalogs_or_models(client):
    data = client.post('/api/extension/search', headers=headers(), json={'query': 'pink midi dress under 2000'}).json()
    assert len(data['links']) == 6
    myntra = next(s for s in data['links'] if s['id'] == 'myntra')
    assert myntra['url'] == 'https://www.myntra.com/pink-midi-dress'
    assert data['budget'] == '2000'


def test_loaded_products_enforce_prompt_price_dislikes_and_unknown_stock(client):
    data = rank(client, [item(), item(title='Cream mini dress', url='https://www.myntra.com/mini', price='1400'),
                         item(url='https://www.myntra.com/expensive', price='3000'), item(url='https://www.myntra.com/sold', sold_out=True),
                         item(url='https://www.myntra.com/unknown', price=None)]).json()
    assert len(data['products']) == 1 and data['unknown_prices'] == 1
    product = data['products'][0]
    assert product['url'].endswith('/1/buy') and 'variant=' not in product['url']
    assert product['price']['amount'] == '1500.00'
    assert product['variant_verified'] is False and 'available' not in product


def test_rank_is_owner_scoped_and_visual_reference_boost_is_grounded(client, database):
    with Session(database[0]) as db:
        from app.models import UserProfile
        db.add(UserProfile(id=UUID(USER_A), email='a@example.com'))
        db.flush()
        db.add(TasteTest(user_id=UUID(USER_A), answers={'q10': {'choices': ['o1']}})); db.commit()
    products = [item(title='Red midi dress', url='https://www.myntra.com/aaa'), item()]
    result = rank(client, products).json()['products']
    assert result[0]['title'] == 'Cream midi dress'
    assert any('neutral' in why for why in result[0]['why'])
    generic = rank(client, products, sort='relevance').json()['products']
    assert generic[0]['title'] == 'Red midi dress'
    other = client.post('/api/extension/rank', headers=headers('user-b'), json={'query': 'midi dress', 'items': products}).json()
    assert not any('saved' in reason for p in other['products'] for reason in p['why'])


@pytest.mark.parametrize('url', ['http://www.myntra.com/dress','https://www.myntra.com.evil.test/dress','https://localhost/dress','javascript:alert(1)','https://user:pass@www.myntra.com/dress'])
def test_untrusted_product_links_are_rejected(client, url):
    assert rank(client, [item(url=url)]).status_code == 422


def test_saved_products_are_durable_idempotent_and_private(client):
    body = {'title': 'A dress', 'url': 'https://www.myntra.com/a-dress', 'image': 'https://assets.myntassets.com/a.jpg'}
    first = client.post('/api/extension/saved', headers=headers(), json=body)
    assert first.status_code == 200, first.text
    assert client.post('/api/extension/saved', headers=headers(), json=body).json()['id'] == first.json()['id']
    assert len(client.get('/api/extension/saved', headers=headers()).json()['items']) == 1
    assert client.get('/api/extension/saved', headers=headers('user-b')).json()['items'] == []
    path = '/api/extension/saved/' + first.json()['id']
    assert client.delete(path, headers=headers('user-b')).status_code == 404
    assert client.delete(path, headers=headers()).status_code == 200


def test_snapshot_cannot_be_used_as_a_search_reference(client):
    assert client.post('/api/extension/describe', headers=headers(), json={}).status_code == 404
    assert rank(client, reference_terms=['red']).status_code == 422


def test_download_contains_installable_package_and_no_credentials(client):
    response = client.get('/api/extension/download')
    assert response.status_code == 200
    assert response.headers['content-type'] == 'application/zip'
    with ZipFile(BytesIO(response.content)) as package:
        manifest = json.loads(package.read('manifest.json'))
        assert manifest['manifest_version'] == 3
        assert set(manifest['permissions']) == {'activeTab','scripting','storage','sidePanel'}
        assert '<all_urls>' not in str(manifest)
        assert 'https://*.myntra.com/*' in manifest['optional_host_permissions']
        assert 'https://*/*' not in manifest['optional_host_permissions']
        assert manifest['externally_connectable']['matches'] == ['http://localhost:5173/*']
        for name in ['worker.js','panel.js','panel.html','extract.js','snapshot.js','cursor.svg','README.md','icons/16.png','icons/48.png','icons/128.png']:
            assert name in package.namelist()
        assert b'http://localhost:5173' in package.read('config.js')
        assert not any('.env' in name or 'test' in name for name in package.namelist())


def test_page_rank_matches_color_from_alt_metadata_and_keeps_blouses_separate_from_tunics(client):
    data = rank(client, [
        item(title='Ruched Wrap Blouse', description='Cream green floral long sleeve blouse', url='https://www.myntra.com/blouse'),
        item(title='Cream Floral Cotton Tunic', description='Ruched wrap', url='https://www.myntra.com/tunic'),
        item(title='Cream Floral Blouse', description='Straight cut', url='https://www.myntra.com/plain-blouse'),
    ], query='cream floral ruched wrap blouse').json()
    assert [p['url'] for p in data['products']] == ['https://www.myntra.com/blouse']
    assert data['excluded'] == {'garment': 1, 'details': 1}


def test_store_search_preserves_specific_garment_cut_and_accent_color(client):
    data = client.post('/api/extension/search', headers=headers(), json={'query': 'cream green floral ruched wrap blouse'}).json()
    assert data['query'] == 'cream green floral ruched wrap blouse'
    assert next(s for s in data['links'] if s['id'] == 'myntra')['url'].endswith('/cream-green-floral-ruched-wrap-blouse')


def test_unrecognized_query_cannot_label_unrelated_products_as_matches(client):
    data = rank(client, query='dragon motif', items=[item(title='Plain Cotton Shirt')]).json()
    assert data['products'] == []
    assert data['excluded'] == {'keywords': 1}


@pytest.mark.parametrize('kind', ['wrong_color', 'wrong_shape', 'not_my_style'])
def test_corrections_rerank_persist_and_are_private(client, kind):
    products = [item(title='Red fitted midi dress', url='https://www.myntra.com/red'),
                item(title='Blue relaxed midi dress', url='https://www.myntra.com/blue'),
                item(title='Red fitted midi dress', url='https://www.myntra.com/red-two')]
    response = client.post('/api/extension/feedback', headers=headers(), json={'item': products[0], 'kind': kind})
    assert response.status_code == 200, response.text
    result = rank(client, products).json()
    assert result['products'][0]['url'].endswith('/blue')
    assert result['excluded']['feedback'] == 1
    assert len(rank(client, products).json()['products']) == 2
    other = client.post('/api/extension/rank', headers=headers('user-b'), json={'query':'midi dress', 'items':products}).json()
    assert len(other['products']) == 3
    assert client.delete('/api/extension/feedback', headers=headers('user-b')).status_code == 200
    assert len(rank(client, products).json()['products']) == 2
    assert client.delete('/api/extension/feedback', headers=headers()).status_code == 200
    assert len(rank(client, products).json()['products']) == 3


def test_positive_feedback_and_price_correction_change_order_without_changing_budget(client):
    products = [item(title='Red midi dress', url='https://www.myntra.com/red', price='1800'),
                item(title='Blue midi dress', url='https://www.myntra.com/blue', price='1000'),
                item(title='Green midi dress', url='https://www.myntra.com/green', price='1900')]
    client.post('/api/extension/feedback', headers=headers(), json={'item':products[1], 'kind':'more_like_this'})
    assert rank(client, products).json()['products'][0]['url'].endswith('/blue')
    client.post('/api/extension/feedback', headers=headers(), json={'item':products[0], 'kind':'too_expensive'})
    data = rank(client, products).json()
    assert data['products'][0]['url'].endswith('/blue')
    assert data['applied_filters']['max_price'] == '2000'
    assert client.post('/api/extension/feedback', headers=headers(), json={'item':products[0], 'kind':'invented'}).status_code == 422


def test_qloo_discovery_drives_brand_search_and_normalized_product_ranking(client, monkeypatch):
    import app.extension as extension
    monkeypatch.setattr(extension, 'current_brands', lambda *args: [
        {'name':name, 'entity_id':str(index), 'rank':index} for index, name in enumerate(['COS','Brand Two','Brand Three','Brand Four'], 1)])
    search = client.post('/api/extension/search', headers=headers(), json={'query':'midi dress under 2000'}).json()
    assert search['discoveries'][0]['name'] == 'COS'
    assert any('cos' in link['url'].lower() for link in search['discoveries'][0]['links'])
    beyond = client.post('/api/extension/search', headers=headers(), json={'query':'midi dress', 'explore':True}).json()
    assert [b['name'] for b in beyond['discoveries']] == ['Brand Four']
    products = [item(brand='Unknown',url='https://www.myntra.com/unknown'), item(brand='C.O.S.',url='https://www.myntra.com/cos')]
    data = rank(client, products).json()
    assert data['products'][0]['qloo_brand'] == 'COS'
    assert data['qloo_matched'] == 1
    assert data['products'][0]['feedback_item']['brand'] == 'C.O.S.'
