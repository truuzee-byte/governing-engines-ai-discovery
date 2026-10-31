"""Offline parser and actual-agent handoff tests; no independent model proof."""
import json
from pathlib import Path
from copy import deepcopy
import pytest
from integration.objective_action_rp import parse_critique_response,review_action_critique,review_action
from tests.test_completed_action_awareness import action,scoped_critique,run_agent,review_context_from_stage
from tests.test_action_scope_discrimination import context,record,real_pipeline

def fixture_payload():
    candidate=action('child','INSPECT_DIRECTORY');c=context([record(action('C:/fixture-workspace','INSPECT_DIRECTORY'))])
    return candidate,c,json.loads(scoped_critique(candidate,c))

def fence(text):return '```json\n'+text+'\n```'

def run_response(monkeypatch,raw):
    candidate,c,_=fixture_payload();a=json.dumps(candidate)
    return run_agent(monkeypatch,a,raw,a,c)

@pytest.mark.parametrize('style',['bare','json_fence','whitespace_bare','whitespace_fence','crlf_fence'])
def test_supported_complete_payload_reaches_finalization_unchanged(monkeypatch,style):
    candidate,c,payload=fixture_payload();text=json.dumps(payload)
    raw={'bare':text,'json_fence':fence(text),'whitespace_bare':' \r\n\t'+text+' \t\n',
        'whitespace_fence':' \t\n'+fence(text)+' \r\n','crlf_fence':'```json\r\n'+text+'\r\n```'}[style]
    parsed,wire=parse_critique_response(raw,True);assert parsed==payload
    result,calls=run_response(monkeypatch,raw)
    assert result.critique==raw and result.context_admission[1]['objective_action_review']['response_contract_valid']
    assert result.context_admission[1]['objective_action_review']['response_format']==wire
    assert result.context_admission[-1]['objective_action_review']['allowed']
    assert result.final_response==result.raw_final_response==json.dumps(candidate) and len(calls)==3
    assert 'CRITIQUE RESPONSE WIRE CONTRACT' in calls[1]['prompt']
    assert 'CRITIQUE RESPONSE WIRE CONTRACT' not in calls[0]['prompt'] and 'CRITIQUE RESPONSE WIRE CONTRACT' not in calls[2]['prompt']

@pytest.mark.parametrize('style',['unlabelled','missing_close','missing_open','multiple_blocks','prose_before','prose_after',
    'python_label','uppercase_label','tilde_fence','four_backticks','extra_payload_bare','extra_payload_fenced','empty_fence',
    'bad_inner_json','truncated_json','duplicate_fields','nonfinite'])
def test_ambiguous_or_malformed_wire_forms_fail_closed_through_agent(monkeypatch,style):
    _,_,payload=fixture_payload();text=json.dumps(payload)
    raw={
        'unlabelled':'```\n'+text+'\n```',
        'missing_close':'```json\n'+text,
        'missing_open':text+'\n```',
        'multiple_blocks':fence(text)+'\n'+fence(text),
        'prose_before':'Here is my review:\n'+fence(text),
        'prose_after':fence(text)+'\nApproved.',
        'python_label':'```python\n'+text+'\n```',
        'uppercase_label':'```JSON\n'+text+'\n```',
        'tilde_fence':'~~~json\n'+text+'\n~~~',
        'four_backticks':'````json\n'+text+'\n````',
        'extra_payload_bare':text+'\n'+text,
        'extra_payload_fenced':fence(text+'\n'+text),
        'empty_fence':fence(''),
        'bad_inner_json':fence('{not JSON}'),
        'truncated_json':fence(text[:-1]),
        'duplicate_fields':fence(text.replace('"decision": "ACCEPT"','"decision": "ACCEPT", "decision": "REJECT"')),
        'nonfinite':fence(json.dumps({**payload,'reasons':[float('nan')]}))}[style]
    with pytest.raises(ValueError):parse_critique_response(raw,True)
    result,calls=run_response(monkeypatch,raw)
    assert result.critique==raw and len(calls)==3
    assert result.context_admission[1]['objective_action_review']['decision']=='UNAVAILABLE'
    assert not result.context_admission[1]['objective_action_review']['response_contract_valid']
    assert not result.context_admission[-1]['objective_action_review']['allowed']
    assert result.context_admission[-1]['selection']=='REJECTED_OBJECTIVE_ACTION_NO_EXECUTION'

@pytest.mark.parametrize('missing',['decision','reasons','repeat_justification','scope_assessment','rejection_basis'])
def test_missing_required_field_does_not_get_invented(monkeypatch,missing):
    _,_,payload=fixture_payload();payload.pop(missing);raw=fence(json.dumps(payload))
    result,_=run_response(monkeypatch,raw)
    assert not result.context_admission[1]['objective_action_review']['response_contract_valid']
    assert not result.context_admission[-1]['objective_action_review']['allowed']

@pytest.mark.parametrize('field,value',[
    ('decision','APPROVE'),('decision','accept'),('decision',True),('decision',None),
    ('reasons','good'),('reasons',[]),('reasons',[None]),('reasons',[' ']),
    ('repeat_justification',[]),('repeat_justification',{'reason':'INDEPENDENT_VERIFICATION'}),
    ('scope_assessment',[]),('scope_assessment',None),('rejection_basis','ALLOW'),('rejection_basis',False)])
def test_wrong_types_and_values_remain_unavailable(monkeypatch,field,value):
    _,_,payload=fixture_payload();payload[field]=value
    result,_=run_response(monkeypatch,fence(json.dumps(payload)))
    assert not result.context_admission[1]['objective_action_review']['response_contract_valid']
    assert not result.context_admission[-1]['objective_action_review']['allowed']

