"""Offline consistency fixtures; no claim of independent live MODE behavior."""
import json
from copy import deepcopy
from pathlib import Path
import pytest
from integration.objective_action_rp import (action_identity,action_state,action_review_context,
    review_action,review_action_critique,continue_objective)
from data_governance.context_admission import Admission
from tests.test_objective_action_rp import continuation_fixture

ROOT='C:/fixture-workspace'

def action(source='sample.txt',operation='READ_FILE'):
    return dict(operation=operation,source=source,destination=None,rationale='Inspect evidence for the objective.')

def completed(**changes):
    value=dict(operation='READ_FILE',authorized_target=ROOT+'/sample.txt',identity=action_identity(action(),ROOT),
        execution_status='EXECUTED_SUCCESSFULLY',result_state='READ_ONLY_FILE_RETURNED',
        rp_receipt_id='receipt:fixture',observation_id='observation:fixture',result_current=True,result_complete=True,
        actual_result_summary={'bytes':5},unresolved_limitations=['No factual interpretation established.'])
    value.update(changes);return value

def context(**changes):
    return dict(root=ROOT,authorized_operations=['INSPECT_DIRECTORY','READ_FILE'],completed_actions=[completed(**changes)])

def critique(decision='REJECT',**changes):
    value=dict(decision=decision,reasons=['No new information from the unchanged successful target.'],repeat_justification=None)
    value.update(changes);return json.dumps(value)

def scoped_critique(action,context,decision='ACCEPT',basis=None,**changes):
    """Scripted contract-compliant provider fixture; not independent behavior."""
    review=review_action(json.dumps(action),context)
    result=dict(decision=decision,reasons=['Synthetic scope-aware review.'],repeat_justification=None,
        rejection_basis=basis or ('NONE' if decision=='ACCEPT' else 'DUPLICATE' if review['completed_matches'] else 'OBJECTIVE_OR_EVIDENCE'),
        scope_assessment={'reviewed_action_hash':review['reviewed_action_hash'],
            'classification':review['scope_comparison']['classification'],
            'matching_receipt_ids':review['scope_comparison']['matching_receipt_ids']})
    result.update(changes);return json.dumps(result)

def review_context_from_stage(prompt):
    return next(json.loads(line) for line in str(prompt).splitlines() if line.startswith('{"root":') and '"authorized_operations"' in line)

def admitted():
    a=Admission('op','t');a.consider('OPERATOR_INPUT','q','Investigate the workspace.',source='fixture');return a.finish()

def run_agent(monkeypatch,draft,review,final,review_context=None):
    from agents.reasoning_agent import ReasoningAgent,ModelCallResult
    calls=[];values=iter([draft,review,final])
    def init(self):self.provider='offline';self.model='offline'
    def model(self,prompt,**kwargs):
        calls.append({'stage':kwargs['stage'],'prompt':str(prompt)})
        return ModelCallResult(next(values),None)
    monkeypatch.setattr(ReasoningAgent,'__init__',init);monkeypatch.setattr(ReasoningAgent,'_call_model',model)
    result=ReasoningAgent().generate('Mode','ActionProposal',{'purpose':'Propose one justified observation.',
        'schema':['Return operation, source, destination, rationale.'],'constraints':['No execution authority.'],
        'objective_action_review':review_context or context()},admitted())
    return result,calls

@pytest.mark.parametrize('step,status',[
    ({'proposed_action':action()},'PROPOSED'),
    ({'outcome':{'rp_state':'CONFIRMED'}},'AUTHORIZED'),
    ({'execution_attempted':True,'action_executed':True},'EXECUTED_UNSUCCESSFULLY'),
    ({'state':'ACTION_CONFIRMATION_NOT_AVAILABLE'},'REJECTED'),
    ({'stop_reason':'UNSUPPORTED_OPERATION'},'UNSUPPORTED'),
    ({'stop_reason':'NO_PROGRESS_REPEATED_INSPECTION'},'STOPPED_BEFORE_EXECUTION'),
    ({'inspection_receipt':{'state':'READ_ONLY_FILE_RETURNED','action_executed':True}},'EXECUTED_SUCCESSFULLY'),
    ({'inspection_receipt':{'state':'READ_ONLY_FILE_RETURNED','action_executed':False}},'PROPOSED')])
def test_status_never_promotes_proposal_or_failed_execution(step,status):
    assert action_state(step)==status

