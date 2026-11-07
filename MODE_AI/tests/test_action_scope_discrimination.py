"""Actual bounded review/agent/RP fixtures; all model responses are scripted."""
import json
from copy import deepcopy
from pathlib import Path
import pytest
from integration.reality_primacy import digest
from integration.objective_action_rp import (observation_scope,action_identity,review_action,review_action_critique,
    continue_objective,inspection_context,action_review_context)
from tests.test_completed_action_awareness import (ROOT,action,completed,run_agent,scoped_critique,review_context_from_stage)
from tests.test_objective_action_rp import continuation_fixture

PARAMETERS={'recursive':False,'max_entries':256,'max_bytes':16384,'max_chars':8192}

def record(proposal,root=ROOT,parameters=None,**changes):
    row=completed(operation=proposal['operation'],authorized_target=str(Path(root)/proposal['source']) if not Path(proposal['source']).is_absolute() else proposal['source'],
        identity=action_identity(proposal,root),observation_scope=observation_scope(proposal,root,parameters or PARAMETERS))
    row.update(changes);return row

def context(records=(),root=ROOT,parameters=None):
    return {'root':root,'authorized_operations':['INSPECT_DIRECTORY','READ_FILE'],'scope_contract_required':True,
        'execution_parameters':parameters or PARAMETERS,'completed_actions':list(records)}

@pytest.mark.parametrize('prior,candidate,relationship',[
    (action(ROOT,'INSPECT_DIRECTORY'),action('child','INSPECT_DIRECTORY'),'COMPLETED_TARGET_IS_ANCESTOR'),
    (action('child','INSPECT_DIRECTORY'),action('child/document.txt'),'COMPLETED_TARGET_IS_ANCESTOR'),
    (action('document.txt'),action(ROOT,'INSPECT_DIRECTORY'),'COMPLETED_TARGET_IS_DESCENDANT'),
    (action('first','INSPECT_DIRECTORY'),action('second','INSPECT_DIRECTORY'),'UNRELATED_TARGET'),
    (action('same','INSPECT_DIRECTORY'),action('same','READ_FILE'),'SAME_TARGET')])
def test_distinct_scopes_reach_actual_critique_and_remain_eligible(monkeypatch,prior,candidate,relationship):
    c=context([record(prior)]);raw=json.dumps(candidate);review=review_action(raw,c)
    assert not review['requires_repeat_justification'] and review['completed_matches']==[]
    assert review['scope_comparison']['completed_comparisons'][0]['relationship']==relationship
    result,calls=run_agent(monkeypatch,raw,scoped_critique(candidate,c),raw,c)
    assert result.context_admission[-1]['objective_action_review']['allowed']
    assert 'shallow parent listing' in calls[1]['prompt'] and 'scope_assessment' in calls[1]['prompt']
    assert result.context_admission[1]['objective_action_review']['scope_contract_valid']
    assert result.final_response==raw

@pytest.mark.parametrize('operation',['INSPECT_DIRECTORY','READ_FILE'])
def test_exact_repeat_different_rationale_still_rejected_in_actual_agent(monkeypatch,operation):
    previous=action('same',operation);candidate={**previous,'rationale':'Different rationale does not change the observation scope.'}
    c=context([record(previous)]);raw=json.dumps(candidate)
    result,_=run_agent(monkeypatch,raw,scoped_critique(candidate,c,'ACCEPT'),raw,c)
    assert result.context_admission[0]['objective_action_review']['requires_repeat_justification']
    assert not result.context_admission[-1]['objective_action_review']['allowed']

def test_target_difference_is_not_automatic_approval(monkeypatch):
    candidate=action('unrelated','INSPECT_DIRECTORY');c=context([record(action(ROOT,'INSPECT_DIRECTORY'))]);raw=json.dumps(candidate)
    result,_=run_agent(monkeypatch,raw,scoped_critique(candidate,c,'REJECT',basis='OBJECTIVE_OR_EVIDENCE'),raw,c)
    assert result.context_admission[1]['objective_action_review']['scope_contract_valid']
    assert not result.context_admission[-1]['objective_action_review']['allowed']
    assert result.context_admission[-1]['selection']=='REJECTED_OBJECTIVE_ACTION_NO_EXECUTION'

@pytest.mark.parametrize('change,reason',[({'result_current':False},'STALE_RESULT'),({'result_complete':False},'INCOMPLETE_RESULT')])
def test_repeat_with_limitations_is_distinguished_without_authorizing_execution(monkeypatch,change,reason):
    a=action();c=context([record(a,**change)])
    lesson={'reason':reason,'basis':'Current result limitation is explicit in the linked evidence.',
        'evidence_references':['receipt:fixture'],'expected_new_information':'Resolve the recorded limitation.'}
    result,_=run_agent(monkeypatch,json.dumps(a),scoped_critique(a,c,repeat_justification=lesson),json.dumps(a),c)
    assert result.context_admission[-1]['objective_action_review']['allowed']
    assert not result.context_admission[1]['objective_action_review']['execution_authority']

