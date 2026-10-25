from datetime import datetime, timezone
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.models import TasteAnalysisRun
from app.qloo import QlooClient
from test_api import database, headers, USER_A
from test_onboarding import client
from test_enrichment import saved_profile, ZARA, ARTIST, COS

BOOK = 'dddddddd-dddd-4ddd-8ddd-dddddddddddd'


def provider(client, failures=()):
    calls = []
    def transport(request):
        calls.append(request)
        if request.url.path == '/search':
            return httpx.Response(200, json={'results': [{'entity_id': ZARA, 'name': 'Zara', 'subtype': 'urn:entity:brand'}]})
        if request.url.path == '/v2/tags':
            return httpx.Response(200, json={'results': {'tags': []}})
        kind = request.url.params['filter.type']
        if kind in failures:
            return httpx.Response(403)
        if kind == 'urn:tag':
            return httpx.Response(200, json={'results': {'tags': [{'tag_id': 'urn:tag:keyword:media:friendship', 'name': 'Friendship'}]}})
        identity = ARTIST if kind == 'urn:entity:artist' else BOOK if kind == 'urn:entity:book' else COS
        return httpx.Response(200, json={'results': {'entities': [{'entity_id': identity, 'name': 'Discovery ' + kind.split(':')[-1], 'subtype': kind,
            'properties': {'image': {'url': 'https://images.example.com/art.jpg'}}}]}})
    client.app.state.qloo = QlooClient(httpx.Client(transport=httpx.MockTransport(transport)))
    return calls


def test_culture_auth_read_only_cache_and_provenance(client):
    assert client.get('/api/onboarding/culture').status_code == 401
    saved_profile(client)
    calls = provider(client)
    assert client.get('/api/onboarding/culture', headers=headers()).json()['status'] == 'not_generated'
    assert calls == []
    response = client.post('/api/onboarding/culture', headers=headers())
    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data['result']['domains']) == 4
    assert data['result']['themes'][0]['name'] == 'Friendship'
    assert data['result']['domains'][0]['items'][0]['image'].startswith('https://')
    assert not data['stale']
    count = len(calls)
    assert client.post('/api/onboarding/culture', headers=headers()).json()['id'] == data['id']
    assert len(calls) == count
    assert client.get('/api/onboarding/culture', headers=headers('user-b')).json()['status'] == 'not_generated'


def test_feedback_changes_seeds_exclusions_and_is_owner_scoped(client):
    saved_profile(client)
    calls = provider(client)
    client.post('/api/onboarding/culture', headers=headers())
    endpoint = f'/api/onboarding/culture/feedback/{ARTIST}'
    assert client.put(endpoint, headers=headers('user-b'), json={'preference': 'like'}).status_code == 404
    data = client.put(endpoint, headers=headers(), json={'preference': 'like', 'fashion_inspiration': True}).json()
    assert data['stale'] and data['analytics']['liked'] == 1 and data['analytics']['fashion_inspirations'] == 1
    client.post('/api/onboarding/culture', headers=headers())
    insights = [c for c in calls if c.url.path == '/v2/insights']
    assert ARTIST in insights[-1].url.params['signal.interests.entities']
    client.put(endpoint, headers=headers(), json={'preference': 'dislike', 'fashion_inspiration': True})
    data = client.post('/api/onboarding/culture', headers=headers()).json()
    assert data['feedback'][0]['fashion_inspiration'] is False
    insights = [c for c in calls if c.url.path == '/v2/insights']
    assert ARTIST in insights[-1].url.params['filter.exclude.entities']
    assert ARTIST not in insights[-1].url.params['signal.interests.entities']
    assert client.put(f'/api/onboarding/culture/feedback/{ZARA}', headers=headers(), json={'preference': 'like'}).status_code == 404


def test_partial_category_failure_preserves_other_discoveries(client):
    saved_profile(client)
    calls = provider(client, failures=('urn:entity:book',))
    data = client.post('/api/onboarding/culture', headers=headers()).json()
    assert data['status'] == 'succeeded' and data['result']['outcome'] == 'partial'
    assert data['result']['domains'][-1]['status'] == 'unavailable'
    assert data['result']['domains'][-1]['error_code'] == 503
    assert data['result']['domains'][-1]['error']
    assert data['result']['domains'][0]['items']
    count = len(calls)
    assert client.post('/api/onboarding/culture', headers=headers()).status_code == 200
    assert len(calls) > count  # A partial result must not become a permanent cache hit.


def test_all_categories_fail_preserves_previous_success(client):
    saved_profile(client)
    provider(client)
    first = client.post('/api/onboarding/culture', headers=headers()).json()
    provider(client, failures=tuple('urn:entity:' + k for k in ('artist', 'movie', 'tv_show', 'book')))
    assert client.post('/api/onboarding/culture?force=true', headers=headers()).status_code == 503
    data = client.get('/api/onboarding/culture', headers=headers()).json()
    assert data['status'] == 'failed' and data['previous_successful']['id'] == first['id']


def test_image_signals_use_only_current_analysis_and_supported_tags(client, database):
    from app.analysis import source_hash
    from app.models import TasteTest
    from app.onboarding import images_for
    from app.auth import AuthUser
    saved_profile(client)
    calls = provider(client)
    user = AuthUser(id=UUID(USER_A), email='a@example.com')
    with Session(database[0]) as db:
        profile = db.get(TasteTest, UUID(USER_A))
        digest = source_hash(profile, images_for(db, user))
        db.add(TasteAnalysisRun(id=UUID(BOOK), user_id=user.id, source_hash=digest, sources={}, status='succeeded',
            model='fixture', prompt_version='fixture', created_at=datetime.now(timezone.utc), result={
                'recurring_visual_signals': [{'category': 'aesthetic', 'attribute': 'Minimal', 'evidence_image_ids': [], 'explanation': 'Clean lines'}], 'images': []}))
        db.commit()
    data = client.post('/api/onboarding/culture', headers=headers()).json()
    image = next(r for r in data['result']['resolutions'] if r.get('source') == 'image')
    assert image['input'] == 'Minimal' and image['status'] == 'unsupported'
    assert any(c.url.params.get('filter.query') == 'Minimal' for c in calls)
    assert 'images' not in data['result']['input_counts']