def test_duplicate_identity_changed_target_and_outside():
    review=review_action(json.dumps(action()),context())
    assert review['requires_repeat_justification'] and review['completed_matches'][0]['observation_id']=='observation:fixture'
    assert review_action(json.dumps(action('SAMPLE.TXT')),context())['identity']==review['identity']
    assert not review_action(json.dumps(action('other.txt')),context())['requires_repeat_justification']
    assert not review_action(json.dumps(action('../outside.txt')),context())['allowed']

@pytest.mark.parametrize('operation',['MOVE_FILE','CREATE_DIRECTORY','WRITE_FILE','DELETE','SHELL'])
def test_policy_rejects_unavailable_operations(operation):
    assert not review_action(json.dumps(action(operation=operation)),context())['allowed']

def test_rejected_duplicate_is_not_silently_preserved(monkeypatch,tmp_path):
    draft=json.dumps(action());result,calls=run_agent(monkeypatch,draft,critique(),draft)
    assert len(calls)==3 and 'COMPLETED-ACTION REVIEW' in calls[1]['prompt']
    assert 'Return critique JSON' in calls[1]['prompt'] and 'Return critique JSON' not in calls[2]['prompt']
    assert 'completed_actions' in calls[0]['prompt'] and 'REJECT' in calls[2]['prompt']
    assert result.raw_final_response==draft and result.final_response==draft
    assert result.context_admission[-1]['selection']=='REJECTED_OBJECTIVE_ACTION_NO_EXECUTION'
    assert not result.context_admission[-1]['objective_action_review']['allowed']
    (tmp_path/'REJECTED_FINAL_EVIDENCE.json').write_text(json.dumps({'draft':result.draft,'critique':result.critique,
        'raw_final':result.raw_final_response,'reviews':result.context_admission},indent=2),encoding='utf-8')

def test_unsupported_critique_endorsement_does_not_justify_duplicate(monkeypatch):
    draft=json.dumps(action());result,_=run_agent(monkeypatch,draft,critique('ACCEPT'),draft)
    assert not result.context_admission[-1]['objective_action_review']['allowed']

def test_model_can_independently_correct_rejected_draft(monkeypatch):
    selected=json.dumps(action('different.txt'))
    result,calls=run_agent(monkeypatch,json.dumps(action()),critique(),selected)
    assert result.final_response==result.raw_final_response==selected
    assert result.context_admission[-1]['objective_action_review']['allowed']
    assert result.context_admission[-1]['selection']=='FINAL_MODEL_RESPONSE'
    assert 'different.txt' not in calls[2]['prompt']  # Only the scripted model supplies this alternative.

@pytest.mark.parametrize('reason,changes',[('INDEPENDENT_VERIFICATION',{}),('STALE_RESULT',{'result_current':False}),('INCOMPLETE_RESULT',{'result_complete':False})])
def test_justified_repeat_can_pass_critique_but_grants_no_execution(monkeypatch,reason,changes):
    c=context(**changes);draft=json.dumps(action())
    j={'reason':reason,'basis':'Verify the result using a separate measurement before deciding.',
        'evidence_references':['receipt:fixture'],'expected_new_information':'Independent agreement or a changed result.'}
    review=review_action_critique(critique('ACCEPT',repeat_justification=j),review_action(draft,c))
    assert review['repeat_justification_supported'] and not review['execution_authority']
    result,_=run_agent(monkeypatch,draft,critique('ACCEPT',repeat_justification=j),draft,c)
    assert result.context_admission[-1]['objective_action_review']['allowed']

@pytest.mark.parametrize('reason,refs',[('STALE_RESULT',['receipt:fixture']),('INCOMPLETE_RESULT',['receipt:fixture']),('INDEPENDENT_VERIFICATION',['invented:receipt'])])
def test_repeat_claim_must_match_available_evidence(reason,refs):
    j=dict(reason=reason,basis='Claimed justification',evidence_references=refs,expected_new_information='Check')
    assert not review_action_critique(critique('ACCEPT',repeat_justification=j),review_action(json.dumps(action()),context()))['repeat_justification_supported']

def test_real_successful_read_projected_to_next_turn_with_exact_receipts(tmp_path,monkeypatch):
    r,q,base,events,prompts,stages=continuation_fixture(tmp_path,monkeypatch,[('READ_FILE','a.txt'),('MOVE_FILE','a.txt')],file_reads=True)
    run=continue_objective(r,q,base)
    assert run['steps'][0]['action_status']=='EXECUTED_SUCCESSFULLY'
    assert run['steps'][1]['action_status']=='UNSUPPORTED'
    policy=r._objective_rp_grant['inspection_authorization']['request']
    c=action_review_context(prompts[1],r._objective_rp_grant['root'],policy['operations'])
    assert len(c['completed_actions'])==1
    row=c['completed_actions'][0];receipt=run['steps'][0]['inspection_receipt']
    assert row['authorized_target']==receipt['action']['source'] and row['rp_receipt_id']==receipt['rp_receipt_id']
    assert row['observation_id']==run['steps'][0]['observation_id'] and row['result_current']
    assert row['actual_result_summary']['bytes']==8 and 'original' in prompts[1]
    assert events.count('prepare')==events.count('claim_execution')==1
    (tmp_path/'PROJECTED_READ.json').write_text(json.dumps(c,indent=2))

