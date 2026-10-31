import json
from types import SimpleNamespace as NS
from pathlib import Path
import pytest

QUERY='Inspect your current Learning subsystem against this objective: learn from consequential interaction outcomes and operator corrections, change future behavior appropriately across relevant contexts and threads without generalizing beyond evidence. Inspect requirements, implementation, integration, runtime behavior, tests and qualification. Determine the blocking gap, explain why and recommend a change without authorization.'

def runtime(tmp_path):
    return NS(context=NS(identity=NS(operator_id='owner'),active_thread=NS(thread_id='fresh')),
              understanding_engine=NS(store=NS(path=tmp_path/'understanding.sqlite3')))

def inspect(tmp_path):
    from integration.runtime_self_inspection import reasoning_context
    r=runtime(tmp_path);p=reasoning_context(r,QUERY)
    return r,p

def test_learning_objective_reaches_evidence_not_numeric_prerequisite(tmp_path):
    r,p=inspect(tmp_path)
    assert r.context.self_inspection['tool_request']['tool']=='inspect_learning_sources'
    assert r.context.self_inspection['evidence_ledger']['objective']['domain']=='LEARNING'

def test_unknown_domain_remains_closed(tmp_path):
    from integration.runtime_self_inspection import reasoning_context
    r=runtime(tmp_path);reasoning_context(r,QUERY.replace('Learning','Unregistered widgets'))
    assert r.context.self_inspection['tool_request'] is None

def test_missing_sources_are_unavailable(tmp_path,monkeypatch):
    import runtime_observation.learning_inspection as reader
    monkeypatch.setattr(reader,'WORKSPACE',tmp_path)
    r,p=inspect(tmp_path)
    entries=r.context.self_inspection['evidence_ledger']['entries']
    assert all(e['evidence_class']=='UNAVAILABLE' for e in entries if e['field'].startswith('learning_class_'))
    assert not any(e['field'] in ('diagnosis','recommendation') for e in entries)

def test_classes_cover_failures_memory_revision_and_unknown_stores(tmp_path):
    r,p=inspect(tmp_path);a=r.context.self_inspection;ledger=a['evidence_ledger']
    assert len(ledger['objective']['required_classes'])==10
    assert any(e['field']=='learning_class_FAILURE' and 'FAIL' in json.dumps(e) for e in ledger['entries'])
    assert any(e['field']=='learning_class_STORE' and e['evidence_class']=='UNAVAILABLE' for e in ledger['entries'])
    from runtime_observation.inspection_coverage import evaluate
    assert evaluate(a['coverage_contract'],ledger,[e['entry_id'] for e in ledger['entries']])['complete']

def proposal(ledger):
    missing=next(e['entry_id'] for e in ledger['entries'] if e['field']=='learning_class_STORE')
    return {'status':'INSUFFICIENT_EVIDENCE','evidence_ids':[missing],
        'gap':None,
        'rationale':'Historical failures do not establish their persistence after later repairs.',
        'recommendation':None,'verification':'Inspect exact current behavioral receipts before selecting a repair.',
        'missing_evidence':[{'evidence_id':missing,'missing':'Current owned Learning journal values are unavailable.',
                             'reason':'Without current state custody, a present concrete defect cannot be established.'}],
        'next_evidence':[{'evidence_id':missing,'inspection':'Inspect the authorized read-only current owned journal projection.'}]}

def test_insufficient_evidence_can_publish_without_recommendation(tmp_path):
    r,p=inspect(tmp_path);ledger=r.context.self_inspection['evidence_ledger']
    from runtime_observation.evidence_ledger import render_selection
    raw={'ledger_id':ledger['ledger_id'],'statements':[e['entry_id'] for e in ledger['entries']], 'diagnosis':proposal(ledger)}
    text,receipt=render_selection(json.dumps(raw),p)
    assert receipt['coverage']['complete'] and 'INFERRED' in text
    assert 'INSUFFICIENT_EVIDENCE' in text
    from integration.self_inspection_activation import assess
    assert assess(QUERY,p,text)['allowed']

@pytest.mark.parametrize('only',['IMPLEMENTATION','TEST','STORE'])
def test_code_tests_memory_alone_cannot_generate_gap_or_recommendation(tmp_path,only):
    from runtime_observation.learning_inspection import validate
    ledger={'entries':[{'entry_id':'E001','field':'learning_class_'+only,'evidence_class':'OBSERVED','value':{'rows':[{'component':'learning/service.py','status':'OBSERVED_RECORDED'}]}}]}
    v={'status':'EVIDENCE_BACKED_GAP','evidence_ids':['E001'],'gap':'A claimed bounded gap requires behavioral evidence.',
       'rationale':'Code or tests or memory alone do not establish the causal behavioral boundary.',
       'verification':'Require independent observed consequences and current source linkage.',
       'recommendation':{'component':'learning/service.py','change':'Repair the selected governed boundary only.','requires_operator_authorization':True,'execution_authority':False}}
    with pytest.raises(PermissionError):validate(ledger,v,['E001'])

