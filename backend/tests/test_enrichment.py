from datetime import datetime, timedelta, timezone
from time import monotonic
from uuid import UUID

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TasteAffinityDismissal, TasteAnalysisRun, TasteEnrichmentRun, TasteTest
from app.qloo import QlooClient
from test_api import database, headers, USER_A
from test_onboarding import client, answers, upload

ZARA = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
COS = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'
ARTIST = 'cccccccc-cccc-4ccc-8ccc-cccccccccccc'


def saved_profile(client):
    data = answers()
    data['q20'] = {'location': 'Private city that must stay local'}
    client.put('/api/onboarding', headers=headers(), json={'answers': data})
    for _ in range(5):
        assert upload(client).status_code == 200
    assert client.post('/api/onboarding/complete', headers=headers()).status_code == 200
    client.app.state.settings.qloo_api_key = 'private-qloo-key'


def provider(client, *, status=200, search=None, insights=None, tags=None):
    calls = []
    def transport(request):
        calls.append(request)
        assert request.headers['x-api-key'] == 'private-qloo-key'
        assert request.url.host == 'api.qloo.com'
        if request.url.path == '/search':
            return httpx.Response(200, json={'results': search if search is not None else [
                {'entity_id': ZARA, 'name': 'Zara', 'types': ['urn:entity:brand']}]})
        if request.url.path == '/v2/tags':
            if request.url.params.get('filter.parents.types') == 'urn:entity:brand':
                return httpx.Response(200, json={'results': {'tags': [{'id': 'urn:tag:genre:brand:fashion', 'name': 'Fashion'}]}})
            return httpx.Response(200, json={'results': {'tags': tags or []}})
        assert request.url.path == '/v2/insights'
        assert request.url.params['filter.type'] == 'urn:entity:brand'
        return httpx.Response(status, json={'success': True, 'results': {'entities': insights if insights is not None else [
            {'entity_id': COS, 'name': 'COS', 'subtype': 'urn:entity:brand', 'score': .82,
             'tags': [{'id': 'urn:tag:genre:brand:fashion', 'name': 'Fashion'}]}]}})
    client.app.state.qloo = QlooClient(httpx.Client(transport=httpx.MockTransport(transport)))
    return calls


def test_auth_configuration_and_completion(client):
    for method in ('get', 'post'):
        assert getattr(client, method)('/api/onboarding/enrichment').status_code == 401
    assert client.put(f'/api/onboarding/enrichment/affinities/{COS}', json={'dismissed': True}).status_code == 401
    assert client.post('/api/onboarding/enrichment', headers=headers()).status_code == 422
    saved_profile(client)
    client.app.state.settings.qloo_api_key = ''
    assert client.post('/api/onboarding/enrichment', headers=headers()).status_code == 503
    assert client.get('/api/onboarding/enrichment', headers=headers()).status_code == 404


def test_provenance_cache_force_and_owner_isolation(client):
    saved_profile(client)
    calls = provider(client)
    response = client.post('/api/onboarding/enrichment', headers=headers())
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['status'] == 'succeeded' and not data['stale']
    assert data['sources']['profile_version'] == 'taste-profile-v1'
    affinity = data['result']['affinities'][0]
    assert (affinity['name'], affinity['category'], affinity['score']) == ('COS', 'fashion', .82)
    assert affinity['evidence_entity_ids'] == [ZARA]
    wire = '\n'.join(str(r.url) for r in calls)
    for private in ('Private', 'user-a', 'SHEIN', 'private-qloo-key'):
        assert private not in wire
    assert 'private-qloo-key' not in response.text
    count = len(calls)
    assert client.get('/api/onboarding/enrichment', headers=headers()).json()['id'] == data['id']
    assert client.post('/api/onboarding/enrichment', headers=headers()).json()['id'] == data['id']
    assert len(calls) == count
    assert client.get('/api/onboarding/enrichment', headers=headers('user-b')).status_code == 404
    assert client.post('/api/onboarding/enrichment?force=true', headers=headers()).status_code == 200
    assert len(calls) == count * 2  # Force refresh repeats lookups as well as Insights.


