from copy import deepcopy
from datetime import datetime, timezone
import json
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy.orm import Session

from app.analysis import source_hash
from app.catalog import BY_ID, ECB_URL, ProductCatalog
from app.enrichment import snapshot
from app.models import TasteAffinityDismissal, TasteAnalysisRun, TasteEnrichmentRun, TasteTest
from app.shopping import SearchRequest, parse_request
from test_api import client, database, headers, USER_A


def product(id='1', title='Cream Relaxed Midi Dress', color='Cream', size='M', price='50.00', **changes):
    value = {'id':'gid://shopify/Product/'+id,'title':title,'handle':'dress-'+id,'vendor':'AVIA','availableForSale':True,
             'productType':'Dress','description':'A relaxed cream dress for an evening party.',
             'featuredImage':{'url':'https://cdn.shopify.com/dress-'+id+'.jpg'},
             'variants':{'nodes':[{'id':'gid://shopify/ProductVariant/'+id+'01','title':size,
                'availableForSale':True,'selectedOptions':[{'name':'Size','value':size},{'name':'Color','value':color}],
                'price':{'amount':price,'currencyCode':'USD'}}], 'pageInfo':{'hasNextPage':False}}}
    value.update(changes)
    return value


def provider(client, nodes=None, failures=None, errors=False):
    calls=[]
    def respond(request):
        calls.append(request)
        assert 'authorization' not in request.headers
        assert 'x-api-key' not in request.headers
        if request.url == ECB_URL:
            today=datetime.now(timezone.utc).date().isoformat()
            return httpx.Response(200,text=f'<Envelope><Cube><Cube time="{today}"><Cube currency="USD" rate="1.1"/><Cube currency="INR" rate="99"/></Cube></Cube></Envelope>')
        assert request.url.host in {s['shop'] for s in BY_ID.values() if s.get('shop')}
        assert request.url.path == '/api/2026-10/graphql.json'
        if failures and request.url.host in failures:
            return httpx.Response(failures[request.url.host])
        if errors: return httpx.Response(200,json={'errors':[{'message':'private diagnostic'}]})
        return httpx.Response(200,json={'data':{'search':{'nodes':nodes if nodes is not None else [product()], 'pageInfo':{'hasNextPage':True}}}})
    client.app.state.catalog.close()
    client.app.state.catalog=ProductCatalog(httpx.Client(transport=httpx.MockTransport(respond)))
    return calls


def search(client, **changes):
    return client.post('/api/search/products',headers=headers(),json={'query':'dress','source_ids':['avia'],'currency':'USD',**changes})


def test_search_and_sources_require_verified_signin(client):
    assert client.get('/api/search/sources').status_code==401
    assert client.post('/api/search/products',json={'query':'dress'}).status_code==401
    for token in ('forged','anonymous','unconfirmed'):
        assert client.post('/api/search/products',headers=headers(token),json={'query':'dress'}).status_code==401
    data=client.get('/api/search/sources',headers=headers()).json()
    assert len([s for s in data['sources'] if s['mode']=='catalog'])==4
    assert len([s for s in data['sources'] if s['mode']=='website'])==6
    assert 'shop' not in str(data)


def test_real_product_contract_and_public_cache_without_generating_ai(client):
    calls=provider(client)
    first=search(client)
    assert first.status_code==200,first.text
    data=first.json(); item=data['products'][0]
    assert item['price']=={'amount':'50.00','currency':'USD','estimated':False}
    assert item['original_price']=={'amount':'50.00','currency':'USD'}
    assert item['available'] is True and item['url']=='https://avia.com/products/dress-1?variant=101'
    assert item['image'].startswith('https://cdn.shopify.com/')
    assert item['fetched_at'] and data['source_statuses'][0]['has_more'] is True
    assert data['exchange'] is None
    assert search(client).json()['products'][0]['id']==item['id']
    assert len(calls)==1
    assert 'private' not in first.text and 'access_token' not in first.text
    payload=json.loads(calls[0].content)
    assert payload['variables']=={'query':'dress'}
    assert 'tags' not in payload['query']  # No token-only product fields.


