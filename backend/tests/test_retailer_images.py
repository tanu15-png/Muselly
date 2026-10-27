from io import BytesIO
import json

import httpx
import pytest
from PIL import Image

from app.retailer_images import RetailerImages
from app.myntra_shopping import public_product
from test_api import database
from test_onboarding import client
from test_myntra_shopping import products


def image_bytes():
    output = BytesIO()
    Image.new('RGB',(8,8),'pink').save(output,format='PNG')
    return output.getvalue()


def test_image_delivery_is_limited_to_known_catalog_item_and_cache(client,tmp_path):
    row = {**products()[0], 'retailer':'H&M','product_id':'hm:101',
           'product_url':'https://www2.hm.com/en_in/productpage.101.html',
           'image_url':'https://image.hm.com/101.jpg'}
    path = tmp_path/'catalog.json'; path.write_text(json.dumps([row]),encoding='utf-8')
    client.app.state.settings.myntra_catalog_path = str(path)
    calls = []
    def transport(request):
        assert str(request.url) == row['image_url']
        assert 'authorization' not in request.headers and 'apikey' not in request.headers
        calls.append(request)
        return httpx.Response(200,content=image_bytes(),headers={'content-type':'image/png'})
    with httpx.Client(transport=httpx.MockTransport(transport)) as source:
        client.app.state.retailer_images = RetailerImages(source)
        for _ in range(2):
            response = client.get('/api/shop/images/hm:101')
            assert response.status_code == 200 and response.headers['content-type'] == 'image/png'
        assert len(calls) == 1
        assert client.get('/api/shop/images/hm:999?url=http://127.0.0.1/').status_code == 404
        assert len(calls) == 1
    assert public_product(row)['image_url'] == '/api/shop/images/hm:101'
    assert public_product(products()[0])['image_url'].startswith('https://assets.myntassets.com/')


@pytest.mark.parametrize('status,content_type,data',[
    (302,'image/png',b''),(200,'text/html',b'<html>error</html>'),
    (200,'image/svg+xml',b'<svg></svg>'),(200,'image/png',b'x'*8_000_001),
], ids=['redirect','html','svg','oversized'])
def test_image_delivery_rejects_redirects_nonimages_and_oversized_data(status,content_type,data):
    def transport(request):
        return httpx.Response(status,content=data,headers={'content-type':content_type,'location':'http://127.0.0.1/'})
    with httpx.Client(transport=httpx.MockTransport(transport)) as source:
        with pytest.raises(Exception) as failure:
            RetailerImages(source).get('https://image.hm.com/101.jpg')
        assert failure.value.status_code == 502


def test_image_cache_has_a_byte_limit():
    calls=[]; data=image_bytes()
    def transport(request):
        calls.append(str(request.url)); return httpx.Response(200,content=data,headers={'content-type':'image/png'})
    with httpx.Client(transport=httpx.MockTransport(transport)) as source:
        cache = RetailerImages(source,max_bytes=len(data)+1)
        cache.get('https://image.hm.com/1.jpg'); cache.get('https://image.hm.com/2.jpg')
        cache.get('https://image.hm.com/1.jpg')
        assert len(calls)==3 and cache.size <= cache.max_bytes