def test_identity_resolution_does_not_substitute_places_or_ambiguous_names(client):
    saved_profile(client)
    calls = provider(client, search=[{'entity_id': ZARA, 'name': 'Zara', 'subtype': 'urn:entity:place'}])
    data = client.post('/api/onboarding/enrichment', headers=headers()).json()
    assert data['result']['outcome'] == 'no-supported-signals'
    assert not any(r.url.path == '/v2/insights' for r in calls)
    provider(client, search=[{'entity_id': ZARA, 'name': 'Zara', 'subtype': 'urn:entity:brand'},
                             {'entity_id': COS, 'name': 'Zara', 'subtype': 'urn:entity:brand'}])
    data = client.post('/api/onboarding/enrichment?force=true', headers=headers()).json()
    assert data['result']['resolutions'][0]['status'] == 'ambiguous'
    assert data['result']['affinities'] == []


def test_aliases_tags_named_interests_and_honest_categories(client):
    saved_profile(client)
    profile = client.get('/api/onboarding', headers=headers()).json()
    profile['answers']['q7']['text'] = ['T. Swift']
    client.put('/api/onboarding', headers=headers(), json={'answers': profile['answers']})
    calls = provider(client, search=[{'entity_id': ZARA, 'name': 'ZARA', 'subtype': 'urn:entity:brand'},
        {'entity_id': ARTIST, 'name': 'Taylor Swift', 'subtype': 'urn:entity:artist', 'properties': {'akas': [{'value': 'T. Swift'}]}}],
        tags=[{'id': 'urn:tag:genre:music:pop', 'name': 'Pop'}],
        insights=[{'entity_id': COS, 'name': 'Unknown category brand', 'subtype': 'urn:entity:brand'}])
    data = client.post('/api/onboarding/enrichment', headers=headers()).json()
    params = next(r.url.params for r in calls if r.url.path == '/v2/insights')
    assert set(params['signal.interests.entities'].split(',')) == {ZARA, ARTIST}
    assert params['signal.interests.tags'] == 'urn:tag:genre:music:pop'
    assert data['result']['affinities'] == []  # Unverified fashion categories are not shown.


def test_empty_results_and_unsupported_interests(client):
    saved_profile(client)
    provider(client, insights=[])
    data = client.post('/api/onboarding/enrichment', headers=headers()).json()
    assert data['result']['outcome'] == 'no-affinities'
    provider(client, search=[])
    data = client.post('/api/onboarding/enrichment?force=true', headers=headers()).json()
    assert data['result']['outcome'] == 'no-supported-signals'
    assert data['result']['affinities'] == []


@pytest.mark.parametrize('status,expected', [(401, 503), (403, 503), (429, 429), (400, 502), (503, 503)])
def test_provider_failures_preserve_previous_success(client, status, expected):
    saved_profile(client)
    provider(client)
    first = client.post('/api/onboarding/enrichment', headers=headers()).json()
    calls = provider(client, status=status)
    response = client.post('/api/onboarding/enrichment?force=true', headers=headers())
    assert response.status_code == expected
    latest = client.get('/api/onboarding/enrichment', headers=headers()).json()
    assert latest['status'] == 'failed' and latest['result'] is None
    assert latest['previous_successful']['id'] == first['id']
    assert len([r for r in calls if r.url.path == '/v2/insights']) == (2 if status == 503 else 1)
    assert 'private-qloo-key' not in response.text


@pytest.mark.parametrize('bad', ['invalid-id', 'wrong-type', 'bad-score', 'bad-schema'])
def test_invalid_provider_output_is_rejected(client, bad):
    saved_profile(client)
    value = {'entity_id': COS, 'name': 'COS', 'subtype': 'urn:entity:brand'}
    if bad == 'invalid-id': value['entity_id'] = 'fabricated-id'
    elif bad == 'wrong-type': value['subtype'] = 'urn:entity:place'
    elif bad == 'bad-score': value['score'] = '82%'
    else: value.pop('name')
    provider(client, insights=[value])
    assert client.post('/api/onboarding/enrichment', headers=headers()).status_code == 502
    assert client.get('/api/onboarding/enrichment', headers=headers()).json()['status'] == 'failed'