def test_material_policy_parameter_difference_same_target_is_not_same_scope(monkeypatch):
    a=action(ROOT,'INSPECT_DIRECTORY');old={**PARAMETERS,'max_entries':128};c=context([record(a,parameters=old)])
    result,_=run_agent(monkeypatch,json.dumps(a),scoped_critique(a,c),json.dumps(a),c)
    comparison=result.context_admission[0]['objective_action_review']['scope_comparison']
    assert comparison['completed_comparisons'][0]['relationship']=='SAME_TARGET'
    assert comparison['classification']=='DISTINCT_OBSERVATION_SCOPE'
    assert result.context_admission[-1]['objective_action_review']['allowed']
    # This comparison does not change the execution guard or authorize a changed grant.

def test_recursive_scope_is_not_invented_or_enabled(monkeypatch):
    a=action(ROOT,'INSPECT_DIRECTORY');c=context(parameters={**PARAMETERS,'recursive':True})
    assert not review_action(json.dumps(a),c)['allowed']
    result,_=run_agent(monkeypatch,json.dumps(a),'{}',json.dumps(a),c)
    assert not result.context_admission[-1]['objective_action_review']['allowed']

def test_proposal_does_not_become_completed_or_create_repeat(monkeypatch):
    a=action();c=context([record(a,execution_status='PROPOSED')])
    result,_=run_agent(monkeypatch,json.dumps(a),scoped_critique(a,c),json.dumps(a),c)
    assert not result.context_admission[0]['objective_action_review']['requires_repeat_justification']

def test_fabricated_or_missing_receipt_completion_fails_existing_admission(tmp_path,monkeypatch):
    r,q,base,events,prompts,stages=continuation_fixture(tmp_path,monkeypatch,[('INSPECT_DIRECTORY','')],file_reads=True)
    run=continue_objective(r,q,base,max_steps=1);step=run['steps'][0]
    broken=deepcopy(step);broken['inspection_receipt']['action_executed']=False
    with pytest.raises(PermissionError,match='binding mismatch'):inspection_context(r,q,base,[broken])
    r.runtime_observation_collector.store.load_record=lambda *a:None
    with pytest.raises(PermissionError,match='Persisted'):inspection_context(r,q,base,[step])

def test_missing_scope_cannot_be_silently_treated_as_distinct(monkeypatch):
    a=action();row=record(a);row.pop('observation_scope');c=context([row])
    result,_=run_agent(monkeypatch,json.dumps(a),'{}',json.dumps(a),c)
    assert not result.context_admission[-1]['objective_action_review']['allowed']
    assert result.context_admission[0]['objective_action_review']['scope_comparison']['classification']=='SCOPE_UNAVAILABLE'

def test_false_duplicate_basis_is_invalid_but_rejection_is_not_overridden(monkeypatch,tmp_path):
    a=action('child','INSPECT_DIRECTORY');c=context([record(action(ROOT,'INSPECT_DIRECTORY'))]);raw=json.dumps(a)
    bad=scoped_critique(a,c,'REJECT',basis='DUPLICATE')
    result,_=run_agent(monkeypatch,raw,bad,raw,c)
    review=result.context_admission[1]['objective_action_review']
    assert review['decision']=='REJECT' and not review['scope_contract_valid']
    assert not result.context_admission[1]['promoted_to_revision']
    assert not result.context_admission[-1]['objective_action_review']['allowed']
    assert result.raw_final_response==raw and result.final_response==raw
    (tmp_path/'INVALID_SCOPE_REJECTION_RETAINED.json').write_text(json.dumps(result.context_admission,indent=2))

def test_changed_explanation_cannot_appeal_valid_rejection(monkeypatch):
    a=action('child','INSPECT_DIRECTORY');c=context([record(action(ROOT,'INSPECT_DIRECTORY'))])
    final={**a,'rationale':'A more detailed explanation cannot reverse the rejection.'}
    result,_=run_agent(monkeypatch,json.dumps(a),scoped_critique(a,c,'REJECT',basis='OBJECTIVE_OR_EVIDENCE'),json.dumps(final),c)
    assert not result.context_admission[-1]['objective_action_review']['allowed']

@pytest.mark.parametrize('operation',['MOVE_FILE','WRITE_FILE','SHELL'])
def test_policy_rejection_remains_fail_closed(monkeypatch,operation):
    a=action('child',operation);c=context();result,_=run_agent(monkeypatch,json.dumps(a),'{}',json.dumps(a),c)
    assert not result.context_admission[-1]['objective_action_review']['allowed']

