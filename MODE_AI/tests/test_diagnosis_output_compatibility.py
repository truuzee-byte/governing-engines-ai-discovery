import json
from pathlib import Path
from types import SimpleNamespace as NS
import pytest
from tests.test_learning_diagnosis_routing import inspect
from tests.test_diagnosis_recommendation_contract import insufficient

def request(tmp_path,scoped=True,admitted=None):
    r,p=inspect(tmp_path)
    from agents.reasoning_agent import ReasoningAgent
    a=ReasoningAgent.__new__(ReasoningAgent);a._governed_request=scoped
    a.provider='offline';a.model='offline';a.temperature=0;a.max_tokens=1800
    a._persist_telemetry=lambda telemetry:(None,None)
    calls=[]
    def create(**kw):
        calls.append(kw)
        return NS(output_text='{"unchanged":null}',usage=None,id='offline-only',model='offline',status='completed')
    a.client=NS(responses=NS(create=create))
    a._call_model(admitted if admitted is not None else p if scoped else 'ordinary unrelated request',interaction_id='i',reasoning_id='r',stage='REASONING_FINAL')
    return r,calls[0]

def test_provider_constrains_raw_json_for_learning_only(tmp_path):
    r,kw=request(tmp_path)
    assert kw['text']['format']['type']=='json_schema'
    assert kw['text']['format']['strict'] is True
    assert kw['text']['format']['schema']['type']=='object'
    _,other=request(tmp_path,False)
    assert 'text' not in other

def test_missing_evidence_enum_comes_from_recorded_classes_not_wording(tmp_path):
    from runtime_observation.learning_inspection import output_format
    r,p=inspect(tmp_path);l=r.context.self_inspection['evidence_ledger']
    fmt=output_format(l);nongap=fmt['schema']['properties']['diagnosis']['anyOf'][0]
    enum=nongap['properties']['missing_evidence']['items']['properties']['evidence_id']['enum']
    observed=next(e for e in l['entries'] if e['field']=='learning_class_LIVE')
    unknown=next(e for e in l['entries'] if e['field']=='objective_unknowns')
    assert observed['entry_id'] not in enum and unknown['entry_id'] in enum
    observed['value']='UNAVAILABLE wording in an observed historical source'
    unknown['value']='OBSERVED wording does not make absent evidence available'
    assert enum==output_format(l)['schema']['properties']['diagnosis']['anyOf'][0]['properties']['missing_evidence']['items']['properties']['evidence_id']['enum']

@pytest.mark.parametrize('wrapper',[lambda s:'```json\n'+s+'\n```',lambda s:'Prose before '+s,lambda s:s+'\nProse after',lambda s:'```json\n{broken\n```'])
def test_strict_transport_remains_fail_closed(tmp_path,wrapper):
    from runtime_observation.evidence_ledger import render_selection
    r,p=inspect(tmp_path);l=r.context.self_inspection['evidence_ledger']
    raw=json.dumps({'ledger_id':l['ledger_id'],'statements':[e['entry_id'] for e in l['entries']],'diagnosis':insufficient(l)})
    with pytest.raises(ValueError):render_selection(wrapper(raw),p)

def test_raw_valid_shape_and_nulls_publish_unchanged(tmp_path):
    from runtime_observation.evidence_ledger import render_selection
    r,p=inspect(tmp_path);l=r.context.self_inspection['evidence_ledger'];v=insufficient(l)
    text,receipt=render_selection(json.dumps({'ledger_id':l['ledger_id'],'statements':[e['entry_id'] for e in l['entries']],'diagnosis':v}),p)
    assert '"gap":null' in text and '"recommendation":null' in text
    assert receipt['coverage']['complete']

def test_wrong_citation_class_still_rejected_without_relabeling(tmp_path):
    from runtime_observation.learning_inspection import validate
    r,p=inspect(tmp_path);l=r.context.self_inspection['evidence_ledger'];v=insufficient(l)
    observed=next(e for e in l['entries'] if e['field']=='learning_class_LIVE')
    v['evidence_ids'].append(observed['entry_id']);v['missing_evidence'][0]['evidence_id']=observed['entry_id']
    with pytest.raises(PermissionError):validate(l,v,[e['entry_id'] for e in l['entries']])
    assert observed['evidence_class']=='OBSERVED'

def test_schema_preserves_supported_gap_branch_and_authority(tmp_path):
    from runtime_observation.learning_inspection import output_format
    r,p=inspect(tmp_path);fmt=output_format(r.context.self_inspection['evidence_ledger'])
    branches=fmt['schema']['properties']['diagnosis']['anyOf']
    assert branches[0]['properties']['recommendation']=={'type':'null'}
    gap=branches[1]
    assert gap['properties']['status']['enum']==['EVIDENCE_BACKED_GAP']
    assert gap['properties']['recommendation']['properties']['execution_authority']['enum']==[False]
    assert gap['properties']['recommendation']['properties']['requires_operator_authorization']['enum']==[True]

def test_preserved_fenced_output_not_silently_repaired(tmp_path):
    from integration.strict_json import load_payload
    stages=json.loads(Path('artifacts/diagnosis_recommendation_contract_20261021/RAW_MODEL_STAGES.json').read_text(encoding='utf-8'))
    for stage in stages:
        with pytest.raises(ValueError):load_payload(stage['exact_output'])

def test_unrelated_governed_capacity_stage_keeps_its_request_format(tmp_path,monkeypatch):
    from tests.test_objective_diagnosis_bridge import fixture
    r,q,p,_=fixture(tmp_path,monkeypatch)
    _,kw=request(tmp_path,admitted=p)
    assert 'text' not in kw