@pytest.mark.parametrize('field,value',[('reviewed_action_hash',23),('classification','SAME_PARENT'),('matching_receipt_ids','receipt:fake'),('matching_receipt_ids',[False])])
def test_scope_field_types_are_validated_after_unwrapping(monkeypatch,field,value):
    _,_,payload=fixture_payload();payload['scope_assessment'][field]=value
    result,_=run_response(monkeypatch,fence(json.dumps(payload)))
    assert not result.context_admission[1]['objective_action_review']['response_contract_valid']
    assert not result.context_admission[-1]['objective_action_review']['allowed']

def test_unsupported_extra_fields_are_not_silently_ignored(monkeypatch):
    _,_,payload=fixture_payload();payload['force_execute']=True
    result,_=run_response(monkeypatch,fence(json.dumps(payload)))
    assert not result.context_admission[-1]['objective_action_review']['allowed']

def test_valid_fenced_rejection_still_binds_retained_action(monkeypatch):
    candidate,c,_=fixture_payload();raw=fence(scoped_critique(candidate,c,'REJECT',basis='OBJECTIVE_OR_EVIDENCE'))
    final={**candidate,'rationale':'Changed explanation is not a new critique acceptance.'}
    result,_=run_agent(monkeypatch,json.dumps(candidate),raw,json.dumps(final),c)
    review=result.context_admission[1]['objective_action_review']
    assert review['decision']=='REJECT' and review['response_contract_valid'] and review['scope_contract_valid']
    assert not result.context_admission[-1]['objective_action_review']['allowed']
    assert result.raw_final_response==json.dumps(final) and result.final_response==result.raw_final_response

def test_fenced_acceptance_does_not_justify_completed_file_repeat(monkeypatch):
    candidate=action();c=context([record(candidate)]);text=json.dumps(candidate)
    result,_=run_agent(monkeypatch,text,fence(scoped_critique(candidate,c)),text,c)
    assert result.context_admission[1]['objective_action_review']['response_contract_valid']
    assert not result.context_admission[1]['objective_action_review']['repeat_justification_supported']
    assert not result.context_admission[-1]['objective_action_review']['allowed']

def test_valid_json_wrapper_does_not_make_false_scope_claim_valid(monkeypatch):
    candidate,c,_=fixture_payload();text=json.dumps(candidate)
    result,_=run_agent(monkeypatch,text,fence(scoped_critique(candidate,c,'REJECT',basis='DUPLICATE')),text,c)
    assert result.context_admission[1]['objective_action_review']['response_contract_valid']
    assert not result.context_admission[1]['objective_action_review']['scope_contract_valid']
    assert not result.context_admission[-1]['objective_action_review']['allowed']

def test_fenced_acceptances_continue_through_fresh_real_rp_and_native_reads(tmp_path,monkeypatch):
    import tests.test_action_scope_discrimination as fixture_module
    original=fixture_module.scoped_critique
    monkeypatch.setattr(fixture_module,'scoped_critique',lambda *a,**kw:fence(original(*a,**kw)))
    r,run,events,calls=fixture_module.real_pipeline(tmp_path,monkeypatch)
    assert run['state']=='STOPPED_STEP_LIMIT' and run['returned_inspection_count']==3
    assert events.count('prepare')==events.count('claim_execution')==3 and len(calls)==9
    assert all(s['proposal_reasoning']['context_admission'][1]['objective_action_review']['response_format']=='JSON_FENCE' for s in run['steps'])
    assert run['steps'][2]['inspection_receipt']['findings']['content']=='child fixture'
    (tmp_path/'FENCED_REVIEW_REAL_RP_SCRIPTED_MODELS.json').write_text(json.dumps(run,indent=2))

def test_exact_preserved_fenced_response_passes_actual_handoff_offline(monkeypatch,tmp_path):
    old=Path('C:/MODE_AI/artifacts/objective_scope_semantic_qualification_20261025/execution')
    reason=json.loads((old/'STEP_04_REASONING.json').read_text(encoding='utf-8'))
    request=json.loads((old/'CALL_12_REQUEST.json').read_text(encoding='utf-8'))
    c=review_context_from_stage(request['input']);raw=reason['critique']
    result,calls=run_agent(monkeypatch,reason['draft'],raw,reason['raw_final_response'],c)
    assert result.critique==raw and len(calls)==3
    review=result.context_admission[1]['objective_action_review']
    assert review['response_format']=='JSON_FENCE' and review['response_contract_valid'] and review['scope_contract_valid']
    assert review['decision']=='ACCEPT'
    assert result.final_response==result.raw_final_response==reason['raw_final_response']
    assert result.context_admission[-1]['selection']=='FINAL_MODEL_RESPONSE'
    assert result.context_admission[-1]['objective_action_review']['allowed']
    (tmp_path/'EXACT_FAILURE_OFFLINE_HANDOFF_REPLAY.json').write_text(json.dumps({'scripted_provider_only':True,
        'no_live_objective_or_rp_dispatch_to_original_workspace':True,'raw_critique':result.critique,
        'before_review':reason['context_admission'][1]['objective_action_review'],'after_reviews':result.context_admission,
        'raw_final_unchanged':result.raw_final_response},indent=2),encoding='utf-8')

def test_legacy_nonscoped_contract_remains_closed_and_valid():
    raw=json.dumps({'decision':'REJECT','reasons':['Unsupported proposal.'],'repeat_justification':None})
    payload,wire=parse_critique_response(raw,False)
    assert payload['decision']=='REJECT' and wire=='BARE_JSON'
