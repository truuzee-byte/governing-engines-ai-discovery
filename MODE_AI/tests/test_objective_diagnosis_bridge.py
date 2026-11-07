"""Objective evidence must come from owned references, not prewritten diagnoses."""
import json
from pathlib import Path
from types import SimpleNamespace as NS
import pytest
from tests.test_capability_registry_inspection import service,put,value

PROMPT=Path('artifacts/objective_diagnosis_bridge_20261021/BEHAVIORAL_PROMPT.txt').read_text(encoding='utf-8')

def fixture(tmp_path,monkeypatch,limit=24,need=25):
 import system_layer.capability_inspection as reader
 monkeypatch.setattr(reader,'WORKSPACE',tmp_path,raising=False)
 source=tmp_path/'select.py'
 source.write_text('def select(selection):\n    ids=selection.get("statements")\n    if not 1 <= len(ids) <= '+str(limit)+':\n        raise ValueError("bound")\n    return ids\n')
 import hashlib
 v=value(tmp_path,cid='evidence-selection');v['capability']['name']='Evidence selection with handoff preservation'
 v['evidence_inventory']['evidence']=[{'kind':'CODE','path':str(source.resolve()),'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'locator':'select','scope':'bounded fixture source','result':'PASS'}]
 from system_layer.capability_inspection import assess
 v['evidence_inventory']['assessment']=assess(v['evidence_inventory']['evidence'])
 from system_layer.creation.service import SystemLayer
 s=SystemLayer(tmp_path/'system_layer.sqlite3',NS(context=NS(identity=NS(operator_id='owner'))));put(s,v)
 r=NS(context=NS(identity=NS(operator_id='owner'),active_thread=NS(thread_id='thread')),understanding_engine=NS(store=NS(path=tmp_path/'understanding.sqlite3')))
 from integration.runtime_self_inspection import reasoning_context
 q=PROMPT.replace('25 independent',str(need)+' independent')
 return r,q,reasoning_context(r,q),source

def proposal(r,need=25,limit=24):
 ledger=r.context.self_inspection['evidence_ledger']
 fact=next(e for e in ledger['entries'] if e['field']=='inspected_capacity')
 return {'ledger_id':ledger['ledger_id'],'statements':[e['entry_id'] for e in ledger['entries']],
  'diagnosis':{'status':'BLOCKED_BY_INSPECTED_BOUND' if need>limit else 'BOUND_SUFFICIENT_ONLY',
   'required_capacity':need,'observed_capacity':limit,'evidence_ids':[fact['entry_id']],
   'gap':'The inspected statement bound is smaller than the objective requires.' if need>limit else 'This bound does not prevent the stated capacity.',
   'rationale':'Each independent required statement needs a slot, so this bound prevents complete output.' if need>limit else 'The measured bound can contain the requested number, but this is not operational proof.',
   'recommendation':{'component':fact['value']['component'],'change':'Review a bounded increase with coverage and size regressions.' if need>limit else 'No capacity change justified by this evidence.',
    'requires_operator_authorization':True,'execution_authority':False}}}

def test_objective_locates_owned_source_and_exposes_gap_not_canned_answer(tmp_path,monkeypatch):
 r,q,p,source=fixture(tmp_path,monkeypatch)
 assert r.context.self_inspection['tool_request']['tool']=='inspect_objective_sources'
 ledger=r.context.self_inspection['evidence_ledger']
 assert ledger['objective']['subject']=='evidence selection'
 assert any(e['field']=='inspected_capacity' and e['value']['maximum']==24 for e in ledger['entries'])
 assert not any(e['field'] in {'diagnosis','recommendation'} for e in ledger['entries'])
 assert any(e['field']=='inspected_capacity' and e['value']['component']==str(source)+'#select' for e in ledger['entries'])

@pytest.mark.parametrize('need,limit',[(25,24),(31,11),(7,40)])
def test_actual_bounds_not_qualification_values(tmp_path,monkeypatch,need,limit):
 r,q,p,_=fixture(tmp_path,monkeypatch,limit,need)
 from runtime_observation.evidence_ledger import render_selection,assess_rendered
 from integration.self_inspection_activation import assess
 text,receipt=render_selection(json.dumps(proposal(r,need,limit)),p)
 assert receipt['coverage']['complete'] and assess(q,p,text)['allowed']
 assert assess_rendered(text,p)['allowed']
 assert text.startswith('OBSERVED') and '\nINFERRED ' in text

@pytest.mark.parametrize('fault',['invented_bound','invented_id','empty_rationale','authority','foreign_component','omit_unknown','fake_observed','no_diagnosis'])
def test_diagnosis_falsifiers_fail_closed(tmp_path,monkeypatch,fault):
 r,q,p,_=fixture(tmp_path,monkeypatch);v=proposal(r)
 if fault=='invented_bound':v['diagnosis']['observed_capacity']=99
 if fault=='invented_id':v['diagnosis']['evidence_ids']=['E999']
 if fault=='empty_rationale':v['diagnosis']['rationale']=''
 if fault=='authority':v['diagnosis']['recommendation']['execution_authority']=True
 if fault=='foreign_component':v['diagnosis']['recommendation']['component']='Learning.rewrite_all'
 if fault=='omit_unknown':v['statements']=[e['entry_id'] for e in r.context.self_inspection['evidence_ledger']['entries'] if e['evidence_class']!='UNAVAILABLE']
 if fault=='fake_observed':v['diagnosis']['evidence_class']='OBSERVED'
 if fault=='no_diagnosis':del v['diagnosis']
 from runtime_observation.evidence_ledger import render_selection
 with pytest.raises((PermissionError,ValueError)):render_selection(json.dumps(v),p)

def test_unregistered_subject_retains_unavailable(tmp_path,monkeypatch):
 r,q,p,_=fixture(tmp_path,monkeypatch)
 from integration.runtime_self_inspection import reasoning_context
 reasoning_context(r,q.replace('evidence selection','unknown widgets'))
 assert r.context.self_inspection['tool_request'] is None

def test_changed_source_is_current_observation_not_old_validation(tmp_path,monkeypatch):
 r,q,p,source=fixture(tmp_path,monkeypatch)
 source.write_text(source.read_text().replace('<= 24','<= 12'))
 from integration.runtime_self_inspection import reasoning_context
 reasoning_context(r,q);ledger=r.context.self_inspection['evidence_ledger']
 fact=next(e for e in ledger['entries'] if e['field']=='inspected_capacity')
 assert fact['value']['maximum']==12
 assert 'CHANGED_SINCE_REGISTRY' in json.dumps(ledger)

def test_outside_source_cannot_be_read(tmp_path,monkeypatch):
 r,q,p,source=fixture(tmp_path,monkeypatch)
 import system_layer.capability_inspection as reader
 monkeypatch.setattr(reader,'WORKSPACE',tmp_path/'other')
 from integration.runtime_self_inspection import reasoning_context
 reasoning_context(r,q)
 assert not any(e['field']=='inspected_capacity' for e in r.context.self_inspection['evidence_ledger']['entries'])

def test_real_agent_stages_preserve_model_authored_diagnosis(tmp_path,monkeypatch):
 r,q,p,_=fixture(tmp_path,monkeypatch);v=proposal(r)
 from tests.test_cross_thread_downstream_preservation import run
 result,calls=run(p,[json.dumps(v)]*3)
 assert len(calls)==3 and 'INFERRED' in result.final_response
 assert 'Review a bounded increase' in result.final_response
 assert all('mandatory diagnosis object' in str(call) for call in calls)

def test_opposite_guard_is_not_fabricated_as_capacity(tmp_path,monkeypatch):
 r,q,p,source=fixture(tmp_path,monkeypatch)
 source.write_text(source.read_text().replace('if not 1','if 1'))
 from integration.runtime_self_inspection import reasoning_context
 from integration.self_inspection_activation import assess
 p=reasoning_context(r,q)
 assert not assess(q,p)['allowed']
 assert not any(e['field']=='inspected_capacity' for e in r.context.self_inspection['evidence_ledger']['entries'])

def test_scope_and_publication_authority_not_changed(tmp_path,monkeypatch):
 r,q,p,source=fixture(tmp_path,monkeypatch)
 from runtime_observation.evidence_ledger import render_selection
 from data_governance.response_gate import evaluate
 text,_=render_selection(json.dumps(proposal(r)),p)
 gate=evaluate(r,q,text,reasoning_input=p)
 assert gate['allowed'] and gate['execution_authority_granted'] is False
 assert gate['materiality']['coverage']=='BOUNDED_OBJECTIVE_DIAGNOSIS_NOT_VALIDATED'
 assert gate['recorded_capability_observation']['model_diagnosis_class']=='INFERRED_NOT_REPAIR_APPROVAL'
