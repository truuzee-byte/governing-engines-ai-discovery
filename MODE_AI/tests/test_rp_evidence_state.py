import json,hashlib
from pathlib import Path
from types import SimpleNamespace as NS
import pytest
from integration.rp_process import ExternalRPProcess

def h(p):return hashlib.sha256(p.read_bytes()).hexdigest()

@pytest.fixture
def external(tmp_path):
    record=tmp_path/'result.json';record.write_text(json.dumps({'claim':'bounded-learning','result':'PASS','scope':'case Y','timestamp':'2026-10-12'}))
    provenance=tmp_path/'provenance.json';provenance.write_text(json.dumps({'operator_id':'owner','source':'preserved controlled case','timestamp':'2026-10-12'}))
    source={'source_id':'source-A','path':'result.json','sha256':h(record),'provenance_path':'provenance.json','provenance_sha256':h(provenance),'temporal_scope':'historical','format':'JSON_RECORDED_RESULT','claim':'bounded-learning'}
    grant={'operator_id':'owner','thread_id':'target','root':str(tmp_path),'sources':[source],'authority_reference':'operator:read-only-evidence'}
    path=tmp_path/'grant.json';path.write_text(json.dumps(grant))
    with_process=[]
    def start():
        p=ExternalRPProcess('C:/REALITY_PRIMACY',path,tmp_path/'unused-ledger',module='reality_primacy.evidence_state');with_process.append(p)
        from integration.rp_evidence_state import EvidenceStateClient
        return EvidenceStateClient(lambda request:p.call('inspect',request),p.public_keys)
    yield NS(start=start,grant=grant,path=path,record=record,provenance=provenance,source=source,quote=record.read_text(),root=tmp_path)
    for p in with_process:p.close()

def test_external_state_returns_historical_provenance_not_self_verification(external):
    c=external.start();q='Artifact records this historical result:\n'+external.quote
    state=c.inspect('owner','target',q);body=c.verify(state,'owner','target',q)
    assert body['records'][0]['temporal_scope']=='historical'
    assert body['records'][0]['evidence_state']=='OBSERVED'
    assert body['records'][0]['provenance'] and body['records'][0]['reported_outcome']=='PASS'
    assert 'current capability' in ' '.join(body['records'][0]['does_not_establish'])
    assert c.claim_text(state,'owner','target',q).strip()=='Artifact records this historical result:'
    with pytest.raises(Exception):c.claim_text(state,'owner','target',q+' I passed this capability.')

def test_self_claim_without_bound_reference_is_not_exempt(external):
    c=external.start();q='I passed this capability.';state=c.inspect('owner','target',q)
    assert c.claim_text(state,'owner','target',q)==q
    assert c.verify(state,'owner','target',q)['evidence_state']!='VERIFIED'

def test_missing_provenance_is_insufficient(external):
    external.provenance.unlink();c=external.start();state=c.inspect('owner','target',external.quote)
    b=c.verify(state,'owner','target',external.quote)
    assert b['records'][0]['evidence_state']=='INSUFFICIENT'
    assert not b['records'][0]['spans'] and b['missing_evidence']

def test_mode_cannot_mutate_signed_classification(external):
    c=external.start();state=c.inspect('owner','target',external.quote)
    from dataclasses import replace
    response=json.loads(state.response_json);response['body']['records'][0]['evidence_state']='VERIFIED'
    altered=replace(state,response_json=json.dumps(response))
    with pytest.raises(Exception):c.verify(altered,'owner','target',external.quote)

def test_actual_unsupported_claim_still_material_after_historical_reference(external):
    c=external.start();q='Historical source:\n'+external.quote+'\nI passed this capability.'
    state=c.inspect('owner','target',q)
    from data_governance.response_claims import consequential
    assert consequential(c.claim_text(state,'owner','target',q))

def test_untyped_historical_pass_phrase_is_not_whitelisted(external):
    c=external.start();q='Historical passes establish my capability.';s=c.inspect('owner','target',q)
    assert c.claim_text(s,'owner','target',q)==q

