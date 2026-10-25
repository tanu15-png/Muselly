from datetime import datetime, timezone
from uuid import UUID, uuid4, uuid5, NAMESPACE_DNS

import httpx
from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models import CulturalEvent, CulturalExposure, TasteAnalysisRun, TasteTest
from app.qloo import QlooClient
from test_api import database, headers, USER_A
from test_onboarding import client
from test_enrichment import saved_profile, ZARA


def stream_provider(client):
    calls = []
    def transport(request):
        calls.append(request)
        if request.url.path == '/search':
            return httpx.Response(200, json={'results': [{'entity_id': ZARA, 'name': 'Zara', 'subtype': 'urn:entity:brand'}]})
        if request.url.path == '/v2/tags':
            return httpx.Response(200, json={'results': {'tags': []}})
        kind = request.url.params['filter.type']
        if kind == 'urn:tag':
            return httpx.Response(200, json={'results': {'tags': []}})
        offset = int(request.url.params.get('offset', 0))
        items = [{'entity_id': str(uuid5(NAMESPACE_DNS, kind + str(index))), 'name': f'{kind} {index}',
                  'subtype': kind, 'tags': [{'tag_id': 'urn:tag:genre:media:drama', 'name': 'Drama'}]}
                 for index in range(offset, min(offset + 8, 16))]
        return httpx.Response(200, json={'results': {'entities': items}})
    client.app.state.qloo = QlooClient(httpx.Client(transport=httpx.MockTransport(transport)))
    return calls


def start(client):
    saved_profile(client)
    calls = stream_provider(client)
    response = client.post('/api/onboarding/culture', headers=headers())
    assert response.status_code == 200, response.text
    return response.json(), calls


def choice(client, session_id, item, action='like', event_id=None):
    return client.post(f'/api/onboarding/culture/sessions/{session_id}/choices/{item["entity_id"]}',
                       headers=headers(), json={'action': action, 'event_id': str(event_id or uuid4())})


def test_deck_mixes_categories_records_actual_views_and_idempotent_feedback(client, database):
    data, calls = start(client)
    session = data['session']
    assert len(session['queue']) == 32
    assert [item['domain'] for item in session['queue'][:4]] == ['artist', 'movie', 'tv_show', 'book']
    count = len(calls)
    item = session['queue'][0]
    url = f'/api/onboarding/culture/sessions/{session["id"]}/shown/{item["entity_id"]}'
    assert client.post(url, headers=headers('user-b')).status_code == 404
    assert client.post(url, headers=headers()).status_code == 200
    assert client.post(url, headers=headers()).status_code == 200
    event = uuid4()
    result = choice(client, session['id'], item, event_id=event)
    assert result.status_code == 200, result.text
    assert result.json()['session']['queue'][0]['domain'] == 'movie'
    assert choice(client, session['id'], item, event_id=event).status_code == 200
    assert len(calls) == count  # Local feedback and GET never invoke Qloo.
    assert client.get('/api/onboarding/culture', headers=headers()).json()['session']['queue'] == result.json()['session']['queue']
    with Session(database[0]) as db:
        assert db.scalar(select(func.count()).select_from(CulturalExposure)) == 1
        assert db.scalar(select(func.count()).select_from(CulturalEvent)) == 1
    analytics = client.get('/api/onboarding/culture/analytics', headers=headers()).json()
    assert analytics['cultural']['totals']['shown'] == 1
    assert analytics['cultural']['totals']['liked'] == 1
    assert analytics['cultural']['themes'] == [{'label': 'Drama', 'count': 1}]


def test_undo_restores_card_and_clears_preference_without_double_counting(client):
    data, calls = start(client)
    session = data['session']
    item = session['queue'][0]
    event = uuid4()
    assert choice(client, session['id'], item, 'fashion', event).status_code == 200
    url = f'/api/onboarding/culture/sessions/{session["id"]}/undo/{event}'
    undo_id = str(uuid4())
    response = client.post(url, headers=headers(), json={'event_id': undo_id})
    assert response.status_code == 200, response.text
    assert response.json()['session']['queue'][0]['entity_id'] == item['entity_id']
    assert response.json()['analytics']['fashion_inspirations'] == 0
    assert client.post(url, headers=headers(), json={'event_id': undo_id}).status_code == 200
    analytics = client.get('/api/onboarding/culture/analytics', headers=headers()).json()
    assert analytics['cultural']['history'] == []


def test_category_refill_uses_offset_excludes_seen_and_can_exhaust(client):
    data, calls = start(client)
    session = data['session']
    originals = [item for item in session['queue'] if item['domain'] == 'artist']
    for item in originals:
        assert choice(client, session['id'], item, 'skip').status_code == 200
    url = f'/api/onboarding/culture/sessions/{session["id"]}/batch?category=artist'
    response = client.post(url, headers=headers())
    assert response.status_code == 200, response.text
    artists = [item for item in response.json()['session']['queue'] if item['domain'] == 'artist']
    assert len(artists) == 8 and not {i['entity_id'] for i in originals} & {i['entity_id'] for i in artists}
    assert calls[-1].url.params['offset'] == '8'
    for item in artists:
        assert choice(client, session['id'], item, 'skip').status_code == 200
    response = client.post(url, headers=headers())
    assert next(d for d in response.json()['session']['domains'] if d['id'] == 'artist')['exhausted']
    assert not [item for item in response.json()['session']['queue'] if item['domain'] == 'artist']