def real_pipeline(tmp_path,monkeypatch,*,bad_child=False):
    from agents.reasoning_agent import ReasoningAgent,ModelCallResult
    r,q,base,events,_,_=continuation_fixture(tmp_path,monkeypatch,[],file_reads=True)
    root=Path(r._objective_rp_grant['root']);calls=[]
    choices=[action(str(root),'INSPECT_DIRECTORY'),action(str(root/'child'),'INSPECT_DIRECTORY'),action(str(root/'child/b.txt'),'READ_FILE')]
    def init(self):self.provider='offline';self.model='offline'
    def model(self,prompt,**kw):
        index=len(calls)//3;a=choices[index];calls.append({'stage':kw['stage'],'prompt':str(prompt)})
        value=(scoped_critique(a,review_context_from_stage(prompt),'REJECT' if bad_child and index==1 else 'ACCEPT',
                basis='DUPLICATE' if bad_child and index==1 else 'NONE') if kw['stage']=='REASONING_CRITIQUE' else json.dumps(a))
        return ModelCallResult(value,None)
    monkeypatch.setattr(ReasoningAgent,'__init__',init);monkeypatch.setattr(ReasoningAgent,'_call_model',model)
    monkeypatch.setattr('agents.reasoning_agent.ReasoningAgent',ReasoningAgent)
    run=continue_objective(r,q,base,max_steps=3)
    return r,run,events,calls

def test_real_root_child_file_acceptance_still_needs_fresh_rp_each_time(tmp_path,monkeypatch):
    r,run,events,calls=real_pipeline(tmp_path,monkeypatch)
    assert run['state']=='STOPPED_STEP_LIMIT' and run['returned_inspection_count']==3,run
    assert events.count('prepare')==events.count('claim_execution')==3 and len(calls)==9
    assert len({x['request']['request_id'] for x in run['steps']})==3
    packet=next(json.loads(line) for line in calls[3]['prompt'].splitlines() if line.startswith('{"contract":"ObjectiveInspectionEvidence'))
    assert packet['recursive'] is False and packet['source_contents_read'] is False
    assert any(x['name']=='child' and x['type']=='directory' for x in packet['entries'])
    assert 'child fixture' not in calls[3]['prompt']  # Child contents weren't in the parent listing.
    assert run['steps'][1]['proposal_reasoning']['context_admission'][0]['objective_action_review']['completed_matches']==[]
    assert run['steps'][2]['inspection_receipt']['findings']['content']=='child fixture'
    (tmp_path/'SCOPED_REAL_RP_SCRIPTED_PROVIDER_PIPELINE.json').write_text(json.dumps(run,indent=2))

def test_false_child_rejection_never_reaches_second_rp_or_executor(tmp_path,monkeypatch):
    r,run,events,calls=real_pipeline(tmp_path,monkeypatch,bad_child=True)
    assert run['state']=='STOPPED_REASONING_ACTION_REJECTED' and len(calls)==6
    assert events.count('prepare')==events.count('claim_execution')==1
    assert run['returned_inspection_count']==1

@pytest.mark.parametrize('case,failed,successful',[('governed_file_reading_qualification_20261024',3,2),('semantic_advancement_qualification_20261025',1,0)])
def test_both_preserved_exact_failures_remain_safe_without_rewriting_outputs(monkeypatch,tmp_path,case,failed,successful):
    base=Path('C:/MODE_AI/artifacts')/case/'execution';run=json.loads((base/'FINAL_RUNTIME_CONTEXT.json').read_text(encoding='utf-8'))['objective_continuation']
    before=run['steps'][successful];reason=run['steps'][failed]['proposal_reasoning'];receipt=before['inspection_receipt'];root=before['request']['scope']['workspace']
    row=record(receipt['action'],root=root,rp_receipt_id=receipt['rp_receipt_id'],observation_id=before['observation_id'],actual_result_summary={'findings_hash':digest(receipt['findings'])})
    c=context([row],root=root)
    result,calls=run_agent(monkeypatch,reason['draft'],reason['critique'],reason['raw_final_response'],c)
    assert result.raw_final_response==reason['raw_final_response'] and result.final_response==reason['final_response']
    assert not result.context_admission[-1]['objective_action_review']['allowed']
    assert result.context_admission[-1]['selection']=='REJECTED_OBJECTIVE_ACTION_NO_EXECUTION'
    assert result.context_admission[0]['objective_action_review']['requires_repeat_justification']==(failed==3)
    assert not result.context_admission[1]['objective_action_review']['scope_contract_valid']
    (tmp_path/'PRESERVED_SCOPE_REPLAY.json').write_text(json.dumps({'case':case,'scripted_replay_only':True,'draft':result.draft,
        'critique':result.critique,'raw_final':result.raw_final_response,'reviews':result.context_admission},indent=2),encoding='utf-8')
