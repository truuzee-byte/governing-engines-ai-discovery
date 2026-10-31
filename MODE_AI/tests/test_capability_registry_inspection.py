import json
from copy import deepcopy
from dataclasses import fields
from types import SimpleNamespace as NS
import hashlib
import pytest
from system_layer.contracts import Capability,digest
from system_layer.creation.service import SystemLayer
from system_layer.capability_inspection import assess,inspect_capabilities
from runtime_observation.capability_ledger import CAPABILITIES,normalize

def value(tmp_path,kinds=('CODE','INTEGRATION','TEST'),cid='self-inspection-activation'):
    cap={f.name:[] for f in fields(Capability) if f.default_factory is not None}
    # Explicit contract; tests do not use stronger reality states.
    strings=('capability_id','name','category','purpose','description','operator_id')
    cap={f.name:[] for f in fields(Capability)}
    cap.update({k:cid for k in strings});cap['operator_id']='owner'
    cap.update(scope={'operator_id':'owner','profile':'INTERNAL','deployment':'test'},
        builder_support={},creation_support={},version=1,supersedes=None,declared_state='DECLARED',
        implementation_state='UNCONFIRMED',integration_state='UNCONFIRMED',validation_state='UNCONFIRMED',
        operational_state='UNCONFIRMED',rp_state='PENDING_VALIDATION',last_audit_at=None,last_validation_at=None,schema_version='1.0')
    p=tmp_path/'evidence.txt';p.write_text('bounded evidence')
    evidence=[{'kind':k,'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
               'locator':'fixture','scope':'test fixture only','result':'PASS'} for k in kinds]
    return {'capability':Capability(**cap).to_dict(),'evidence_inventory':{
        'contract':'CapabilityEvidenceInventory/1','evidence':evidence,'assessment':assess(evidence),
        'limitations':['Synthetic engineering fixture, not qualification.'],'component_ownership':'UNAVAILABLE'},
        'control':'EVIDENCE_ONLY','target_state':'UNCONFIRMED'}

def service(tmp_path):return SystemLayer(tmp_path/'system.sqlite3',NS(context=NS(identity=NS(operator_id='owner'))))
def put(s,v,expected=None):
    request={'value':v,'expected_receipt':expected}
    return s.record_capability_evidence(v,expected,{'operator_id':'owner','action':'CAPABILITY_EVIDENCE','decision':'APPROVE','hash':digest(request)})

@pytest.mark.parametrize('kinds,axis,expected',[
    ((),'implemented','UNKNOWN'),(('CODE',),'validated','UNKNOWN'),
    (('TEST',),'operational','UNKNOWN'),(('INTEGRATION',),'integrated','UNKNOWN'),
    (('CODE','INTEGRATION'),'integrated','INTEGRATED'),(('TEST',),'validated','VALIDATED'),
    (('RUNTIME',),'operational','OPERATIONAL')])
def test_evidence_strength_does_not_cross_promote(tmp_path,kinds,axis,expected):
    v=value(tmp_path,kinds);r=put(service(tmp_path),v)
    assert r['value']['evidence_inventory']['assessment'][axis]==expected
    assert all(r['value']['capability'][k]=='UNCONFIRMED' for k in ('implementation_state','integration_state','validation_state','operational_state'))

def test_missing_registry_is_read_only_unknown(tmp_path):
    path=tmp_path/'absent.sqlite3'
    p=inspect_capabilities(path,'owner','owner',['absent'])
    assert p['entries'][0]['state']=='UNKNOWN' and not path.exists()

def test_custody_and_snapshot_no_mutation(tmp_path):
    s=service(tmp_path);put(s,value(tmp_path));before=s.store.path.read_bytes()
    with pytest.raises(PermissionError):inspect_capabilities(s.store.path,'other','owner',['self-inspection-activation'])
    p=inspect_capabilities(s.store.path,'owner','owner',['self-inspection-activation'])
    p['entries'][0]['inventory']['assessment']['operational']='OPERATIONAL'
    assert s.store.path.read_bytes()==before
    again=inspect_capabilities(s.store.path,'owner','owner',['self-inspection-activation'])
    assert again['entries'][0]['inventory']['assessment']['operational']=='UNKNOWN'

def test_evidence_failure_records_degradation_without_qualification(tmp_path):
    s=service(tmp_path);v=value(tmp_path,('TEST','RUNTIME'))
    v['evidence_inventory']['evidence'][-1]['result']='FAIL'
    v['evidence_inventory']['assessment']=assess(v['evidence_inventory']['evidence'])
    r=put(s,v)
    assert r['value']['evidence_inventory']['assessment']['health']=='DEGRADED'
    assert r['value']['capability']['rp_state']=='PENDING_VALIDATION'

def test_cannot_import_stronger_authority_or_forged_assessment(tmp_path):
    s=service(tmp_path);v=value(tmp_path)
    v['capability']['operational_state']='OPERATIONAL'
    with pytest.raises(PermissionError):put(s,v)
    v=value(tmp_path);v['capability']['declared_state']='OPERATIONAL'
    with pytest.raises(PermissionError):put(s,v)
    v=value(tmp_path);v['evidence_inventory']['assessment']['operational']='OPERATIONAL'
    with pytest.raises(PermissionError):put(s,v)

def test_version_and_exact_approval(tmp_path):
    s=service(tmp_path);v=value(tmp_path);r=put(s,v)
    with pytest.raises(PermissionError):put(s,v)
    v['capability'].update(version=2,supersedes=r['receipt_id']);put(s,v,r['receipt_id'])
    with pytest.raises(PermissionError):s.record_capability_evidence(v,None,{})

