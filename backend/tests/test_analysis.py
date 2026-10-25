import json

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis import PROMPT_VERSION
from app.models import TasteAnalysisRun, TasteTest
from test_api import database, headers
from test_onboarding import client, answers, upload


def prepare(client):
    client.app.state.settings.gemini_api_key = 'test-gemini-secret'
    assert client.put('/api/onboarding', headers=headers(), json={'answers': answers()}).status_code == 200
    for _ in range(5):
        assert upload(client).status_code == 200
    return client.get('/api/onboarding', headers=headers()).json()['images']


def response_for(images):
    return {'summary': 'Relaxed neutral outfits.',
            'images': [{'image_id': i['id'], 'description': 'An outfit inspiration.',
                        'garments': ['trousers'], 'colors': ['cream'], 'patterns': [],
                        'silhouettes': ['relaxed'], 'layering_and_accessories': [],
                        'possible_aesthetics': ['minimal'], 'possible_materials': [],
                        'uncertainties': ['Exact fabric is unclear.']} for i in images],
            'recurring_visual_signals': [{'category': 'color', 'attribute': 'cream',
                                          'evidence_image_ids': [i['id'] for i in images],
                                          'explanation': 'Appears across the inspirations.'}],
            'questionnaire_interpretation': 'Keep the explicit dislikes as constraints.',
            'conflicts': [], 'limitations': ['Visual interpretations can be wrong.']}


def mock_gemini(client, images, *, status=200, result=None, finish='STOP'):
    calls = []

    def transport(request):
        calls.append(request)
        return httpx.Response(status, json={
            'candidates': [{'finishReason': finish, 'content': {'parts': [{'text': json.dumps(result if result is not None else response_for(images))}]}}],
            'usageMetadata': {'promptTokenCount': 200, 'candidatesTokenCount': 100, 'totalTokenCount': 300}})

    client.app.state.analysis_client = httpx.Client(transport=httpx.MockTransport(transport))
    return calls


def test_analysis_requires_authentication_and_valid_saved_inputs(client):
    assert client.get('/api/onboarding/analysis').status_code == 401
    assert client.post('/api/onboarding/analysis').status_code == 401
    assert client.post('/api/onboarding/analysis', headers=headers()).status_code == 503
    client.app.state.settings.gemini_api_key = 'test-key'
    assert client.post('/api/onboarding/analysis', headers=headers()).status_code == 422
    client.put('/api/onboarding', headers=headers(), json={'answers': answers()})
    for _ in range(4):
        upload(client)
    assert client.post('/api/onboarding/analysis', headers=headers()).status_code == 422
    assert client.get('/api/onboarding/analysis', headers=headers()).status_code == 404


def test_real_payload_persistence_cache_and_owner_isolation(client):
    images = prepare(client)
    calls = mock_gemini(client, images)
    result = client.post('/api/onboarding/analysis', headers=headers())
    assert result.status_code == 200, result.text
    body = result.json()
    assert body['status'] == 'succeeded' and body['stale'] is False
    assert body['prompt_version'] == PROMPT_VERSION
    assert body['result']['summary'] == 'Relaxed neutral outfits.'
    assert body['usage']['totalTokenCount'] == 300
    assert body['completed_at']
    assert len(body['sources']['images']) == 5
    assert body['sources']['answers'][0]['choices'] == ["Women's fashion"]
    payload = json.loads(calls[0].content)
    wire_schema = payload['generationConfig']['responseJsonSchema']
    assert wire_schema['properties']['images']['items']['properties']['image_id']['type'] == 'string'
    assert '$ref' not in json.dumps(wire_schema) and '"format"' not in json.dumps(wire_schema)
    assert calls[0].headers['x-goog-api-key'] == 'test-gemini-secret'
    assert 'key=' not in str(calls[0].url)
    assert len([p for p in payload['contents'][0]['parts'] if 'inlineData' in p]) == 5
    assert 'test-gemini-secret' not in result.text
    assert 'storage_path' not in result.text
    assert client.get('/api/onboarding/analysis', headers=headers()).json()['id'] == body['id']
    assert client.get('/api/onboarding/analysis', headers=headers('user-b')).status_code == 404
    assert client.post('/api/onboarding/analysis', headers=headers()).json()['id'] == body['id']
    assert len(calls) == 1  # A matching successful snapshot is reused without another charge.
    assert client.post('/api/onboarding/analysis?force=true', headers=headers()).status_code == 200
    assert len(calls) == 2


def test_answer_and_image_changes_mark_results_stale(client):
    images = prepare(client)
    mock_gemini(client, images)
    assert client.post('/api/onboarding/analysis', headers=headers()).status_code == 200
    changed = answers()
    changed['q1'] = {'choices': ['o2']}
    client.put('/api/onboarding', headers=headers(), json={'answers': changed})
    assert client.get('/api/onboarding/analysis', headers=headers()).json()['stale'] is True
    assert client.post('/api/onboarding/analysis', headers=headers()).json()['stale'] is False
    assert upload(client, id=images[0]['id'], name='replacement.png').status_code == 200
    assert client.get('/api/onboarding/analysis', headers=headers()).json()['stale'] is True


