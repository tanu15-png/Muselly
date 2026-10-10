from io import BytesIO
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient
from PIL import Image
import pytest
from sqlalchemy.orm import Session

from app.config import Settings
from app.database import get_db
from app.main import create_app
from app.onboarding import QUESTIONS, LIMIT
from test_api import database, headers, supabase_response, USER_A


@pytest.fixture
def client(database, tmp_path):
    objects = {}
    failures = []
    calls = []

    def transport(request):
        if '/auth/v1/' in str(request.url):
            return supabase_response(request)
        if request.headers['apikey'].startswith('sb_secret_'):
            assert 'authorization' not in request.headers
        else:
            assert request.headers['apikey'] == 'private-storage-key'
            assert request.headers['authorization'] == 'Bearer private-storage-key'
        calls.append(request)
        if failures:
            failures.pop()
            return httpx.Response(503)
        path = request.url.path
        if request.method == 'POST':
            objects[path.removeprefix('/storage/v1/object/')] = request.content
            return httpx.Response(200, json={'Key': path})
        if request.method == 'DELETE':
            import json
            for path in json.loads(request.content)['prefixes']:
                objects.pop(f'muselly-inspirations/{path}', None)
            return httpx.Response(200, json=[])
        key = path.removeprefix('/storage/v1/object/authenticated/')
        return httpx.Response(200, content=objects[key]) if key in objects else httpx.Response(404)

    settings = Settings(_env_file=None, supabase_url='https://test.supabase.co', supabase_publishable_key='test-public-key', supabase_service_role_key='private-storage-key')
    app = create_app(settings, auth_transport=httpx.MockTransport(transport), public_directory=tmp_path)

    def override():
        with Session(database[0]) as db:
            yield db

    app.dependency_overrides[get_db] = override
    with TestClient(app) as c:
        c.storage_objects, c.storage_failures, c.storage_calls = objects, failures, calls
        yield c


def answers():
    return {q['id']: {'choices': [q['options'][0]['id']]} for q in QUESTIONS if not q['optional']}


def image_bytes(format='PNG'):
    output = BytesIO()
    Image.new('RGB', (20, 30), '#e88ca4').save(output, format=format)
    return output.getvalue()


def upload(client, id=None, token='user-a', data=None, type='image/png', name='look.png'):
    return client.put(f'/api/onboarding/images/{id or uuid4()}', headers={**headers(token), 'Content-Type': type, 'X-Filename': name}, content=data if data is not None else image_bytes())


def test_drafts_restore_location_and_other_with_owner_isolation(client):
    assert client.get('/api/onboarding').status_code == 401
    assert client.put('/api/onboarding', json={'answers': {}}).status_code == 401
    assert client.get('/api/onboarding', headers=headers()).json()['answers'] == {}
    draft = {'q1': {'choices': ['other'], 'other': 'Clothes for performances'}, 'q20': {'location': 'Mumbai, India'}, 'q7': {'choices': ['o2'], 'text': ['Lorde', 'The Strokes']}}
    saved = client.put('/api/onboarding', headers=headers(), json={'answers': draft, 'position': 7})
    assert saved.status_code == 200
    assert saved.json()['created_at'] and saved.json()['updated_at']
    restored = client.get('/api/onboarding', headers=headers()).json()
    assert restored['position'] == 7
    assert restored['answers']['q20']['location'] == 'Mumbai, India'
    assert restored['answers']['q1']['other'] == 'Clothes for performances'
    assert client.get('/api/onboarding', headers=headers('user-b')).json()['answers'] == {}
    assert client.put('/api/onboarding', headers=headers(), json={'answers': draft, 'user_id': 'forged'}).status_code == 422


@pytest.mark.parametrize('invalid', [
    {'q999': {'choices': []}}, {'q1': {'choices': ['unknown']}},
    {'q1': {'choices': ['o1', 'o2']}}, {'q5': {'choices': ['o1', 'o1']}},
    {'q9': {'choices': ['o1', 'o2', 'o3', 'o4']}},
    {'q19': {'choices': ['o1', 'o2', 'o3', 'other'], 'other': 'All'}},
    {'q15': {'choices': ['none', 'o1']}}, {'q1': {'other': 'Custom'}},
    {'q7': {'text': ['a' * 101]}}, {'q20': {'location': 'a' * 201}},
    {'q1': {'location': 'Unexpected'}}, {'q5': {'text': ['Unexpected']}},
])
def test_backend_validates_choices_limits_and_text(client, invalid):
    assert client.put('/api/onboarding', headers=headers(), json={'answers': invalid}).status_code == 422


