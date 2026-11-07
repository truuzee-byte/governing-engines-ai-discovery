import pytest
from tests.test_execution_spine import envelope, authorize, runtime

@pytest.mark.parametrize('nested', [False, True])
@pytest.mark.parametrize('expression,expected', [('file:calculator.py','FAILED'),('file:absent.py','PASSED'),('unknown prohibition','UNPROVEN')])
def test_prohibition_polarity(tmp_path, nested, expression, expected):
    e=envelope(tmp_path/'artifact')
    source=e['understanding']['requirements'][0] if nested else e['understanding']
    source['prohibited_states']=[expression]
    out=runtime(tmp_path).build_runtime.execute(authorize(e))
    checks=[c for c in out['build']['validation_results'] if c.get('obligation',{}).get('polarity')=='NEGATIVE']
    assert len(checks)==1 and checks[0]['state']==expected
    assert checks[0]['obligation']['authority_class']=='AUTHORITATIVE'
    if nested: assert checks[0]['obligation']['parent_id']=='add'
    assert (out['build']['validation_status']=='PASS') == (expected=='PASSED')

@pytest.mark.parametrize('field,value', [
 ('completion_conditions',{'kind':'PREFERENCE','text':'file:absent.txt'}),
 ('completion_conditions',{'unknown':'unsupported'}),
 ('completion_conditions',{'text':'validation commands passed','unknown':'unmet condition'}),
 ('completion_conditions',{'kind':'UNKNOWN','text':'validation commands passed'}),
 ('completion_conditions',{'text':'validation commands passed','completion_condition':False}),
 ('evidence_requirements','file:absent.txt'),
 ('authority_requirements','file:absent.txt'),
])
def test_authoritative_unresolved(tmp_path, field, value):
    e=envelope(tmp_path/'artifact');e['understanding'][field]=[value]
    out=runtime(tmp_path).build_runtime.execute(authorize(e))
    assert out['build']['validation_status']=='UNPROVEN'
    assert out['state']!='BUILD_PASS_RP_CONFIRMED'

@pytest.mark.parametrize('field', ['receipt_requirements','governance_constraints'])
def test_missing_contract_obligation(tmp_path,field):
    e=envelope(tmp_path/'artifact');e['request'][field]=['file:absent.txt']
    out=runtime(tmp_path).build_runtime.execute(authorize(e))
    assert out['build']['validation_status']=='UNPROVEN'

@pytest.mark.parametrize('ready', [True,False,None])
def test_context_readiness(tmp_path,ready):
    from types import SimpleNamespace
    r=runtime(tmp_path)
    r.context.assembled_context=SimpleNamespace(runtime=SimpleNamespace(context_ready=ready))
    out=r.build_runtime.execute(envelope(tmp_path/'artifact'))
    record=r.runtime_observation_collector.store.load_record('operator',out['observation_ids'][-1])
    assert record.context_ready is ready
    assert ('CONTEXT_ASSEMBLY_ISSUE' in [t.value for t in record.observation_types]) == (ready is False)

@pytest.mark.parametrize('value', [
 {'kind':'PREFERENCE','text':'receipt written'},
])
def test_malformed_receipt_predicate_cannot_be_deferred(tmp_path,value):
    e=envelope(tmp_path/'artifact');e['understanding']['completion_conditions']=[value]
    out=runtime(tmp_path).build_runtime.execute(authorize(e))
    assert out['build']['validation_status']=='UNPROVEN'

def test_metadata_cannot_violate_prohibition_after_validation(tmp_path):
    e=envelope(tmp_path/'artifact')
    e['understanding']['prohibited_states']=['file:.builder_metadata/build_receipt.json']
    out=runtime(tmp_path).build_runtime.execute(authorize(e))
    assert out['build']['validation_status']=='FAIL'

@pytest.mark.parametrize('group,kind', [('completion','COMPLETION'),('evidence','EVIDENCE'),('governance','GOVERNANCE'),('receipt','RECEIPT')])
def test_native_contract_semantics_reach_receipt(tmp_path,group,kind):
    import json
    from pathlib import Path
    e=envelope(tmp_path/'artifact')
    if group=='governance': e['request']['governance_constraints']=['file:calculator.py']
    if group=='receipt': e['request']['receipt_requirements']=['build_receipt']
    out=runtime(tmp_path).build_runtime.execute(authorize(e))
    assert out['build']['validation_status']=='PASS'
    receipt=json.loads(Path(out['build']['receipt_path']).read_text())
    checks=[c for c in receipt['validation_results'] if c.get('group')==group and not c.get('obligation')]
    assert checks
    for check in checks:
        item=check['contract_obligation']
        assert item['obligation_class']==kind and item['polarity']=='POSITIVE'
        assert item['id'] and item['source'] and item['authority_class']=='AUTHORITATIVE'