def test_recommendation_without_gap_forbidden(tmp_path):
    r,p=inspect(tmp_path);ledger=r.context.self_inspection['evidence_ledger']
    from runtime_observation.learning_inspection import validate
    v=proposal(ledger);v['recommendation']={'change':'Fix Learning'}
    with pytest.raises(PermissionError):validate(ledger,v,[])

def test_history_keeps_nonpass_and_no_general_promotion(tmp_path):
    r,p=inspect(tmp_path);ledger=r.context.self_inspection['evidence_ledger']
    assert 'INCONCLUSIVE' in json.dumps(ledger) and 'FAIL' in json.dumps(ledger)
    assert ledger['validation_state']=='RECORDED_NOT_INDEPENDENTLY_VALIDATED'
    from runtime_observation.learning_inspection import validate
    v=proposal(ledger);v['status']='GENERALIZED_LEARNING_DEMONSTRATED'
    with pytest.raises(PermissionError):validate(ledger,v,[])

def test_missing_required_class_cannot_pass_coverage(tmp_path):
    r,p=inspect(tmp_path);a=r.context.self_inspection;ledger=a['evidence_ledger']
    from runtime_observation.inspection_coverage import evaluate
    selected=[e['entry_id'] for e in ledger['entries'] if e['field']!='learning_class_FAILURE']
    assert not evaluate(a['coverage_contract'],ledger,selected)['complete']

def test_source_paths_cannot_escape_workspace(tmp_path):
    from runtime_observation.learning_inspection import read_source
    row=read_source('../outside.py',None)
    assert row['status']=='UNAVAILABLE' and 'source_excerpt' not in row

def test_no_learning_service_or_store_initialized(tmp_path):
    r,p=inspect(tmp_path)
    assert not hasattr(r,'learning_service') and not hasattr(r,'learning_memory_gateway')
    assert not list(tmp_path.glob('*.sqlite3'))

def test_model_cannot_authorize_or_recommend_uninspected_component(tmp_path):
    r,p=inspect(tmp_path);ledger=r.context.self_inspection['evidence_ledger']
    from runtime_observation.learning_inspection import validate
    ids=[e['entry_id'] for e in ledger['entries']]
    v=proposal(ledger);v.update(status='EVIDENCE_BACKED_GAP',evidence_ids=ids,
        recommendation={'component':'uninspected.py#repair','change':'Repair a boundary with operator review.',
                        'requires_operator_authorization':True,'execution_authority':False})
    with pytest.raises(PermissionError):validate(ledger,v,ids)

def test_gap_can_be_inferred_only_with_inspected_behavior_and_component(tmp_path):
    r,p=inspect(tmp_path);ledger=r.context.self_inspection['evidence_ledger']
    from runtime_observation.learning_inspection import validate
    ids=[e['entry_id'] for e in ledger['entries']]
    v=proposal(ledger);v.update(status='EVIDENCE_BACKED_GAP',evidence_ids=ids,
        gap='A bounded current inference requires source and behavioral citations.',
        recommendation={'component':'integration/interaction_learning.py#evaluate','change':'Review the exact scoped behavioral boundary against its evidence before implementation.',
                        'requires_operator_authorization':True,'execution_authority':False})
    del v['missing_evidence'];del v['next_evidence']
    assert validate(ledger,v,ids)['recommendation']['execution_authority'] is False
    v['recommendation']['execution_authority']=True
    with pytest.raises(PermissionError):validate(ledger,v,ids)

def test_actual_reasoning_stages_keep_learning_contract_and_evidence(tmp_path):
    r,p=inspect(tmp_path);ledger=r.context.self_inspection['evidence_ledger']
    from tests.test_cross_thread_downstream_preservation import run
    raw={'ledger_id':ledger['ledger_id'],'statements':[e['entry_id'] for e in ledger['entries']],
         'diagnosis':proposal(ledger)}
    result,calls=run(p,[json.dumps(raw)]*3)
    assert len(calls)==3 and 'INSUFFICIENT_EVIDENCE' in result.final_response
    assert all('For the LEARNING objective' in str(c) and 'learning_class_FAILURE' in str(c) for c in calls)