def test_upload_validation_storage_failure_retry_replacement_and_removal(client):
    id = uuid4()
    assert upload(client, id, data=b'not an image').status_code == 422
    assert upload(client, data=image_bytes(), type='image/gif', name='x.gif').status_code == 422
    assert upload(client, data=image_bytes(), type='image/jpeg', name='x.jpg').status_code == 422
    assert upload(client, data=b'x' * (LIMIT + 1)).status_code == 413
    assert not client.storage_objects
    client.storage_failures.append(True)
    assert upload(client, id).status_code == 503
    assert client.get('/api/onboarding', headers=headers()).json()['images'] == []
    saved = upload(client, id)
    assert saved.status_code == 200
    assert saved.json()['id'] == str(id)
    assert (saved.json()['width'], saved.json()['height']) == (20, 30)
    assert len(client.storage_objects) == 1
    assert all(path.startswith(f'muselly-inspirations/{USER_A}/{id}/') for path in client.storage_objects)
    assert client.get(f'/api/onboarding/images/{id}', headers=headers()).content == next(iter(client.storage_objects.values()))
    assert client.get(f'/api/onboarding/images/{id}').status_code == 401
    for method in ('get', 'delete'):
        assert getattr(client, method)(f'/api/onboarding/images/{id}', headers=headers('user-b')).status_code == 404
    assert upload(client, id, token='user-b').status_code == 404
    # Failed replacement preserves the previously saved image.
    client.storage_failures.append(True)
    assert upload(client, id, name='replacement.png').status_code == 503
    assert len(client.storage_objects) == 1
    assert client.get('/api/onboarding', headers=headers()).json()['images'][0]['filename'] == 'look.png'
    assert upload(client, id, name='replacement.png').status_code == 200
    assert len(client.storage_objects) == 1
    assert len(client.get('/api/onboarding', headers=headers()).json()['images']) == 1
    client.storage_failures.append(True)
    assert client.delete(f'/api/onboarding/images/{id}', headers=headers()).status_code == 503
    assert len(client.get('/api/onboarding', headers=headers()).json()['images']) == 1
    assert client.delete(f'/api/onboarding/images/{id}', headers=headers()).status_code == 200
    assert not client.storage_objects
    assert client.get(f'/api/onboarding/images/{id}', headers=headers()).status_code == 404


@pytest.mark.parametrize('format,type,name', [('JPEG','image/jpeg','photo.jpeg'), ('PNG','image/png','photo.png'), ('WEBP','image/webp','photo.webp')])
def test_supported_image_types(client, format, type, name):
    assert upload(client, data=image_bytes(format), type=type, name=name).status_code == 200


def test_completion_requires_saved_answers_and_five_to_ten_images(client):
    assert client.post('/api/onboarding/complete').status_code == 401
    assert client.post('/api/onboarding/complete', headers=headers()).status_code == 422
    full = answers()
    full['q1'] = {'choices': ['other'], 'other': ''}
    assert client.put('/api/onboarding', headers=headers(), json={'answers': full}).status_code == 200  # Drafts can be incomplete.
    assert client.post('/api/onboarding/complete', headers=headers()).status_code == 422
    full['q1']['other'] = 'Stage outfits'
    assert client.put('/api/onboarding', headers=headers(), json={'answers': full}).status_code == 200
    ids = []
    for _ in range(4):
        result = upload(client)
        assert result.status_code == 200
        ids.append(result.json()['id'])
    assert client.post('/api/onboarding/complete', headers=headers()).status_code == 422
    assert upload(client).status_code == 200
    complete = client.post('/api/onboarding/complete', headers=headers())
    assert complete.status_code == 200
    completed_at = complete.json()['completed_at']
    assert completed_at
    assert complete.json()['position'] == len(QUESTIONS)
    assert len(complete.json()['images']) == 5
    assert client.get('/api/onboarding', headers=headers()).json()['completed_at'] == completed_at
    assert client.post('/api/onboarding/complete', headers=headers()).json()['completed_at'] == completed_at
    assert client.get('/api/onboarding', headers=headers('user-b')).json()['completed_at'] is None
    for _ in range(5):
        assert upload(client).status_code == 200
    assert upload(client).status_code == 422
    assert len(client.storage_objects) == 10
    assert upload(client, ids[0], name='new.png').status_code == 200  # Replacement at cap.
    assert len(client.storage_objects) == 10
    for id in [i['id'] for i in client.get('/api/onboarding', headers=headers()).json()['images']][:6]:
        assert client.delete(f'/api/onboarding/images/{id}', headers=headers()).status_code == 200
    assert client.get('/api/onboarding', headers=headers()).json()['completed_at'] is None
    assert client.post('/api/onboarding/complete', headers=headers()).status_code == 422


def test_storage_configuration_failure_keeps_incomplete(client):
    client.app.state.settings.supabase_service_role_key = ''
    assert upload(client).status_code == 503
    assert client.get('/api/onboarding', headers=headers()).json()['images'] == []


def test_missing_storage_object_or_outage_blocks_completion(client):
    client.put('/api/onboarding', headers=headers(), json={'answers': answers()})
    for _ in range(5):
        assert upload(client).status_code == 200
    client.storage_failures.append(True)
    assert client.post('/api/onboarding/complete', headers=headers()).status_code == 503
    assert client.get('/api/onboarding', headers=headers()).json()['completed_at'] is None
    path, content = next(iter(client.storage_objects.items()))
    del client.storage_objects[path]
    assert client.post('/api/onboarding/complete', headers=headers()).status_code == 503
    assert client.get('/api/onboarding', headers=headers()).json()['completed_at'] is None
    client.storage_objects[path] = content
    assert client.post('/api/onboarding/complete', headers=headers()).status_code == 200


def test_modern_secret_key_uses_apikey_header_without_bearer(client):
    client.app.state.settings.supabase_secret_key = 'sb_secret_test_backend_key'
    assert upload(client).status_code == 200
    assert client.storage_calls[-1].headers['apikey'] == 'sb_secret_test_backend_key'
    assert 'authorization' not in client.storage_calls[-1].headers


def test_public_key_cannot_be_used_as_storage_secret(client):
    client.app.state.settings.supabase_secret_key = 'sb_publishable_wrong_key'
    result = upload(client)
    assert result.status_code == 503
    assert 'secret key, not the public key' in result.json()['detail']
    assert not client.storage_calls


def test_legacy_anon_key_cannot_be_used_for_private_storage(client):
    import base64, json
    payload = base64.urlsafe_b64encode(json.dumps({'role':'anon'}).encode()).decode().rstrip('=')
    client.app.state.settings.supabase_service_role_key = f'header.{payload}.signature'
    result = upload(client)
    assert result.status_code == 503
    assert 'public/anon' in result.json()['detail']
    assert not client.storage_calls