def test_changed_reference_is_conflict_not_silent_promotion(tmp_path):
    s=service(tmp_path);put(s,value(tmp_path))
    p=inspect_capabilities(s.store.path,'owner','owner',['self-inspection-activation'])
    # Outside workspace references are intentionally unavailable to this reader.
    assert p['entries'][0]['conflict']=='REVALIDATION_REQUIRED'
    ledger=normalize(p,'thread');assert any(e['field']=='registry_runtime_conflicts' and e['value']['observed_conflicts'] for e in ledger['entries'])

def routed(tmp_path):
    s=service(tmp_path)
    for cid in CAPABILITIES:put(s,value(tmp_path,cid=cid))
    runtime=NS(context=NS(identity=NS(operator_id='owner'),active_thread=NS(thread_id='thread')),
        understanding_engine=NS(store=NS(path=s.store.path.with_name('understanding.sqlite3'))))
    # Runtime service convention uses this filename.
    s.store.path.rename(s.store.path.with_name('system_layer.sqlite3'))
    from integration.runtime_self_inspection import reasoning_context
    query='Inspect your current capability state recorded in your System Layer.'
    prompt=reasoning_context(runtime,query,selector=lambda _:pytest.fail('No interaction selector for registry read'))
    return runtime,query,prompt

def test_automatic_read_namespace_coverage_and_publication(tmp_path):
    from runtime_observation.evidence_ledger import render_selection,line
    from integration.self_inspection_activation import assess as activation
    r,q,p=routed(tmp_path);ledger=r.context.self_inspection['evidence_ledger']
    assert ledger['contract']=='CapabilityEvidenceLedger/1'
    assert {s['source_type'] for s in ledger['sources'].values()}=={'SYSTEM_CAPABILITY','QUALIFICATION','INFERENCE'}
    assert not any(s['source_type'] in {'OBSERVATION','TRANSITION_RECORD'} for s in ledger['sources'].values())
    raw=json.dumps({'ledger_id':ledger['ledger_id'],'statements':[e['entry_id'] for e in ledger['entries']]})
    text,receipt=render_selection(raw,p)
    assert receipt['coverage']['complete'] and activation(q,p,text)['allowed']
    assert not activation(q,p,text.replace('UNCONFIRMED','OPERATIONAL'))['allowed']
    assert not activation(q,p,'I am operationally capable of everything.')['allowed']

def test_incomplete_selection_rejected_and_handoff_preserved(tmp_path):
    from tests.test_cross_thread_downstream_preservation import run
    r,q,p=routed(tmp_path);ledger=r.context.self_inspection['evidence_ledger']
    ids=[e['entry_id'] for e in ledger['entries']]
    valid=json.dumps({'ledger_id':ledger['ledger_id'],'statements':ids})
    invalid=json.dumps({'ledger_id':ledger['ledger_id'],'statements':ids[:-1]})
    result,calls=run(p,[valid,invalid,invalid])
    assert len(calls)==3 and result.context_admission[-1]['self_explanation']['coverage']['complete']
    assert result.raw_final_response==invalid

def test_tampered_store_receipt_fails_closed(tmp_path):
    import sqlite3
    s=service(tmp_path);put(s,value(tmp_path))
    with sqlite3.connect(s.store.path) as db:db.execute("UPDATE events SET hash='bad'")
    with pytest.raises(ValueError):inspect_capabilities(s.store.path,'owner','owner',['self-inspection-activation'])

def test_whole_publication_gate_distinguishes_record_quotation_from_truth(tmp_path):
    from runtime_observation.evidence_ledger import render_selection
    from data_governance.response_gate import evaluate
    r,q,p=routed(tmp_path);ledger=r.context.self_inspection['evidence_ledger']
    raw=json.dumps({'ledger_id':ledger['ledger_id'],'statements':[e['entry_id'] for e in ledger['entries']]})
    text,_=render_selection(raw,p)
    from data_governance.response_claims import consequential
    assert consequential(text)  # Preserved regression: 'passed' inside a recorded test reference.
    result=evaluate(r,q,generated_text=text,reasoning_input=p)
    assert result['allowed'] and not result['material']
    assert result['recorded_capability_observation']['recorded_not_independently_validated']
    assert result['execution_authority_granted'] is False
    for invalid in (text+'\nI am operational.',text.replace('UNCONFIRMED','OPERATIONAL'),text.splitlines()[0]):
        blocked=evaluate(r,q,generated_text=invalid,reasoning_input=p)
        assert not blocked['allowed'] and blocked['recorded_capability_observation'] is None

@pytest.mark.parametrize('explicit', ['claim','external_current'])
def test_record_quotation_does_not_discharge_explicit_rp_obligation(tmp_path,explicit):
    from runtime_observation.evidence_ledger import render_selection
    from data_governance.response_gate import evaluate
    r,q,p=routed(tmp_path);ledger=r.context.self_inspection['evidence_ledger']
    text,_=render_selection(json.dumps({'ledger_id':ledger['ledger_id'],'statements':[e['entry_id'] for e in ledger['entries']]}),p)
    if explicit=='claim':r.context.material_response_claim={'claim_id':'protected'}
    else:r.context.knowledge_classification=NS(primary_domain='EXTERNAL_CURRENT')
    gate=evaluate(r,q,generated_text=text,reasoning_input=p)
    assert gate['material'] and not gate['allowed'] and gate['recorded_capability_observation'] is None
