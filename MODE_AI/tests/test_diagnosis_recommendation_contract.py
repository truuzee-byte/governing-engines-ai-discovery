import json
from pathlib import Path
import pytest
from tests.test_learning_diagnosis_routing import inspect

def insufficient(ledger,status='INSUFFICIENT_EVIDENCE'):
    missing=next(e['entry_id'] for e in ledger['entries'] if e['field']=='learning_class_STORE')
    return {'status':status,'evidence_ids':[missing],'gap':None,
        'rationale':'Current store values cannot be inspected, so this evidence cannot establish a current concrete defect.',
        'recommendation':None,'verification':'Inspect current owned records and correlate them with accepted behavioral receipts.',
        'missing_evidence':[{'evidence_id':missing,'missing':'Current owner-scoped governed journal values.',
                             'reason':'Implementation alone does not show the current records or behavioral causality.'}],
        'next_evidence':[{'evidence_id':missing,'inspection':'Inspect an authorized owner-scoped read-only journal projection.'}]}

def test_insufficiency_publishes_missing_and_next_evidence_without_defect(tmp_path):
    r,p=inspect(tmp_path);l=r.context.self_inspection['evidence_ledger']
    from runtime_observation.evidence_ledger import render_selection
    v={'ledger_id':l['ledger_id'],'statements':[e['entry_id'] for e in l['entries']],'diagnosis':insufficient(l)}
    text,receipt=render_selection(json.dumps(v),p)
    assert receipt['coverage']['complete'] and 'next_evidence' in text

@pytest.mark.parametrize('status',['INSUFFICIENT_EVIDENCE','UNAVAILABLE'])
def test_non_diagnosed_states_never_carry_gap_or_repair(tmp_path,status):
    r,p=inspect(tmp_path);l=r.context.self_inspection['evidence_ledger']
    from runtime_observation.learning_inspection import validate
    ids=[e['entry_id'] for e in l['entries']];v=insufficient(l,status)
    assert validate(l,v,ids)['gap'] is None
    v['recommendation']={'change':'Implement a Learning rewrite.'}
    with pytest.raises(PermissionError):validate(l,v,ids)
    v['recommendation']=None;v['gap']='A concrete defect has been established.'
    with pytest.raises(PermissionError):validate(l,v,ids)

@pytest.mark.parametrize('field,value',[
 ('next_evidence',[{'evidence_id':'E999','inspection':'Inspect the exact missing record.'}]),
 ('next_evidence',[{'evidence_id':'E013','inspection':'Implement a new memory journaling subsystem.'}]),
 ('missing_evidence',[]),('missing_evidence',[{'evidence_id':'E999','missing':'Absent journal','reason':'Uninspected data.'}])])
def test_inspection_request_is_not_repair_or_fabricated_evidence(tmp_path,field,value):
    r,p=inspect(tmp_path);l=r.context.self_inspection['evidence_ledger']
    from runtime_observation.learning_inspection import validate
    v=insufficient(l);v[field]=value
    with pytest.raises(PermissionError):validate(l,v,[e['entry_id'] for e in l['entries']])

def test_prior_exact_conflicting_final_remains_rejected(tmp_path):
    from runtime_observation.learning_inspection import validate
    r,p=inspect(tmp_path);l=r.context.self_inspection['evidence_ledger']
    prior=json.loads(Path('artifacts/objective_digest_repair_20261021/RAW_MODEL_STAGES.json').read_text(encoding='utf-8'))[-1]['parsed']['diagnosis']
    assert prior['status']=='INSUFFICIENT_EVIDENCE' and prior['recommendation'] is not None
    with pytest.raises(PermissionError):validate(l,prior,[e['entry_id'] for e in l['entries']])

def test_invalid_draft_feedback_reaches_critique_and_final(tmp_path):
    r,p=inspect(tmp_path);l=r.context.self_inspection['evidence_ledger']
    valid={'ledger_id':l['ledger_id'],'statements':[e['entry_id'] for e in l['entries']],'diagnosis':insufficient(l)}
    invalid=json.loads(json.dumps(valid));invalid['diagnosis']['recommendation']={'change':'Build memory journaling.'}
    from tests.test_cross_thread_downstream_preservation import run
    result,calls=run(p,[json.dumps(invalid),json.dumps(valid),json.dumps(valid)])
    assert 'DIAGNOSIS_CONTRACT_REJECTION' in calls[1][0]
    assert 'DIAGNOSIS_CONTRACT_REJECTION' in calls[2][0]
    assert 'STATE-CONDITIONAL DIAGNOSIS CONTRACT' in calls[2][0]
    assert '"recommendation":null' in result.final_response

def test_supported_gap_requires_real_selected_citations_and_no_authority(tmp_path):
    from runtime_observation.learning_inspection import validate
    r,p=inspect(tmp_path);l=r.context.self_inspection['evidence_ledger'];ids=[e['entry_id'] for e in l['entries']]
    v={'status':'EVIDENCE_BACKED_GAP','evidence_ids':ids,'gap':'A bounded inspected failure requires further component-specific review.',
       'rationale':'The source and historical behavior support this bounded inferred gap, not general readiness.',
       'recommendation':{'component':'integration/interaction_learning.py#evaluate','change':'Review the measured boundary with a separately approved minimal correction.',
                         'requires_operator_authorization':True,'execution_authority':False},
       'verification':'Requalify the exact causal boundary with independent evidence and negative controls.'}
    assert validate(l,v,ids)['recommendation']['execution_authority'] is False
    v['evidence_ids']=[]
    with pytest.raises(PermissionError):validate(l,v,ids)
