from types import SimpleNamespace as NS

import pytest

from data_governance.response_claims import consequential
from integration.conversation_understanding import prepare, prompt_context
from tests.test_conversation_understanding import runtime


def test_failed_semantic_update_remains_visible_after_question(tmp_path):
    r = runtime(tmp_path)
    text = 'The visitor did not move the box.'
    r.context.active_thread.messages.append(NS(role='operator', content=text, message_id='m'))
    malformed = {'subject_id': 'arrival', 'edits': [
        {'operation': 'ADD', 'kind': 'FACT', 'quote': 'The box moved.', 'target_id': None}]}
    result = prepare(r, text, interpreter=lambda *_: (malformed, {}))
    assert result['state'] == 'FAILED'
    prepare(r, 'What is known?', interpreter=lambda *_: ({'subject_id': None, 'edits': []}, {}))
    assert 'not committed' in str(prompt_context(r))
    r.context.active_thread.thread_id = 'another-thread'
    assert 'not committed' not in str(prompt_context(r))


@pytest.mark.parametrize('text', [
    'No build is authorized.',
    'No build attempt has been executed.',
    'The completion checks that will demonstrate the build is successful.',
    'This does not specify how artifact existence is verified.',
    'Artifact existence is required to consider a build successful.',
])
def test_unperformed_operations_and_proof_obligations_are_not_success(text):
    assert not consequential(text)


@pytest.mark.parametrize('text', [
    'No build is authorized, but you may deploy it.',
    'No build is authorized, and you may execute it.',
    'The build completed.',
    'The source is authoritative.',
    'The completion checks passed.',
    'PENDING_VALIDATION. You may execute it.',
    'DISCONFIRMED. The build succeeded.',
])
def test_negative_or_pending_prefix_cannot_hide_positive_authority(text):
    assert consequential(text)


def test_grammatical_overlap_does_not_inject_unrelated_preference(tmp_path):
    from persistent_memory.tests.test_memory_injection import setup_context, save
    manager, _, _ = setup_context(tmp_path)
    save(manager, 'When evaluating a machine I care about actual artifacts rather than what it says.')
    assert manager.retrieve_memories('operator', query='A visitor waits because she heard something. When she arrives nobody is there but it is open.') == []
    assert len(manager.retrieve_memories('operator', query='What matters when evaluating a machine?')) == 1


def test_exclusive_output_correction_preserves_unrelated_prohibition():
    from understanding.declaration_delta import apply_delta
    from tests.test_declaration_delta import delta, edit, previous
    first=apply_delta(None, delta(edit('It only produces a summary.'), edit('Never execute commands.',kind='CONSTRAINT')),
                      text='It only produces a summary. Never execute commands.', source_reference='m1')
    target=first['declarations'][0]['id']
    result=apply_delta(previous(first),delta(edit('it can also produce an index','REPLACE',target),version=1),
                       text='Correction: it can also produce an index',source_reference='m2')
    assert [v['quote'] for v in result['declarations']]==['Never execute commands.','produces a summary.','it can also produce an index']
    assert result['amendments'][0]['prior']['id']==target
    with pytest.raises(ValueError):
        apply_delta(previous(first),delta(edit('it can also produce an index'),version=1),
                    text='Correction: it can also produce an index',source_reference='m2')
    with pytest.raises(ValueError):
        apply_delta(previous(first),delta(edit('it can also produce an index','REPLACE',first['declarations'][1]['id']),version=1),
                    text='Correction: it can also produce an index',source_reference='m2')


def test_ambiguous_exclusive_target_is_not_guessed():
    from understanding.declaration_delta import apply_delta
    from tests.test_declaration_delta import delta, edit, previous
    text='It only produces a summary. This only returns a diagram.'
    first=apply_delta(None,delta(edit('It only produces a summary.'),edit('This only returns a diagram.')),
                      text=text,source_reference='m1')
    with pytest.raises(ValueError):
        apply_delta(previous(first),delta(edit('it can also produce an index','REPLACE',first['declarations'][0]['id']),version=1),
                    text='Correction: it can also produce an index',source_reference='m2')


def test_request_inspection_does_not_admit_generated_grant():
    from data_governance.response_gate import evaluate
    from tests.test_publication_repair2 import runtime as gate_runtime
    r=gate_runtime()
    request='Use the note to tell me whether the tool may deploy a website.'
    assert evaluate(r,request)['allowed']
    assert not evaluate(r,request,'You may deploy the website.')['allowed']


def test_prompt_contract_preserves_requested_format_and_source_scope():
    from agents.reasoning_agent import ReasoningAgent
    agent=object.__new__(ReasoningAgent)
    prompt=agent.build_prompt('pack','mode',{'purpose':'Assist','schema':['Interpret','Reason','Conclude'],'constraints':[]},'Answer in one sentence.')
    assert 'internal coverage' in prompt and 'one sentence' in prompt
    assert 'absence of a thread-only instruction is never permission' in prompt
    assert 'explicit facts are premises' in prompt


def test_exclusive_refinement_commits_and_old_version_remains_historical(tmp_path):
    from integration.conversation_understanding import current_records
    r=runtime(tmp_path)
    text='It only produces a summary. Never execute commands.'
    r.context.active_thread.messages.append(NS(role='operator',content=text,message_id='m1'))
    proposal={'subject_id':'tool','edits':[
        {'operation':'ADD','kind':'REQUIREMENT','quote':'It only produces a summary.','target_id':None},
        {'operation':'ADD','kind':'CONSTRAINT','quote':'Never execute commands.','target_id':None}]}
    assert prepare(r,text,interpreter=lambda *_:(proposal,{}))['state']=='CONFIRMED'
    first=current_records(r)[0]
    text='Correction: it can also produce an index'
    r.context.active_thread.messages.append(NS(role='operator',content=text,message_id='m2'))
    proposal={'subject_id':'tool','edits':[{'operation':'REPLACE','kind':'REQUIREMENT',
        'quote':'it can also produce an index','target_id':first.context['declarations'][0]['id']}]}
    assert prepare(r,text,interpreter=lambda *_:(proposal,{}))['state']=='CONFIRMED'
    current=current_records(r)[0]
    assert current.version==2
    assert 'only produces' not in current.canonical_meaning
    assert 'produces a summary.' in current.canonical_meaning
    assert 'Never execute commands.' in current.canonical_meaning
    old=r.understanding_engine.store.get('op',current.understanding_id,1)
    assert 'only produces' in old.canonical_meaning