def test_five_choices_refresh_query_without_waiting_for_entire_queue(client):
    data, calls = start(client)
    session_id = data['session']['id']
    liked = []
    for _ in range(5):
        item = data['session']['queue'][0]
        liked.append(item['entity_id'])
        data = choice(client, session_id, item).json()
    first = data['session']['queue'][0]['entity_id']
    anchor = data['session']['queue'][-1]['entity_id']
    assert len(data['session']['queue']) > 6 and data['session']['choices_since_refresh'] == 5
    response = client.post(f'/api/onboarding/culture/sessions/{session_id}/batch?anchor={anchor}', headers=headers())
    assert response.status_code == 200, response.text
    assert response.json()['session']['queue'][0]['entity_id'] == anchor
    assert first in {item['entity_id'] for item in response.json()['session']['queue']}
    assert anchor in {item['entity_id'] for item in response.json()['session']['queue']}
    assert response.json()['session']['choices_since_refresh'] == 0
    assert all(value in calls[-1].url.params['signal.interests.entities'] for value in liked)
    assert calls[-1].url.params['offset'] == '0'


def test_failed_category_can_retry_while_other_categories_have_full_buffers(client):
    saved_profile(client)
    calls = stream_provider(client)
    original = client.app.state.qloo.get
    def unavailable(settings, path, params, **options):
        if path == '/v2/insights' and params.get('filter.type') == 'urn:entity:artist':
            raise HTTPException(504, 'Temporary music timeout')
        return original(settings, path, params, **options)
    client.app.state.qloo.get = unavailable
    data = client.post('/api/onboarding/culture', headers=headers()).json()
    assert len(data['session']['queue']) == 24
    assert data['session']['domains'][0]['error_code'] == 504
    client.app.state.qloo.get = original
    count = len(calls)
    response = client.post(f'/api/onboarding/culture/sessions/{data["session"]["id"]}/batch?retry=true', headers=headers())
    assert response.status_code == 200, response.text
    assert len(response.json()['session']['queue']) == 32
    assert all(domain['status'] == 'ready' for domain in response.json()['session']['domains'])
    requests = [call for call in calls[count:] if call.url.path == '/v2/insights']
    assert len(requests) == 1 and requests[0].url.params['filter.type'] == 'urn:entity:artist'


def test_analytics_is_private_and_familiarity_is_not_dislike(client):
    data, calls = start(client)
    item = data['session']['queue'][0]
    assert choice(client, data['session']['id'], item, 'known').status_code == 200
    count = len(calls)
    analytics = client.get('/api/onboarding/culture/analytics', headers=headers()).json()
    totals = analytics['cultural']['totals']
    assert totals['known'] == 1 and totals['disliked'] == 0 and totals['rated'] == 0
    assert analytics['cultural']['domains'][0]['like_rate'] is None
    assert client.get('/api/onboarding/culture/analytics').status_code == 401
    other = client.get('/api/onboarding/culture/analytics', headers=headers('user-b')).json()
    assert other['cultural']['totals']['shown'] == 0 and other['cultural']['totals']['known'] == 0
    assert len(calls) == count


def test_visual_counts_deduplicate_per_image_and_ignore_deleted_or_modified_references(client, database):
    from app.onboarding import images_for
    from app.auth import AuthUser
    saved_profile(client)
    user = AuthUser(id=UUID(USER_A), email='a@example.com')
    with Session(database[0]) as db:
        images = list(images_for(db, user))
        first = str(images[0].id)
        db.add(TasteAnalysisRun(id=uuid4(), user_id=user.id, source_hash='old', model='fixture', prompt_version='fixture',
            status='succeeded', sources={'images': [{'id': first, 'updated_at': images[0].updated_at.isoformat()},
              {'id': str(images[1].id), 'updated_at': '2000-01-01'}]},
            result={'images': [{'image_id': first, 'colors': ['Cream', 'cream'], 'patterns': ['Floral', 'floral']},
                              {'image_id': str(images[1].id), 'colors': ['Red'], 'patterns': ['Striped']},
                              {'image_id': str(uuid4()), 'colors': ['Blue'], 'patterns': ['Checked']}]},
            created_at=datetime.now(timezone.utc)))
        db.commit()
    visual = client.get('/api/onboarding/culture/analytics', headers=headers()).json()['visual']
    assert visual['analyzed_images'] == 1 and visual['stale']
    assert visual['colors'] == [{'label': 'Cream', 'count': 1, 'image_ids': [first]}]
    assert visual['patterns'][0]['count'] == 1