def test_conflicting_records_remain_insufficient(external):
    second=external.root/'negative.json';second.write_text(json.dumps({'claim':'bounded-learning','result':'FAIL','scope':'case Y'}))
    other={**external.source,'source_id':'source-B','path':'negative.json','sha256':h(second)}
    external.grant['sources'].append(other);external.path.write_text(json.dumps(external.grant))
    c=external.start();q=external.quote+'\n'+second.read_text();b=c.verify(c.inspect('owner','target',q),'owner','target',q)
    assert b['evidence_state']=='INSUFFICIENT' and b['conflicts']
    assert {r['reported_outcome'] for r in b['records']}=={'PASS','FAIL'}

def test_current_report_not_verified_and_missing_scope_cannot_be_historical(external):
    external.grant['sources'][0]['temporal_scope']='current';external.path.write_text(json.dumps(external.grant))
    c=external.start();q=external.quote;b=c.verify(c.inspect('owner','target',q),'owner','target',q)
    assert b['records'][0]['evidence_state']=='REPORTED' and not b['records'][0]['spans']

def test_operator_and_query_binding(external):
    c=external.start();s=c.inspect('owner','target',external.quote)
    with pytest.raises(Exception):c.verify(s,'foreign','target',external.quote)
    with pytest.raises(Exception):c.verify(s,'owner','target',external.quote+'changed')

def test_exact_preserved_request_only_becomes_nonmaterial_with_pinned_provenance(tmp_path):
    from data_governance.response_claims import consequential
    from integration.rp_evidence_state import EvidenceStateClient
    root=Path('C:/MODE_AI');prior=root/'artifacts/diagnosis_output_compatibility_20261021'
    q=(root/'artifacts/learning_evidence_acquisition_plan_20261021/BEHAVIORAL_PROMPT.txt').read_text(encoding='utf-8')
    owner=json.loads((prior/'PUBLICATION_RECEIPT.json').read_text())['operator_id']
    source={'source_id':'previous-diagnosis','path':str((prior/'MODE_EXACT_ANSWER.txt').relative_to(root)),'sha256':h(prior/'MODE_EXACT_ANSWER.txt'),
        'provenance_path':str((prior/'PUBLICATION_RECEIPT.json').relative_to(root)),'provenance_sha256':h(prior/'PUBLICATION_RECEIPT.json'),
        'temporal_scope':'historical','format':'MODE_DIAGNOSIS_LINE','claim':'Learning evidence insufficiency'}
    grant={'operator_id':owner,'thread_id':'target','root':str(root),'sources':[source],'authority_reference':'operator:historical-evidence-read'}
    p=tmp_path/'grant.json';p.write_text(json.dumps(grant))
    process=ExternalRPProcess('C:/REALITY_PRIMACY',p,tmp_path/'unused',module='reality_primacy.evidence_state')
    try:
        c=EvidenceStateClient(lambda r:process.call('inspect',r),process.public_keys);state=c.inspect(owner,'target',q)
        assert consequential(q) and not consequential(c.claim_text(state,owner,'target',q))
    finally:process.close()


def test_real_gate_preserves_fresh_claim_obligation(external):
    from data_governance.context_admission import Admission
    from integration.rp_evidence_state import reasoning_context
    from data_governance.response_gate import evaluate
    c=external.start()
    runtime=NS(context=NS(identity=NS(operator_id='owner'),active_thread=NS(thread_id='target')),evidence_state_client=c)
    q='Recorded evidence:\n'+external.quote
    admitted=reasoning_context(runtime,q)
    assert evaluate(runtime,q,reasoning_input=admitted)['allowed']
    q+='\nI passed this capability.'
    admitted=reasoning_context(runtime,q)
    result=evaluate(runtime,q,reasoning_input=admitted)
    assert not result['allowed'] and result['material']
    assert 'Required scoped current RP confirmation unavailable' in result['reasons']


def test_changed_source_is_unavailable(external):
    external.record.write_text('altered')
    c=external.start();q=external.quote;b=c.verify(c.inspect('owner','target',q),'owner','target',q)
    assert b['records'][0]['evidence_state']=='UNAVAILABLE' and not b['records'][0]['spans']


def test_temporal_scope_required(external):
    del external.grant['sources'][0]['temporal_scope']
    external.path.write_text(json.dumps(external.grant))
    with pytest.raises(Exception):external.start()