def test_stale_inputs_concurrent_and_abandoned_runs(client, database):
    saved_profile(client)
    provider(client)
    first = client.post('/api/onboarding/enrichment', headers=headers()).json()
    profile = client.get('/api/onboarding', headers=headers()).json()
    profile['answers']['q15'] = {'choices': ['other'], 'other': 'No sequins'}
    client.put('/api/onboarding', headers=headers(), json={'answers': profile['answers']})
    assert client.get('/api/onboarding/enrichment', headers=headers()).json()['stale'] is True
    with Session(database[0]) as db:
        run = db.get(TasteEnrichmentRun, UUID(first['id']))
        run.status = 'running'
        db.commit()
    assert client.post('/api/onboarding/enrichment', headers=headers()).status_code == 409
    with Session(database[0]) as db:
        db.get(TasteEnrichmentRun, UUID(first['id'])).created_at = datetime.now(timezone.utc) - timedelta(minutes=3)
        db.commit()
    assert client.post('/api/onboarding/enrichment', headers=headers()).json()['stale'] is False


def test_dismissal_survives_refresh_is_private_and_restorable(client, database):
    saved_profile(client)
    provider(client)
    client.post('/api/onboarding/enrichment', headers=headers())
    path = f'/api/onboarding/enrichment/affinities/{COS}'
    assert client.put(path, headers=headers('user-b'), json={'dismissed': True}).status_code == 404
    hidden = client.put(path, headers=headers(), json={'dismissed': True}).json()
    assert hidden['result']['affinities'] == [] and hidden['dismissed'][0]['name'] == 'COS'
    assert client.post('/api/onboarding/enrichment?force=true', headers=headers()).json()['result']['affinities'] == []
    restored = client.put(path, headers=headers(), json={'dismissed': False}).json()
    assert restored['result']['affinities'][0]['name'] == 'COS' and restored['dismissed'] == []
    with Session(database[0]) as db:
        assert db.scalar(select(TasteAffinityDismissal)) is None


def test_editing_during_enrichment_marks_snapshot_stale(client, database):
    saved_profile(client)
    provider(client)
    original = client.app.state.qloo.enrich
    def during_request(*args, **kwargs):
        with Session(database[0]) as db:
            profile = db.get(TasteTest, UUID(USER_A))
            profile.answers = {**profile.answers, 'q1': {'choices': ['o2']}}
            db.commit()
        return original(*args, **kwargs)
    client.app.state.qloo.enrich = during_request
    data = client.post('/api/onboarding/enrichment', headers=headers()).json()
    assert data['stale'] is True
    assert data['sources']['questionnaire'][0]['values'][0]['original'] == "Women's fashion"


def test_timeouts_and_schema_drift_are_sanitized(client):
    saved_profile(client)
    def failure(request):
        raise httpx.ReadTimeout('secret diagnostic with token')
    client.app.state.qloo = QlooClient(httpx.Client(transport=httpx.MockTransport(failure)))
    response = client.post('/api/onboarding/enrichment', headers=headers())
    assert response.status_code == 504 and 'secret diagnostic' not in response.text
    client.app.state.qloo = QlooClient(httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={'unexpected': []}))))
    assert client.post('/api/onboarding/enrichment', headers=headers()).status_code == 502


def test_deadline_and_refresh_rate_limit(client):
    saved_profile(client)
    provider(client)
    for _ in range(3):
        assert client.post('/api/onboarding/enrichment?force=true', headers=headers()).status_code == 200
    assert client.post('/api/onboarding/enrichment?force=true', headers=headers()).status_code == 429
    with pytest.raises(Exception) as failure:
        client.app.state.qloo.get(client.app.state.settings, '/search', {'query': 'Zara'}, deadline=monotonic() - 1)
    assert failure.value.status_code == 504


