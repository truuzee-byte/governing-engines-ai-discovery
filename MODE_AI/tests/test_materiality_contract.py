import json
from copy import deepcopy
from pathlib import Path
import pytest


def ledger():
    source={'source_type':'PRIMARY_RECORD','reference':{'path':'evidence.json','sha256':'a'*64,'locator':'case-Y'},'temporal_scope':{'version':1,'scope':'historical-case-Y'}}
    entry={'entry_id':'E1','source_id':'s','field':'fact','scope':'case-Y','evidence_class':'OBSERVED','value':{'fact':'measured result','failure':False,'contradictions':[],'authority':'none','qualification':'case-Y-only'},'directly_recorded':True,'derived':False,'support':[],'recorded_alternatives':[],'conflicts':[]}
    return {'contract':'CapabilityEvidenceLedger/1','ledger_id':'fixture','operator_id':'owner','thread_id':'thread','objective':{'query_hash':'q'},'sources':{'s':source},'entries':[entry], 'execution_authority':False}


def assess(value):
    from runtime_observation.materiality_contract import evaluate
    return evaluate(value)


def test_unknown_retained_despite_size():
    u=ledger();u['entries'][0]['value']='x'*100000
    result=assess(u)
    assert result['receipt']['retained_ids']==['E1']
    assert result['receipt']['size_gate']=='BLOCK'
    assert result['receipt']['decisions'][0]['materiality_state']=='UNKNOWN MATERIALITY'


def test_identity_representative_only_with_scoped_primary_provenance():
    u=ledger();other=deepcopy(u['entries'][0]);other['entry_id']='E2';u['entries'].append(other)
    result=assess(u);r=result['receipt']
    assert r['excluded_ids']==['E2'] and r['retained_ids']==['E1']
    decision=r['decisions'][1]
    assert decision['representative']=='E1' and decision['basis']=='EXACT_SCOPED_PRIMARY_RECORD_IDENTITY'
    assert decision['source_locator']['reference']['sha256']=='a'*64
    assert u['entries'][1]['entry_id']=='E2'


@pytest.mark.parametrize('field,value',[
 ('value',{'fact':'different unique measurement'}),('conflicts',['contradiction']),
 ('value',{'fact':'measured result','failure':True}),('value',{'authority':'operator-approved'}),
 ('value',{'qualification':'other-scope'}),('recorded_alternatives',['prior failure']),
 ('scope','other-case'),('evidence_class','UNAVAILABLE'),('derived',True)])
def test_distinct_fact_failure_conflict_authority_qualification_never_dropped(field,value):
    u=ledger();v=deepcopy(u['entries'][0]);v.update(entry_id='E2');v[field]=value;u['entries'].append(v)
    assert assess(u)['receipt']['excluded_ids']==[]


@pytest.mark.parametrize('change',['temporal','provenance','no-primary','no-time'])
def test_wording_alone_cannot_substitute(change):
    u=ledger();u['sources']['t']=deepcopy(u['sources']['s']);v=deepcopy(u['entries'][0]);v.update(entry_id='E2',source_id='t');u['entries'].append(v)
    if change=='temporal':u['sources']['t']['temporal_scope']['version']=2
    elif change=='provenance':u['sources']['t']['reference']['sha256']='b'*64
    elif change=='no-primary':u['sources']['t']['source_type']='SUMMARY'
    else:u['sources']['t'].pop('temporal_scope')
    assert assess(u)['receipt']['excluded_ids']==[]


def test_exact_universe_stays_accounted_and_blocked():
    u=json.loads(Path('C:/MODE_AI/artifacts/diagnostic_evidence_bound_trace_20261021/RECONSTRUCTED_PRE_BOUND_LEDGER.json').read_text())
    result=assess(u);r=result['receipt']
    assert r['universe_count']==17 and len(r['decisions'])==17
    assert r['excluded_ids']==[] and r['package_bytes']==105417
    assert r['size_gate']=='BLOCK' and result['ledger']==u


def test_duplicate_ids_rejected():
    u=ledger();u['entries'].append(deepcopy(u['entries'][0]))
    with pytest.raises(ValueError):assess(u)


def test_learning_route_receipt_precedes_unchanged_gate(tmp_path):
    from types import SimpleNamespace as NS
    from integration.runtime_self_inspection import reasoning_context
    query=Path('C:/MODE_AI/artifacts/evidence_plan_composition_20261021/BEHAVIORAL_PROMPT.txt').read_text().strip()
    r=NS(context=NS(identity=NS(operator_id='owner'),active_thread=NS(thread_id='thread')),understanding_engine=NS(store=NS(path=tmp_path/'unused.sqlite')))
    with pytest.raises(PermissionError,match='Learning diagnostic evidence bound exceeded'):reasoning_context(r,query)
    assert r.context.diagnostic_materiality['receipt']['size_gate']=='BLOCK'
    assert not (tmp_path/'unused.sqlite').exists()
