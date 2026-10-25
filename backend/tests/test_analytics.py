from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.enrichment import snapshot
from app.models import TasteAffinityDismissal, TasteEnrichmentRun
from test_api import client, database, headers, USER_A


def product(path='one'):
    return {'title': 'Blue dress', 'url': 'https://www.myntra.com/' + path, 'price': '1200', 'brand': 'COS'}


def test_analytics_is_authenticated_read_only_and_reports_real_zero_counts(client):
    assert client.get('/api/onboarding/analytics').status_code == 401
    data = client.get('/api/onboarding/analytics', headers=headers()).json()
    assert data['shopping']['refined_products'] == 0
    assert data['shopping']['saved_products'] == 0
    assert data['qloo']['status'] == 'not_generated'
    assert data['qloo']['brands'] == []


def test_analytics_counts_latest_corrections_and_isolates_accounts(client):
    for path, kind in [('one', 'wrong_color'), ('two', 'too_expensive')]:
        assert client.post('/api/extension/feedback', headers=headers(), json={'item': product(path), 'kind': kind}).status_code == 200
    client.post('/api/extension/feedback', headers=headers(), json={'item': product(), 'kind': 'more_like_this'})
    client.post('/api/extension/saved', headers=headers(), json={'title': 'Dress', 'url': product()['url']})
    data = client.get('/api/onboarding/analytics', headers=headers()).json()['shopping']
    assert data['refined_products'] == 2
    assert data['feedback_counts'] == {'more_like_this': 1, 'too_expensive': 1}
    assert data['saved_products'] == 1
    assert data['last_feedback_at']
    other = client.get('/api/onboarding/analytics', headers=headers('user-b')).json()
    assert other['shopping']['refined_products'] == 0
    assert other['shopping']['saved_products'] == 0


def test_analytics_deduplicates_qloo_inputs_honors_hidden_brands_and_labels_stale_runs(client, database):
    client.post('/api/extension/feedback', headers=headers(), json={'item': product(), 'kind': 'more_like_this'})
    visible, hidden, artist = str(uuid4()), str(uuid4()), str(uuid4())
    with Session(database[0]) as db:
        user = type('Owner', (), {'id': UUID(USER_A)})()
        sources, fingerprint = snapshot(db, user, client.app.state.settings)
        run = TasteEnrichmentRun(id=uuid4(), user_id=user.id, source_hash=fingerprint, sources=sources,
            resolver_version='test', status='succeeded', completed_at=datetime.now(timezone.utc), result={
                'resolutions': [
                    {'kind': 'brand', 'status': 'resolved', 'input': 'COS', 'match': {'entity_id': visible}},
                    {'kind': 'brand', 'status': 'resolved', 'input': 'cos', 'match': {'entity_id': visible}},
                    {'kind': 'artist', 'status': 'resolved', 'input': 'An artist', 'match': {'entity_id': artist}},
                    {'kind': 'inspiration', 'status': 'resolved', 'input': 'The same artist', 'match': {'entity_id': artist}},
                    {'kind': 'tag', 'status': 'unsupported', 'input': 'Unresolved interest'},
                ], 'affinities': [{'entity_id': visible, 'name': 'Visible brand', 'rank': 2}, {'entity_id': hidden, 'name': 'Hidden brand', 'rank': 3}]})
        db.add(run)
        db.add(TasteAffinityDismissal(user_id=user.id, entity_id=UUID(hidden), name='Hidden brand'))
        db.commit()
        run_id = run.id
    data = client.get('/api/onboarding/analytics', headers=headers()).json()['qloo']
    assert data['stale'] is False
    assert data['input_counts'] == {'brand': 1, 'artist': 1}
    assert data['unresolved_count'] == 1
    assert [brand['name'] for brand in data['brands']] == ['Visible brand']
    assert client.get('/api/onboarding/analytics', headers=headers('user-b')).json()['qloo']['brands'] == []
    with Session(database[0]) as db:
        db.get(TasteEnrichmentRun, run_id).source_hash = 'outdated'
        db.commit()
    assert client.get('/api/onboarding/analytics', headers=headers()).json()['qloo']['stale'] is True