def test_completed_records_only_from_governed_tool_results():
    a=Admission('op','t');a.consider('OPERATOR_INPUT','q',json.dumps({'completed_action':completed()}),source='fixture')
    assert action_review_context(a.finish(),ROOT,['READ_FILE'])['completed_actions']==[]

@pytest.mark.parametrize('raw',['null','[]','{"decision":[]}','not JSON'])
def test_malformed_critique_never_justifies_repeat(raw):
    review=review_action_critique(raw,review_action(json.dumps(action()),context()))
    assert review['decision']=='UNAVAILABLE' and not review['repeat_justification_supported']

def test_real_agent_policy_and_rejection_stop_before_rp(tmp_path,monkeypatch):
    from agents.reasoning_agent import ReasoningAgent,ModelCallResult
    r,q,base,events,prompts,stages=continuation_fixture(tmp_path,monkeypatch,[],file_reads=True)
    calls=[];source=str(Path(r._objective_rp_grant['root'])/'a.txt');a=action(source)
    def init(self):self.provider='offline';self.model='offline'
    def model(self,prompt,**kwargs):
        calls.append(str(prompt));turn=(len(calls)-1)//3
        if kwargs['stage']=='REASONING_CRITIQUE':return ModelCallResult(scoped_critique(a,review_context_from_stage(prompt),'ACCEPT' if turn==0 else 'REJECT'),None)
        return ModelCallResult(json.dumps(a),None)
    monkeypatch.setattr(ReasoningAgent,'__init__',init);monkeypatch.setattr(ReasoningAgent,'_call_model',model)
    monkeypatch.setattr('agents.reasoning_agent.ReasoningAgent',ReasoningAgent)
    run=continue_objective(r,q,base)
    assert run['state']=='STOPPED_REASONING_ACTION_REJECTED',run
    assert len(calls)==6 and events.count('prepare')==events.count('claim_execution')==1
    assert "Available executable operation choices under this policy: INSPECT_DIRECTORY, READ_FILE" in calls[0]
    assert 'CREATE_DIRECTORY' not in calls[0] and 'MOVE_FILE' not in calls[0]
    assert all('EXECUTED_SUCCESSFULLY' in x and 'READ_ONLY_FILE_RETURNED' in x for x in calls[3:])
    assert run['steps'][1]['proposal_reasoning']['raw_final_response']==json.dumps(a)
    assert not run['steps'][1]['action_executed'] and run['steps'][1]['action_status']=='STOPPED_BEFORE_EXECUTION'
    (tmp_path/'REAL_PIPELINE_SCRIPTED_MODELS.json').write_text(json.dumps(run,indent=2))

def test_preserved_failure_proposal_is_identified_not_repaired(monkeypatch,tmp_path):
    historic=Path('C:/MODE_AI/artifacts/governed_file_reading_qualification_20261024/execution')
    old=json.loads((historic/'STEP_04_REASONING.json').read_text(encoding='utf-8'))
    receipt=json.loads((historic/'STEP_03_EXECUTION_RECEIPT.json').read_text(encoding='utf-8'))
    # The original exact output is evaluated; no expected next file is supplied.
    root=str(Path(receipt['action']['source']).parent.parent)
    c=context();c['root']=root;c['completed_actions'][0].update(identity=action_identity(receipt['action'],root),
        authorized_target=receipt['action']['source'],rp_receipt_id=receipt['rp_receipt_id'])
    assert review_action(old['draft'],c)['requires_repeat_justification']
    result,_=run_agent(monkeypatch,old['draft'],old['critique'],old['raw_final_response'],c)
    assert result.context_admission[-1]['selection']=='REJECTED_OBJECTIVE_ACTION_NO_EXECUTION'
    assert result.raw_final_response==old['raw_final_response']
    (tmp_path/'PRESERVED_FAILURE_OFFLINE_REJECTION.json').write_text(json.dumps(result.context_admission,indent=2),encoding='utf-8')