def test_normalized_image_signals_keep_evidence_and_new_analysis_invalidates_enrichment(client):
    from test_analysis import mock_gemini, response_for
    saved_profile(client)
    images = client.get('/api/onboarding', headers=headers()).json()['images']
    client.app.state.settings.gemini_api_key = 'test-gemini-secret'
    result = response_for(images)
    result['recurring_visual_signals'].append({**result['recurring_visual_signals'][0], 'attribute': ' Cream '})
    mock_gemini(client, images, result=result)
    first_analysis = client.post('/api/onboarding/analysis', headers=headers()).json()
    provider(client)
    data = client.post('/api/onboarding/enrichment', headers=headers()).json()
    signals = data['sources']['visual_signals']
    assert len(signals) == 1 and signals[0]['normalized'] == 'cream'
    assert signals[0]['original_labels'] == ['cream', ' Cream ']
    assert len(signals[0]['evidence_image_ids']) == 5
    assert signals[0]['uncertainties'] == ['Exact fabric is unclear.']
    assert data['sources']['analysis_id'] == first_analysis['id']
    assert client.post('/api/onboarding/analysis?force=true', headers=headers()).status_code == 200
    assert client.get('/api/onboarding/enrichment', headers=headers()).json()['stale'] is True
    profile = client.get('/api/onboarding', headers=headers()).json()
    profile['answers']['q15'] = {'choices': ['o2']}
    client.put('/api/onboarding', headers=headers(), json={'answers': profile['answers']})
    data = client.post('/api/onboarding/enrichment', headers=headers()).json()
    assert data['sources']['analysis_stale'] is True
    assert data['sources']['visual_signals'] == []


def test_cache_is_scoped_to_api_host_and_key_and_malformed_responses_do_not_poison_it(client):
    settings = client.app.state.settings
    settings.qloo_api_key = 'first-key'
    calls, broken = [], [True]
    def transport(request):
        calls.append(request)
        return httpx.Response(200, json={'results': [{'entity_id': ZARA, 'name': 'Zara',
            'types': ['urn:entity:brand'], 'properties': {'akas': 'invalid' if broken[0] else []}}]})
    qloo = QlooClient(httpx.Client(transport=httpx.MockTransport(transport)))
    signal = {'question_id': 'q13', 'input': 'Zara', 'kind': 'brand'}
    with pytest.raises(Exception) as failure:
        qloo.resolve(settings, signal, monotonic() + 5)
    assert failure.value.status_code == 502
    broken[0] = False
    assert qloo.resolve(settings, signal, monotonic() + 5)['status'] == 'resolved'
    assert qloo.resolve(settings, signal, monotonic() + 5)['status'] == 'resolved'
    assert len(calls) == 2
    settings.qloo_api_key = 'second-key'
    qloo.resolve(settings, signal, monotonic() + 5)
    settings.qloo_base_url = 'https://hackathon.api.qloo.com'
    qloo.resolve(settings, signal, monotonic() + 5)
    assert len(calls) == 4


def test_search_404_is_an_unsupported_signal_and_cap_prevents_unbounded_lookups(client):
    client.app.state.settings.qloo_api_key = 'key'
    calls = []
    def transport(request):
        calls.append(request)
        return httpx.Response(404)
    qloo = QlooClient(httpx.Client(transport=httpx.MockTransport(transport)))
    signals = [{'question_id': 'q13', 'input': f'Unknown {i}', 'kind': 'brand'} for i in range(30)]
    result = qloo.enrich(client.app.state.settings, signals)
    assert len(calls) == 24
    assert len([r for r in result['resolutions'] if r['status'] == 'deferred']) == 6
    assert result['outcome'] == 'no-supported-signals'
    qloo.enrich(client.app.state.settings, signals)
    assert len(calls) == 24