def test_natural_language_parses_budget_category_color_size_and_occasion():
    parsed=parse_request(SearchRequest(query='Find a pastel farewell dress under ₹3,000 size M'))
    assert parsed['category']=='dresses' and parsed['color']=='pastels' and parsed['size']=='m'
    assert parsed['max_price']==3000 and parsed['currency']=='INR' and parsed['occasion']=='party'
    assert parsed['catalog_query']=='dress'
    parsed=parse_request(SearchRequest(query='Shoes between $30 and $80',max_price='60'))
    assert parsed['min_price']==30 and parsed['max_price']==60 and parsed['currency']=='USD'


@pytest.mark.parametrize('changes', [{'max_price':'-1'},{'min_price':'100','max_price':'20'},
    {'source_ids':['https://internal.invalid']},{'source_ids':['avia','avia']},{'query':'x'},
    {'query':'dress under -3000'},{'query':'dress under 999999999'},{'currency':'INVALID'}])
def test_invalid_filters_never_query_a_store(client,changes):
    calls=provider(client)
    assert search(client,**changes).status_code==422
    assert calls==[]


def test_size_color_availability_and_budget_apply_to_the_same_variant(client):
    item=product()
    item['variants']['nodes']=[
        {**item['variants']['nodes'][0],'id':'gid://shopify/ProductVariant/1','price':{'amount':'20','currencyCode':'USD'},
         'selectedOptions':[{'name':'Size','value':'S'},{'name':'Color','value':'Red'}]},
        {**item['variants']['nodes'][0],'id':'gid://shopify/ProductVariant/2','price':{'amount':'50','currencyCode':'USD'},
         'selectedOptions':[{'name':'Size','value':'M'},{'name':'Color','value':'Blue'}]},
        {**item['variants']['nodes'][0],'id':'gid://shopify/ProductVariant/3','availableForSale':False,
         'selectedOptions':[{'name':'Size','value':'M'},{'name':'Color','value':'Red'}]},
    ]
    provider(client,[item])
    assert search(client,size='M',color='Red',max_price='30').json()['products']==[]
    chosen=search(client,size='M',color='Blue',max_price='55').json()['products'][0]
    assert chosen['url'].endswith('?variant=2') and chosen['price']['amount']=='50.00'
    assert chosen['selected_options']['size']=='M'


def test_inr_conversion_is_real_dated_and_budget_is_enforced(client):
    calls=provider(client)
    data=search(client,currency='INR',max_price='4500').json()
    assert data['products'][0]['price']=={'amount':'4500.00','currency':'INR','estimated':True}
    assert data['products'][0]['original_price']['currency']=='USD'
    assert data['exchange']['source']=='ECB' and data['exchange']['date']
    assert search(client,currency='INR',max_price='4499').json()['products']==[]
    assert len([r for r in calls if r.url==ECB_URL])==1


def test_dislikes_are_hard_constraints_and_do_not_leak_between_accounts(client):
    provider(client,[product(title='Cream Sequin Midi Dress'), product(id='2',title='Plain Midi Dress',description='No sequins, with a relaxed fit.')])
    client.put('/api/onboarding',headers=headers(),json={'answers':{'q15':{'choices':['other'],'other':'Sequin'}}})
    data=search(client).json()
    assert [p['id'] for p in data['products']]==['avia:2']
    other=client.post('/api/search/products',headers=headers('user-b'),json={'query':'dress','source_ids':['avia'],'currency':'USD'}).json()
    assert len(other['products'])==2