def test_failed_regeneration_preserves_previous_success_for_only_its_owner(client):
    images = prepare(client)
    mock_gemini(client, images)
    success = client.post('/api/onboarding/analysis', headers=headers()).json()
    mock_gemini(client, images, status=503)
    assert client.post('/api/onboarding/analysis?force=true', headers=headers()).status_code == 503
    latest = client.get('/api/onboarding/analysis', headers=headers()).json()
    assert latest['status'] == 'failed'
    assert latest['previous_successful']['id'] == success['id']
    assert latest['previous_successful']['result'] == success['result']
    assert latest['previous_successful']['stale'] is False
    assert client.get('/api/onboarding/analysis', headers=headers('user-b')).status_code == 404


@pytest.mark.parametrize('provider_status,expected', [(429, 429), (403, 503), (404, 503), (400, 502), (500, 503), (503, 503)])
def test_provider_errors_are_saved_without_a_fabricated_result(client, provider_status, expected):
    images = prepare(client)
    mock_gemini(client, images, status=provider_status)
    assert client.post('/api/onboarding/analysis', headers=headers()).status_code == expected
    failed = client.get('/api/onboarding/analysis', headers=headers()).json()
    assert failed['status'] == 'failed'
    assert failed['result'] is None and failed['error']
    mock_gemini(client, images)
    assert client.post('/api/onboarding/analysis', headers=headers()).status_code == 200


@pytest.mark.parametrize('invalid', ['missing-image', 'unknown-evidence', 'unknown-question', 'blocked', 'bad-schema'])
def test_rejects_invalid_or_ungrounded_model_results(client, invalid):
    images = prepare(client)
    result = response_for(images)
    if invalid == 'missing-image':
        result['images'][-1] = result['images'][0]
    elif invalid == 'unknown-evidence':
        result['recurring_visual_signals'][0]['evidence_image_ids'] = ['11111111-1111-4111-8111-111111111111']
    elif invalid == 'bad-schema':
        result = {'summary': 'Made-up partial result'}
    elif invalid == 'unknown-question':
        result['conflicts'] = [{'question_id': 'q999', 'evidence_image_ids': [images[0]['id']],
                                'description': 'Unsupported question.', 'resolution': 'Keep preferences.'}]
    mock_gemini(client, images, result=result, finish='SAFETY' if invalid == 'blocked' else 'STOP')
    assert client.post('/api/onboarding/analysis', headers=headers()).status_code == 502
    assert client.get('/api/onboarding/analysis', headers=headers()).json()['result'] is None


def test_missing_storage_never_calls_gemini_and_running_requests_do_not_duplicate(client, database):
    images = prepare(client)
    calls = mock_gemini(client, images)
    client.storage_objects.clear()
    assert client.post('/api/onboarding/analysis', headers=headers()).status_code == 503
    assert not calls
    with Session(database[0]) as db:
        run = db.scalar(select(TasteAnalysisRun))
        run.status = 'running'
        db.commit()
    assert client.post('/api/onboarding/analysis', headers=headers()).status_code == 409
    assert not calls


@pytest.mark.parametrize('exception,status', [(httpx.ReadTimeout('private diagnostic'), 504), (httpx.ConnectError('private diagnostic'), 503)])
def test_network_errors_are_sanitized_and_retryable(client, exception, status):
    images = prepare(client)

    def transport(request):
        raise exception

    client.app.state.analysis_client = httpx.Client(transport=httpx.MockTransport(transport))
    response = client.post('/api/onboarding/analysis', headers=headers())
    assert response.status_code == status
    assert 'private diagnostic' not in response.text
    assert client.get('/api/onboarding/analysis', headers=headers()).json()['status'] == 'failed'
    mock_gemini(client, images)
    assert client.post('/api/onboarding/analysis', headers=headers()).status_code == 200


def test_editing_during_analysis_preserves_snapshot_and_marks_result_stale(client, database, monkeypatch):
    images = prepare(client)

    def generate(request, sources, image_inputs):
        with Session(database[0]) as db:
            run = db.scalar(select(TasteAnalysisRun))
            profile = db.get(TasteTest, run.user_id)
            profile.answers = {**profile.answers, 'q1': {'choices': ['o2']}}
            db.commit()
        return response_for(images), {}

    monkeypatch.setattr('app.analysis.generate_analysis', generate)
    result = client.post('/api/onboarding/analysis', headers=headers())
    assert result.status_code == 200
    assert result.json()['stale'] is True
    assert result.json()['sources']['answers'][0]['choices'] == ["Women's fashion"]
