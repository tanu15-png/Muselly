from uuid import uuid4

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models import CulturalEvent, CulturalExposure
from test_api import database, headers
from test_onboarding import client
from test_discovery import start


def test_removing_fashion_connection_keeps_like_and_reference_library(client, database):
    from app.models import InspirationImage, CulturalFeedback
    from test_api import USER_A
    from uuid import UUID
    data, _ = start(client)
    item = data['session']['queue'][0]
    with Session(database[0]) as db:
        images = list(db.scalars(select(InspirationImage.id)))
    url = f'/api/onboarding/culture/feedback/{item["entity_id"]}'
    assert client.put(url, headers=headers(), json={'preference': 'like', 'fashion_inspiration': True,
        'reference_image_ids': [str(images[0])]}).status_code == 200
    assert client.put(url, headers=headers('user-b'), json={'fashion_inspiration': False}).status_code == 404
    assert client.put(url, headers=headers(), json={'preference': 'like', 'fashion_inspiration': False}).status_code == 200
    with Session(database[0]) as db:
        row = db.get(CulturalFeedback, (UUID(USER_A), UUID(item['entity_id'])))
        assert row.preference == 'like' and not row.fashion_inspiration and row.reference_image_ids == []
        assert set(db.scalars(select(InspirationImage.id))) == set(images)


def test_confirmed_fashion_links_are_owned_persisted_and_undone(client, database):
    from app.models import InspirationImage
    from test_api import USER_A
    from uuid import UUID
    data, _ = start(client)
    item = data['session']['queue'][0]
    with Session(database[0]) as db:
        image_id = str(db.scalar(select(InspirationImage.id).where(InspirationImage.user_id == UUID(USER_A))))
    url = f'/api/onboarding/culture/sessions/{data["session"]["id"]}/sync'
    invalid = event(item, 'fashion', reference_image_ids=[str(uuid4())])
    assert client.post(url, headers=headers(), json={'actions': [invalid]}).status_code == 422
    assert client.post(url, headers=headers(), json={'actions': [event(item, 'fashion', reference_image_ids=[])]}).status_code == 422
    action = event(item, 'fashion', reference_image_ids=[image_id])
    assert client.post(url, headers=headers(), json={'actions': [action]}).status_code == 200
    linked = client.get('/api/onboarding/culture/analytics', headers=headers()).json()['combined']['fashion_entities']
    assert linked[0]['reference_image_ids'] == [image_id]
    assert client.post(url, headers=headers(), json={'actions': [action]}).status_code == 200
    assert client.post(url, headers=headers(), json={'actions': [event(item, 'undo', target_id=action['event_id'])]}).status_code == 200
    assert client.get('/api/onboarding/culture/analytics', headers=headers()).json()['combined']['fashion_entities'] == []


def test_deleted_reference_stops_appearing_as_confirmed_evidence(client, database):
    from app.models import InspirationImage
    data, _ = start(client)
    with Session(database[0]) as db:
        image = db.scalar(select(InspirationImage))
        image_id = str(image.id)
    action = event(data['session']['queue'][0], 'fashion', reference_image_ids=[image_id])
    url = f'/api/onboarding/culture/sessions/{data["session"]["id"]}/sync'
    assert client.post(url, headers=headers(), json={'actions': [action]}).status_code == 200
    with Session(database[0]) as db:
        db.delete(db.get(InspirationImage, image.id)); db.commit()
    linked = client.get('/api/onboarding/culture/analytics', headers=headers()).json()['combined']['fashion_entities']
    assert linked[0]['reference_image_ids'] == []


def test_connection_attributes_use_only_selected_reference_evidence(client, database):
    from datetime import datetime, timezone
    from app.models import InspirationImage, TasteAnalysisRun
    data, _ = start(client)
    with Session(database[0]) as db:
        images = list(db.scalars(select(InspirationImage)))[:2]
        selected_id = str(images[0].id)
        other_id = str(images[1].id)
        db.add(TasteAnalysisRun(id=uuid4(), user_id=images[0].user_id, source_hash='fixture',
            model='fixture', prompt_version='fixture', status='succeeded',
            sources={'images': [{'id': str(image.id), 'updated_at': image.updated_at.isoformat()} for image in images]},
            result={'images': [{'image_id': selected_id, 'colors': ['Cream'], 'patterns': ['Floral']},
                {'image_id': str(images[1].id), 'colors': ['Red'], 'patterns': ['Striped']}]},
            created_at=datetime.now(timezone.utc)))
        db.commit()
    item = data['session']['queue'][0]
    url = f'/api/onboarding/culture/sessions/{data["session"]["id"]}/sync'
    assert client.post(url, headers=headers(), json={'actions': [event(item, 'fashion', reference_image_ids=[selected_id])]}).status_code == 200
    linked = client.get('/api/onboarding/culture/analytics', headers=headers()).json()['combined']['fashion_entities'][0]
    assert linked['colors'] == ['Cream'] and linked['patterns'] == ['Floral']
    edited = client.put(f'/api/onboarding/culture/feedback/{item["entity_id"]}', headers=headers(),
        json={'preference': 'like', 'fashion_inspiration': True, 'reference_image_ids': [other_id]})
    assert edited.status_code == 200
    linked = client.get('/api/onboarding/culture/analytics', headers=headers()).json()['combined']['fashion_entities'][0]
    assert linked['colors'] == ['Red'] and linked['preference'] == 'like'