def test_taste_ranking_respects_owner_and_generic_comparison(client,database):
    provider(client,[product(id='1',color='Red',title='Red Midi Dress'),product(id='2',color='Cream')])
    client.put('/api/onboarding',headers=headers(),json={'answers':{'q10':{'choices':['o1']}}})
    personalized=search(client).json()['products']
    assert personalized[0]['id']=='avia:2'
    assert any('saved neutrals' in reason for reason in personalized[0]['why'])
    generic=search(client,sort='relevance').json()['products']
    assert all(not any('saved neutrals' in why for why in p['why']) for p in generic)


def test_current_image_evidence_and_qloo_influence_are_saved_owner_scoped_signals(client,database):
    provider(client)
    client.put('/api/onboarding',headers=headers(),json={'answers':{'q15':{'choices':['none']}}})
    with Session(database[0]) as db:
        user=type('User',(),{'id':UUID(USER_A)})()
        profile=db.get(TasteTest,user.id)
        db.add(TasteAnalysisRun(id=uuid4(),user_id=user.id,source_hash=source_hash(profile,[]),sources={},model='test',prompt_version='test',status='succeeded',
            result={'recurring_visual_signals':[{'category':'color','attribute':'cream','evidence_image_ids':[],'explanation':'Test observation'}]}))
        db.commit()
        sources,fingerprint=snapshot(db,user,client.app.state.settings)
        db.add(TasteEnrichmentRun(id=uuid4(),user_id=user.id,source_hash=fingerprint,sources=sources,resolver_version='qloo-v2',status='succeeded',
            result={'affinities':[{'entity_id':BY_ID['avia']['qloo_entity_id'],'name':'AVIA'}]}))
        db.commit()
    item=search(client).json()['products'][0]
    assert any('saved inspirations' in why for why in item['why'])
    assert any('Qloo' in why for why in item['why'])
    with Session(database[0]) as db:
        db.add(TasteAffinityDismissal(user_id=UUID(USER_A),entity_id=UUID(BY_ID['avia']['qloo_entity_id']),name='AVIA'));db.commit()
    assert not any('Qloo' in why for why in search(client).json()['products'][0]['why'])


def test_partial_provider_failure_keeps_working_results_and_all_failures_are_recoverable(client):
    provider(client,failures={'prabalgurung.myshopify.com':429})
    data=search(client,source_ids=['avia','prabal-gurung']).json()
    assert data['status']=='partial' and len(data['products'])==1
    assert any(s['status']=='rate_limited' for s in data['source_statuses'])
    assert search(client,source_ids=['prabal-gurung']).status_code==503
    provider(client,errors=True)
    failure=search(client)
    assert failure.status_code==503 and 'private diagnostic' not in failure.text


def test_retailers_are_external_links_and_never_fake_product_cards(client):
    calls=provider(client)
    data=search(client,source_ids=['myntra','amazon-fashion','nykaa-fashion']).json()
    assert data['status']=='external_only' and data['products']==[]
    assert len(data['retailer_links'])==3 and calls==[]
    assert data['retailer_links'][0]['url']=='https://www.myntra.com/dress'
    assert 'i=apparel' in data['retailer_links'][1]['url']


def test_non_products_and_unsafe_or_missing_images_are_omitted(client):
    provider(client,[product(featuredImage={'url':'javascript:alert(1)'}),product(id='2',availableForSale=False),product(id='3',handle='../admin'),product(id='4')])
    data=search(client).json()
    assert [p['id'] for p in data['products']]==['avia:4']


def test_search_rate_limit_uses_authenticated_identity(client):
    provider(client)
    for _ in range(10): assert search(client).status_code==200
    assert search(client).status_code==429
    assert client.post('/api/search/products',headers=headers('user-b'),json={'query':'dress','currency':'USD','source_ids':['avia']}).status_code==200


@pytest.mark.parametrize('query, expected', [('floral blouse', 'floral blouse'), ('cotton tunic', 'cotton tunic'), ('linen shirt', 'linen shirt'), ('denim skirt', 'denim skirt')])
def test_query_parser_preserves_requested_garment(query, expected):
    assert parse_request(SearchRequest(query=query))['catalog_query'] == expected
