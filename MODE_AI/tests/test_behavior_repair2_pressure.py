from types import SimpleNamespace as NS
import pytest
from tests.test_conversation_understanding import runtime
from tests.test_declaration_delta import edit, delta, previous
from understanding.declaration_delta import apply_delta
from integration.conversation_understanding import prepare, current_records, prompt_context
from specs.conversation_specification import current, synchronize_pending


def turn(r,text,edits,subject='tool'):
    r.context.active_thread.messages.append(NS(role='operator',content=text,message_id=str(len(r.context.active_thread.messages))))
    return prepare(r,text,interpreter=lambda *_:({'subject_id':subject,'edits':edits},{}))


def test_correction_revocation_and_topic_switch_keep_current_inventory(tmp_path):
    r=runtime(tmp_path)
    turn(r,'Use XML.',[edit('Use XML.',kind='REQUIREMENT')])
    turn(r,'Reject blank input.',[edit('Reject blank input.',kind='CONSTRAINT')])
    original=current(r)[0]['requirement_inventory'][0]['id']
    turn(r,'The visitor arrived.',[edit('The visitor arrived.')],subject='visit')
    result=turn(r,'Replace "Use XML." with "Use JSON."',[edit('Use JSON.','REPLACE',original,'REQUIREMENT')])
    assert not result['result']['errors']
    view=current(r)[0]
    assert {v['quote'] for v in view['requirement_inventory']}=={'Use JSON.','Reject blank input.'}
    assert 'Use XML.' not in str(prompt_context(r))
    target=next(v['id'] for v in view['requirement_inventory'] if v['quote']=='Use JSON.')
    result=turn(r,'Revoke "Use JSON."',[edit('Use JSON.','REVOKE',target,'REQUIREMENT')])
    assert not result['result']['errors']
    assert [v['quote'] for v in current(r)[0]['requirement_inventory']]==['Reject blank input.']
    assert len(current_records(r))==2


def test_pending_explicit_fields_survive_new_requirement_but_approval_does_not(tmp_path):
    r=runtime(tmp_path)
    turn(r,'Use JSON.',[edit('Use JSON.',kind='REQUIREMENT')])
    r.context.build_clarification={'thread_id':'t','operator_input':'Build the tool.',
        'envelope':{'request':{'artifact_structure':{'files':['tool.py']},
            'construction_scope':['Explicit existing module'],
            'governance_constraints':['Operator review required'],
            'authority_state':'handoff_approved','validation_state':'valid',
            'readiness_state':'ready_for_build','save_ready_state':True,'clarification_required':False,
            'execution':{'repository_target':'C:/qualification'},
            'validation':{'commands':['python -m unittest']}},'authorization':{'decision':'APPROVE'}}}
    synchronize_pending(r)
    turn(r,'Reject blank input.',[edit('Reject blank input.',kind='CONSTRAINT')])
    envelope=r.context.build_clarification['envelope']
    assert 'authorization' not in envelope
    assert envelope['request']['artifact_structure']=={'files':['tool.py']}
    assert envelope['request']['execution']=={'repository_target':'C:/qualification'}
    assert envelope['request']['validation']=={'commands':['python -m unittest']}
    assert envelope['request']['authority_state']=='draft_only'
    assert envelope['request']['readiness_state']=='needs_clarification'
    assert envelope['request']['validation_state']=='incomplete'
    assert envelope['request']['save_ready_state'] is False
    assert envelope['request']['clarification_required'] is True
    assert len(envelope['understanding']['requirements'])==2
    assert 'Explicit existing module' in envelope['request']['construction_scope']
    assert 'Operator review required' in envelope['request']['governance_constraints']


def test_unknown_actor_is_not_resolved_by_new_fact(tmp_path):
    r=runtime(tmp_path)
    turn(r,'Who moved the box is unknown.',[edit('Who moved the box is unknown.',kind='UNRESOLVED')])
    turn(r,'The box is outside.',[edit('The box is outside.')])
    assert len(current_records(r)[0].context['declarations'])==2
    assert 'unknown' in str(prompt_context(r))
    assert 'execution_authority' in str(r.context.conversation_understanding)


def test_restart_retains_only_same_thread_scope(tmp_path):
    r=runtime(tmp_path)
    turn(r,'Use JSON.',[edit('Use JSON.',kind='REQUIREMENT')])
    assert len(current_records(runtime(tmp_path)))==1
    assert current_records(runtime(tmp_path,'new-thread'))==[]


def test_failed_extraction_does_not_expose_provider_error_or_replace_state(tmp_path):
    r=runtime(tmp_path)
    turn(r,'Use JSON.',[edit('Use JSON.',kind='REQUIREMENT')])
    def failed(*_):raise RuntimeError('sensitive-provider-detail')
    result=prepare(r,'more',interpreter=failed)
    assert result['state']=='CLARIFICATION_REQUIRED'
    assert 'sensitive-provider-detail' not in str(result)
    assert current_records(r)[0].version==1
    assert 'latest semantic update was not committed' in str(prompt_context(r))
    assert 'sensitive-provider-detail' not in str(prompt_context(r))


def test_ambiguous_correction_cannot_silently_remove_prior_meaning(tmp_path):
    r=runtime(tmp_path)
    turn(r,'Use XML.',[edit('Use XML.',kind='REQUIREMENT')])
    target=current(r)[0]['requirement_inventory'][0]['id']
    result=turn(r,'Use JSON instead.',[edit('Use JSON','REPLACE',target,'REQUIREMENT')])
    assert result['result']['errors']
    assert current_records(r)[0].version==1
    assert current(r)[0]['requirement_inventory'][0]['quote']=='Use XML.'


def test_unrelated_question_and_repeated_fact_preserve_inventory(tmp_path):
    r=runtime(tmp_path)
    turn(r,'The door is open.',[edit('The door is open.')],subject='visit')
    result=prepare(r,'Why?',interpreter=lambda *_:({'subject_id':None,'edits':[]},{}))
    assert result['state']=='NO_CHANGE'
    turn(r,'The door is open.',[edit('The door is open.')],subject='visit')
    assert len(current_records(r)[0].context['declarations'])==1
    assert len(current_records(r)[0].context['declarations'][0]['source_references'])==2


def test_unknown_kind_or_cross_owner_authority_cannot_commit(tmp_path):
    from understanding import UnderstandingRequest, AuthorityContext, AuthorityLevel
    r=runtime(tmp_path)
    request=UnderstandingRequest('op','t','Use JSON.',declaration_delta={
        'subject_id':'tool','expected_version':0,'edits':[edit('Use JSON.',kind='REQUIREMENT')]},
        authority_context=AuthorityContext('other',AuthorityLevel.DIRECT_OPERATOR_STATEMENT,'OPERATOR',authenticated=True),
        runtime_metadata={'operator_source_reference':'m'})
    assert r.understanding_engine.process(request).errors
    assert current_records(r)==[]


def test_projection_failure_does_not_relabel_committed_meaning(tmp_path,monkeypatch):
    r=runtime(tmp_path)
    def failed(*_):raise ValueError('projection unavailable')
    monkeypatch.setattr('specs.conversation_specification.synchronize_pending',failed)
    result=turn(r,'Use JSON.',[edit('Use JSON.',kind='REQUIREMENT')])
    assert not result['result']['errors']
    assert result['specification_projection']['state']=='CLARIFICATION_REQUIRED'
    assert len(current_records(r))==1
    assert result['result']['final_understanding']['version']==1
