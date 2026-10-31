"""General routing boundaries and preserved live-output regressions; no API calls."""
import json
from pathlib import Path
from types import SimpleNamespace as NS
import pytest
from data_governance.response_gate import evaluate


def runtime():
    return NS(context=NS(identity=NS(operator_id='op'), active_thread=NS(thread_id='t')))


@pytest.mark.parametrize('input_text,response', [
    ('Greetings', '1. Interpretation\nYou are starting a conversation.\n2. Reasoning\nWe can talk.\n3. Conclusion\nWhat would you like to discuss?'),
    ('I feel tired', 'That sounds exhausting. Would you like to talk about it?'),
    ('Explain sequences', 'Lists are mutable. Tuples are immutable.'),
    ('Improve that', 'Which part would you like to improve?'),
    ('Plan a restful weekend', 'You could read a book or take a walk.'),
])
def test_conversation_is_not_execution(input_text, response):
    result = evaluate(runtime(), input_text, response)
    assert result['allowed'] and result['publication_scope'] == 'CONVERSATION_ONLY'
    assert result['execution_authority_granted'] is False


@pytest.mark.parametrize('text', ['Deploy it somewhere', 'Erase the database',
    'Authorize any future action', 'The artifact passed validation', 'You may release the funds',
    'The build completed successfully', 'I saved your fact to persistent memory'])
def test_consequential_ambiguity_still_requires_governance(text):
    assert not evaluate(runtime(), text, text)['allowed']


def test_explicit_material_context_cannot_be_overridden_by_unknown_output():
    r = runtime()
    r.context.material_response_claim = {'claim_id': 'unvalidated'}
    assert not evaluate(r, 'Proceed', 'Unclear result')['allowed']


def test_absent_evidence_disclosure_is_not_completion_claim():
    text = ('You are requesting evidence that the build passed.\n'
            'I do not have evidence to confirm the build passed.')
    assert evaluate(runtime(), 'Show evidence', text)['allowed']
    assert not evaluate(runtime(), 'Show evidence', text + '\nThe build passed validation.')['allowed']


@pytest.mark.parametrize('text', ['Explain this and then deploy it',
    'I cannot approve it and then grant administrator privileges'])
def test_conversational_or_negative_prefix_cannot_hide_action(text):
    assert not evaluate(runtime(), 'Conversation', text)['allowed']


def test_thread_command_custody_roundtrip(tmp_path):
    from interactive_mode_ai import ModeRuntime
    from memory.thread_store import ThreadStore
    r = ModeRuntime.__new__(ModeRuntime)
    r.thread_store = ThreadStore(str(tmp_path / 'threads'))
    thread = r.thread_store.create_thread('op')
    r.context = NS(active_thread=thread)
    fact = 'Do not save to persistent memory: my favorite color is orange.'
    r._record_command_exchange(fact, 'No persistent save.')
    loaded = r.thread_store.load_thread('op', thread.thread_id)
    assert loaded.messages[0].content == fact
    assert loaded.messages[1].content == 'No persistent save.'
    assert not (tmp_path / 'persistent_memory').exists()


def test_build_clarification_retains_scope_and_resumes(tmp_path):
    from tests.test_execution_spine import runtime, envelope
    r = runtime(tmp_path)
    first = r.handle_build_request('Build a text editor application')
    assert first['clarification_required'] and not first['execution_attempted']
    assert 'where' in first['reasons'][0]
    assert r.handle_build_request('Let us discuss dinner instead') is None
    complete = envelope(tmp_path / 'output')
    # Existing execute owns all validation/authorization; intake cannot bypass it.
    seen = []
    r.build_runtime.execute = lambda e: seen.append(e) or {'state': 'SPECIFICATION_READY'}
    r.handle_build_request('/build clarify ' + json.dumps({'request': complete['request']}))
    assert not seen
    result = r.handle_build_request('/build clarify ' + json.dumps({
        'understanding': complete['understanding'], 'authorization': complete['authorization']}))
    assert result['state'] == 'SPECIFICATION_READY' and seen == [complete]
    assert r.context.build_clarification is None


def test_clarification_does_not_fabricate_authorization(tmp_path):
    from tests.test_execution_spine import runtime, envelope
    r = runtime(tmp_path)
    r.handle_build_request('Build an editor')
    e = envelope(tmp_path / 'output')
    e['authorization']['decision'] = 'DENY'
    result = r.handle_build_request('/build clarify ' + json.dumps(e))
    assert result['state'] == 'SPECIFICATION_NOT_READY'
    assert not result['execution_attempted']
    assert any('authorization' in reason for reason in result['reasons'])


def test_clarified_request_reaches_real_specification_and_builder(tmp_path):
    from tests.test_execution_spine import runtime, envelope
    r = runtime(tmp_path)
    e = envelope(tmp_path / 'output')
    r.handle_build_request(e['request']['operator_input'])
    first = r.handle_build_request('/build clarify ' + json.dumps({'request': e['request']}))
    assert first['clarification_required'] and not first['execution_attempted']
    out = r.handle_build_request('/build clarify ' + json.dumps({
        'understanding': e['understanding'], 'authorization': e['authorization']}))
    assert out['state'] == 'BUILD_PASS_RP_PENDING'
    assert out['specification']['metadata']['operator_authorization'] == e['authorization']
    assert out['specification']['metadata']['governed_understanding'] == out['understanding']
    assert out['observation_ids'] and out['build']['validation_status'] == 'PASS'
    assert (tmp_path / 'output' / 'calculator.py').is_file()
