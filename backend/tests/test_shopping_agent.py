import json
from uuid import UUID

from sqlalchemy.orm import Session
from app.models import ShoppingAgentSession
from app.shopping_agent import Interpretation, merge_request
from test_api import database, headers, USER_A
from test_onboarding import client
from test_myntra_shopping import setup, seed_cultural_link


def run(client, message='', **extra):
    response = client.post('/api/shop/agent', headers=headers(), json={'message': message, **extra})
    assert response.status_code == 200, response.text
    events = [json.loads(line) for line in response.text.splitlines()]
    assert events[-1]['type'] == 'result', events
    return events, events[-1]['result']


def test_corrections_preserve_budget_and_hard_constraints():
    state = merge_request('cream dress under 1000 without bodycon', {}, None)
    result = merge_request('more floral and cheaper', state, Interpretation(preferred=['floral'], cheaper=True))
    assert result['wanted']['max_price'] == 1000
    assert result['wanted']['categories'] == ['Dresses']
    assert result['wanted']['colors'] == ['cream']
    assert 'bodycon' in result['wanted']['excluded']
    assert result['preferred'] == ['floral'] and result['cheaper']
    assert merge_request('under 800', result, None)['wanted']['max_price'] == 800


def test_agent_streams_real_stages_and_keeps_owner_scoped_context(client, database, tmp_path):
    setup(client, tmp_path)
    events, first = run(client, 'dress under 1000')
    assert len([event for event in events if event['type'] == 'progress']) >= 4
    assert first['total'] == 2
    agent = first['agent']
    _, revised = run(client, 'without red', session_id=agent['session_id'], revision=agent['revision'])
    assert [row['product_id'] for row in revised['products']] == ['101']
    assert revised['filters']['max_price'] == 1000
    response = client.post('/api/shop/agent', headers=headers('user-b'), json={
        'message': 'cheaper', 'session_id': agent['session_id'], 'revision': agent['revision']})
    assert response.status_code == 404
    assert client.post('/api/shop/agent', headers=headers(), json={
        'message': 'cheaper', 'session_id': agent['session_id'], 'revision': agent['revision']}).status_code == 409
    assert client.post('/api/shop/agent', json={'message': 'dress'}).status_code == 401


def test_qloo_is_expanded_when_its_first_brands_do_not_match(client, database, tmp_path):
    setup(client, tmp_path); seed_cultural_link(client, database)
    calls = []
    class Qloo:
        def get(self, settings, path, params, **kwargs):
            page = params.get('page', 1)
            calls.append((params['take'], page))
            if page == 1:
                return [{'name': f'Unsupported {i}', 'entity_id': f'first-{i}'} for i in range(50)]
            if page == 2:
                return [{'name': 'CultureBrand', 'entity_id': 'brand-id'}] + [
                    {'name': f'Unsupported next {i}', 'entity_id': f'next-{i}'} for i in range(49)]
            return []
    client.app.state.qloo = Qloo()
    events, result = run(client, 'dress under 1000')
    assert calls == [(50, 1), (50, 1), (50, 2), (50, 3)]
    assert result['agent']['action'] == 'expand_qloo'
    assert result['agent']['assessment']['qloo_matches'] == 1
    assert result['products'][0]['product_id'] == '101'
    assert any('Exploring more Qloo' in event.get('message', '') for event in events)


def test_empty_result_diagnoses_budget_without_relaxing_it(client, tmp_path):
    setup(client, tmp_path)
    _, result = run(client, 'floral dress under 500')
    assert result['products'] == [] and result['filters']['max_price'] == 500
    assert result['agent']['gap']['suggested_max_price'] == 900
    assert 'unchanged' in result['agent']['message']


def test_clarification_and_supported_fallback(client, tmp_path):
    setup(client, tmp_path)
    _, first = run(client, 'something nice')
    assert first['agent']['question'] is True
    _, result = run(client, 'office shirt under 1500', session_id=first['agent']['session_id'], revision=1)
    assert result['products'][0]['product_id'] == '103'
    assert result['agent']['mode'] == 'rules_fallback'


def test_model_can_choose_a_bounded_tool_and_cannot_change_budget(client, database, tmp_path, monkeypatch):
    from app import shopping_agent as agent_module
    setup(client, tmp_path); seed_cultural_link(client, database)
    class Qloo:
        def get(self, *args, **kwargs): return []
    client.app.state.qloo = Qloo()
    def model(request, schema, instruction, data, **kwargs):
        if schema is agent_module.Interpretation:
            return Interpretation(preferred=['floral', 'made-up-property'], categories=['Shoes'])
        return agent_module.Decision(action='finish')
    monkeypatch.setattr(agent_module, 'model_json', model)
    _, result = run(client, 'dress under 1000')
    assert result['filters']['max_price'] == 1000 and result['filters']['categories'] == ['Dresses']
    assert result['agent']['action'] == 'finish' and result['agent']['mode'] == 'model'
    assert result['products'][0]['product_id'] == '101'


