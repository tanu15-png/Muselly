import json
from copy import deepcopy

import pytest

from app.myntra_shopping import read_catalog
from app.retailers import valid_source
from tools.multi_retailer_catalog import normalize


def ajio():
    return {'product_id': '123_blue', 'name': 'Women Cotton Floral Dress', 'brand': 'Example',
            'price': 900, 'offer_price': 500, 'regular_price': 1500, 'currency': 'INR',
            'main_image': 'https://assets.ajio.com/model.jpg',
            'url': 'https://www.ajio.com/example/p/123_blue', 'breadcrumbs': ['Women', 'Dresses']}


def test_coupon_price_is_not_used_and_gender_is_evidenced():
    row = normalize(ajio(), 'AJIO')
    assert row['price'] == 900 and row['product_id'] == 'ajio:123_blue'
    raw = ajio(); raw['breadcrumbs'] = ['Kids', 'Dresses']
    assert normalize(raw, 'AJIO') is None


def test_region_host_and_identifier_cannot_be_mismatched():
    row = normalize(ajio(), 'AJIO')
    assert valid_source(row)
    for url in ['https://www.ajio.com.evil.test/example/p/123_blue',
                'https://www.ajio.com/example/p/999', 'https://user@www.ajio.com/example/p/123_blue']:
        assert not valid_source({**row, 'product_url': url})
    hm = {**row, 'retailer': 'H&M', 'product_id': 'hm:123',
          'product_url': 'https://www2.hm.com/en_us/productpage.123.html',
          'image_url': 'https://image.hm.com/a.jpg'}
    assert not valid_source(hm)
    assert valid_source({**hm, 'product_url': 'https://www2.hm.com/en_in/productpage.123.html'})


def test_nykaa_null_variants_and_wrong_pet_record_are_handled():
    raw = {'id': '123', 'title': 'Example', 'sub_title': 'Women Floral Dress',
           'price': 1500, 'discounted_price': 900, 'category_id': ['6557'],
           'image_url': 'https://adn-static1.nykaa.com/a.jpg', 'action_url': '/example/p/123',
           'plp_pdp_bridge': {'variants': None}}
    assert normalize(raw, 'Nykaa Fashion')['price'] == 900
    raw['sub_title'] = 'Unisex Dog Jumper'
    assert normalize(raw, 'Nykaa Fashion') is None


def test_catalog_keeps_cross_retailer_ids_distinct_and_rejects_malicious_source(tmp_path):
    ajio_row = normalize(ajio(), 'AJIO')
    myntra = {**ajio_row, 'retailer': 'Myntra', 'product_id': '123',
              'product_url': 'https://www.myntra.com/clothing/123/buy',
              'image_url': 'https://assets.myntassets.com/123.jpg'}
    path = tmp_path/'catalog.json'
    path.write_text(json.dumps([myntra,ajio_row]),encoding='utf-8')
    stat = path.stat()
    assert len(read_catalog(str(path),stat.st_mtime_ns,stat.st_size)) == 2
    ajio_row['image_url'] = 'https://example.test/image.jpg'
    path.write_text(json.dumps([myntra,ajio_row]),encoding='utf-8')
    stat = path.stat()
    with pytest.raises(Exception) as failure:
        read_catalog(str(path),stat.st_mtime_ns,stat.st_size)
    assert failure.value.status_code == 503