def test_live_music_taxonomy_resolves_context_and_returns_filtered_fashion_brands(client):
    import json
    from pathlib import Path
    fixture = json.loads((Path(__file__).parent / 'fixtures/qloo_music_fashion.json').read_text())
    saved_profile(client)
    profile = client.get('/api/onboarding', headers=headers()).json()
    profile['answers']['q13'] = {'choices': ['o7', 'o8']}
    profile['answers']['q7'] = {'choices': ['o4', 'o5']}
    profile['answers']['q14'] = {'choices': ['o3']}
    client.put('/api/onboarding', headers=headers(), json={'answers': profile['answers']})
    calls = provider(client, search=[], tags=fixture['music_tags'], insights=fixture['fashion_entities'])
    data = client.post('/api/onboarding/enrichment', headers=headers()).json()
    by_input = {r['input']: r for r in data['result']['resolutions']}
    assert by_input['K-pop']['match']['tag_id'] == 'urn:tag:genre:music:k_pop'
    assert by_input['Bollywood']['match']['tag_id'] == 'urn:tag:genre:music:bollywood'
    assert by_input['Urbanic']['status'] == by_input['Savana']['status'] == 'unsupported'
    assert data['result']['outcome'] == 'enriched'
    assert {a['name'] for a in data['result']['affinities']} == {'Robert Naorem', 'AVIA'}
    assert all(a['affinity'] > 0 and a['category'] == 'fashion' for a in data['result']['affinities'])
    insights = next(r for r in calls if r.url.path == '/v2/insights')
    assert insights.url.params['filter.tags'] == 'urn:tag:genre:brand:fashion'
    assert insights.url.params['operator.filter.tags'] == 'union'
    assert all(r.url.params['filter.tag.types'] == 'urn:tag:genre:music' for r in calls
               if r.url.path == '/v2/tags' and r.url.params.get('filter.query') in ('K Pop', 'Bollywood'))


def test_music_ambiguity_within_the_same_namespace_is_not_guessed(client):
    saved_profile(client)
    calls = provider(client, search=[], tags=[
        {'id': 'urn:tag:genre:music:pop_a', 'name': 'Pop'},
        {'id': 'urn:tag:genre:music:pop_b', 'name': 'Pop'},
        {'id': 'urn:tag:decor:qloo:pop', 'name': 'Pop'},
    ])
    data = client.post('/api/onboarding/enrichment', headers=headers()).json()
    result = next(r for r in data['result']['resolutions'] if r['input'] == 'Pop')
    assert result['status'] == 'ambiguous'
    assert len(result['candidates']) == 2
    assert not any(r.url.path == '/v2/insights' for r in calls)


def test_force_refresh_retries_previously_unsupported_lookups(client):
    saved_profile(client)
    calls, available = [], [False]
    def transport(request):
        calls.append(request)
        if request.url.path == '/search':
            return httpx.Response(200, json={'results': [
                {'entity_id': ZARA, 'name': 'Zara', 'types': ['urn:entity:brand']}] if available[0] else []})
        if request.url.path == '/v2/tags':
            return httpx.Response(200, json={'results': {'tags': [
                {'id': 'urn:tag:genre:brand:fashion', 'name': 'Fashion'}
            ] if request.url.params.get('filter.parents.types') else []}})
        return httpx.Response(200, json={'results': {'entities': [
            {'entity_id': COS, 'name': 'COS', 'subtype': 'urn:entity:brand', 'tags': [
                {'tag_id': 'urn:tag:genre:brand:fashion', 'name': 'Fashion'}], 'query': {'affinity': .8}}]}})
    client.app.state.qloo = QlooClient(httpx.Client(transport=httpx.MockTransport(transport)))
    assert client.post('/api/onboarding/enrichment', headers=headers()).json()['result']['outcome'] == 'no-supported-signals'
    available[0] = True
    data = client.post('/api/onboarding/enrichment?force=true', headers=headers()).json()
    assert data['result']['affinities'][0]['name'] == 'COS'
    assert len([r for r in calls if r.url.path == '/search']) == 2


def test_liked_product_brands_become_qloo_signals_on_explicit_refresh(client):
    saved_profile(client)
    calls = provider(client)
    assert client.post('/api/onboarding/enrichment', headers=headers()).status_code == 200
    previous_count = len(calls)
    product = {'title':'Dress', 'brand':'COS', 'url':'https://www.myntra.com/cos-dress', 'price':'1200'}
    assert client.post('/api/extension/feedback', headers=headers(), json={'item':product,'kind':'more_like_this'}).status_code == 200
    assert len(calls) == previous_count
    current = client.get('/api/onboarding/enrichment', headers=headers()).json()
    assert current['stale'] is True
    refreshed = client.post('/api/onboarding/enrichment', headers=headers()).json()
    assert any(s['input'] == 'COS' and s['question_id'] == 'product_feedback' for s in refreshed['sources']['signals'])