def test_budget_suggestion_requires_explicit_confirmation(client, tmp_path):
    setup(client, tmp_path)
    _, first = run(client, 'floral dress under 500')
    agent = first['agent']
    _, accepted = run(client, 'yes', session_id=agent['session_id'], revision=agent['revision'])
    assert accepted['filters']['max_price'] == 900
    assert accepted['products'][0]['product_id'] == '101'


def test_palette_aliases_do_not_broaden_an_explicit_color():
    from app.myntra_shopping import intent
    assert intent('cream dress')['colors'] == ['cream']
    assert intent('pink dress')['colors'] == ['pink']
    assert intent('neutral dress')['colors'] == ['neutrals']


def test_pagination_preserves_conversation_revision(client, tmp_path):
    setup(client, tmp_path)
    _, first = run(client, 'dress under 1000')
    _, page = run(client, '', offset=24, session_id=first['agent']['session_id'], revision=1)
    assert page['products'] == [] and page['total'] == 2
    assert page['agent']['revision'] == 1


def test_agent_variety_never_overrides_highest_taste_percentage():
    from app.shopping_agent import diversify
    rows = [
        {'product_id': '1', 'brand': 'A', 'taste_match': 90},
        {'product_id': '2', 'brand': 'A', 'taste_match': 90},
        {'product_id': '3', 'brand': 'B', 'taste_match': 90},
        {'product_id': '4', 'brand': 'C', 'taste_match': 80},
    ]
    result = diversify(rows)
    assert [row['product_id'] for row in result] == ['1', '3', '2', '4']
    assert [row['taste_match'] for row in result] == [90, 90, 90, 80]


def test_request_and_correction_beat_qloo_but_qloo_still_personalizes_ties():
    from app.myntra_shopping import rank_catalog, intent
    from test_myntra_shopping import products
    rows = products()[:2]
    brands = {'other': {'name': 'Other', 'entity_id': 'qloo-brand'}}
    ranked = rank_catalog(rows, intent('dress under 1500'), [], [], brands, [],
        preferred=['floral'], focus_preferred=['floral'], request_first=True)
    assert [row['product_id'] for row in ranked] == ['101', '102']
    assert ranked[0]['taste_match'] > ranked[1]['taste_match']
    assert 'correction' in ranked[0]['why'][0]
    twin = {**rows[0], 'product_id': '105', 'brand': 'Other', 'price': 950}
    personalized = rank_catalog([rows[0], twin], intent('dress under 1500'), [], [], brands, [],
        preferred=['floral'], focus_preferred=['floral'], request_first=True)
    assert personalized[0]['product_id'] == '105'
    assert personalized[0]['qloo_brand'] is not None


def test_occasion_and_cheaper_priority_cannot_be_overridden_by_brand():
    from app.myntra_shopping import rank_catalog, intent
    from test_myntra_shopping import products
    rows = products()
    rows[2] = {**rows[2], 'brand': 'Unconnected', 'price': 1400}
    brands = {'other': {'name': 'Other'}}
    ranked = rank_catalog(rows, intent('office outfit under 1500'), [], [], brands, [], request_first=True)
    assert ranked[0]['product_id'] == '103'
    cheap = {**rows[0], 'product_id': '106', 'price': 250, 'brand': 'Unconnected'}
    ranked = rank_catalog([rows[0], cheap], intent('dress under 1500'), [], [], {'culturebrand': {'name': 'CultureBrand'}}, [],
        request_first=True, cheaper=True)
    assert ranked[0]['product_id'] == '106'
    assert ranked[0]['price'] == 250
    assert all(row['price'] <= 1500 for row in ranked)


def test_new_pattern_correction_replaces_conflicting_old_preference():
    previous = merge_request('floral dress under 1000', {}, Interpretation(preferred=['floral']))
    current = merge_request('solid instead', previous, Interpretation(preferred=['solid']))
    assert 'floral' not in current['wanted']['required']
    assert current['focus_preferred'] == ['solid']
    assert 'floral' not in current['preferred']
    assert current['wanted']['max_price'] == 1000


def test_model_cannot_turn_a_budget_ceiling_into_cheapest_first():
    state = merge_request('office outfit under 2000', {}, Interpretation(cheaper=True))
    assert state['cheaper'] is False
    assert merge_request('cheaper please', state, Interpretation(cheaper=False))['cheaper'] is True


def test_diversification_keeps_request_priority_even_when_percentages_round_equal():
    from app.shopping_agent import diversify
    rows = [
        {'product_id': '1', 'brand': 'A', 'taste_match': 90, '_request_priority': (2,)},
        {'product_id': '2', 'brand': 'A', 'taste_match': 90, '_request_priority': (2,)},
        {'product_id': '3', 'brand': 'B', 'taste_match': 90, '_request_priority': (1,)},
    ]
    assert [row['product_id'] for row in diversify(rows)] == ['1','2','3']