def event(item, action, **extra):
    return {'event_id': str(uuid4()), 'entity_id': item['entity_id'], 'action': action, **extra}


def test_batch_saves_multiple_choices_and_views_without_profile_read_or_qloo(client, database, monkeypatch):
    data, calls = start(client)
    session = data['session']
    items = session['queue'][:3]
    actions = [event(items[0], 'shown'), event(items[0], 'like'), event(items[1], 'known'), event(items[2], 'fashion')]
    count = len(calls)
    import app.culture
    monkeypatch.setattr(app.culture, 'view', lambda *args: (_ for _ in ()).throw(AssertionError('Sync must not rebuild profile')))
    url = f'/api/onboarding/culture/sessions/{session["id"]}/sync'
    response = client.post(url, headers=headers(), json={'actions': actions})
    assert response.status_code == 200, response.text
    assert response.json()['acked'] == [a['event_id'] for a in actions]
    assert set(response.json()) == {'acked', 'session_id', 'choices_since_refresh'}
    assert client.post(url, headers=headers(), json={'actions': actions}).status_code == 200
    assert len(calls) == count
    with Session(database[0]) as db:
        assert db.scalar(select(func.count()).select_from(CulturalEvent)) == 4
        assert db.scalar(select(func.count()).select_from(CulturalExposure)) == 3
    totals = client.get('/api/onboarding/culture/analytics', headers=headers()).json()['cultural']['totals']
    assert totals['liked'] == 1 and totals['known'] == 1 and totals['fashion'] == 1 and totals['shown'] == 3


def test_pending_choice_and_undo_can_be_committed_in_one_batch(client):
    data, _ = start(client)
    item = data['session']['queue'][0]
    choice = event(item, 'like')
    undo = event(item, 'undo', target_id=choice['event_id'])
    url = f'/api/onboarding/culture/sessions/{data["session"]["id"]}/sync'
    response = client.post(url, headers=headers(), json={'actions': [choice, undo]})
    assert response.status_code == 200, response.text
    assert client.post(url, headers=headers(), json={'actions': [choice, undo]}).status_code == 200
    result = client.get('/api/onboarding/culture', headers=headers()).json()
    assert result['session']['queue'][0]['entity_id'] == item['entity_id']
    assert result['analytics']['liked'] == 0
    assert client.get('/api/onboarding/culture/analytics', headers=headers()).json()['cultural']['history'] == []


def test_sync_is_atomic_owner_scoped_and_rejects_unoffered_products(client, database):
    data, _ = start(client)
    item = data['session']['queue'][0]
    url = f'/api/onboarding/culture/sessions/{data["session"]["id"]}/sync'
    actions = [event(item, 'like')]
    assert client.post(url, json={'actions': actions}).status_code == 401
    assert client.post(url, headers=headers('user-b'), json={'actions': actions}).status_code == 404
    invalid = event({'entity_id': str(uuid4())}, 'like')
    assert client.post(url, headers=headers(), json={'actions': [*actions, invalid]}).status_code == 404
    with Session(database[0]) as db:
        assert db.scalar(select(func.count()).select_from(CulturalEvent)) == 0
    assert client.post(url, headers=headers(), json={'actions': actions}).status_code == 200
    assert client.post(url, headers=headers(), json={'actions': [{**actions[0], 'action': 'dislike'}]}).status_code == 409


def test_late_choices_are_valid_after_background_queue_replacement(client):
    data, _ = start(client)
    session = data['session']
    actions = [event(item, 'like') for item in session['queue'][:5]]
    url = f'/api/onboarding/culture/sessions/{session["id"]}/sync'
    assert client.post(url, headers=headers(), json={'actions': actions}).status_code == 200
    before = session['queue'][-1]
    assert client.post(f'/api/onboarding/culture/sessions/{session["id"]}/batch', headers=headers()).status_code == 200
    response = client.post(url, headers=headers(), json={'actions': [event(before, 'like')]})
    assert response.status_code == 200, response.text


def test_music_requests_have_longer_bounded_timeouts(client):
    _, calls = start(client)
    insights = [call for call in calls if call.url.path == '/v2/insights']
    artist = next(call for call in insights if call.url.params['filter.type'] == 'urn:entity:artist')
    movie = next(call for call in insights if call.url.params['filter.type'] == 'urn:entity:movie')
    assert artist.extensions['timeout']['read'] == 25
    assert movie.extensions['timeout']['read'] == 12
