import json
from pathlib import Path
import pytest
from data_governance.context_admission import Admission
from runtime_observation.evidence_ledger import normalize, render_selection, line, PREFIX as LEDGER_PREFIX
from runtime_observation.inspection_coverage import derive, evaluate, require, require_published, from_prompt, PREFIX, CoverageIncomplete

ROOT = Path(__file__).resolve().parents[1]
QUERY = (ROOT/'artifacts/evidence_selection_coverage_20261020/BEHAVIORAL_PROMPT.txt').read_text(encoding='utf-8').rstrip('\n')

@pytest.fixture
def ledger():
    return normalize(json.loads((ROOT/'artifacts/transformation_provenance_20261020/CONTROL_EVIDENCE.json').read_text(encoding='utf-8')))

def minimal(contract):
    ids = []
    for d in contract['dimensions']:
        if not d['operator_requested']: continue
        for g in d['coverage_groups']:
            if not set(ids).intersection(g['any_of']): ids.append(g['any_of'][0])
    return ids

def sealed(ledger, contract):
    a = Admission(ledger['operator_id'], ledger['thread_id'])
    for name, prefix, value in [('InteractionEvidenceLedger/1', LEDGER_PREFIX, ledger), ('InspectionCoverage/1', PREFIX, contract)]:
        a.consider('RUNTIME', name, prefix+json.dumps(value), source=name,
                   basis={'validation_state':'UNVALIDATED','authority':'READ_ONLY_RUNTIME_EVIDENCE','lineage':[ledger['ledger_id']]})
    return a.finish()

def test_exact_prompt_requires_eight_dimensions_and_minimal_suffices(ledger):
    c = derive(QUERY, ledger); ids = minimal(c); r = evaluate(c, ledger, ids)
    assert all(d['operator_requested'] and d['status']=='COVERED' for d in r['dimensions'])
    assert len(ids) <= 24 and len(ids) < len(ledger['entries'])
    assert 'E039' in ids and {'E033','E045','E064'}.issubset(ids)
    assert not {'E005','E019','E034','E046','E058'}.intersection(ids)

@pytest.mark.parametrize('removed', ['E027','E032','E039','E044','E051','E056','E030','E042','E054','E062','E063','E033','E045','E064'])
def test_each_material_obligation_fails_closed(ledger, removed):
    c=derive(QUERY,ledger); ids=minimal(c)
    assert removed in ids
    with pytest.raises(CoverageIncomplete) as exc: require(sealed(ledger,c),[i for i in ids if i!=removed])
    assert not exc.value.report['complete']

def test_previous_published_selection_is_rejected(ledger):
    ids=['E027','E001','E002','E003','E004','E030','E031','E032','E026','E038','E041','E042','E043','E044','E050','E051','E053','E054','E055','E056','E062','E063']
    with pytest.raises(CoverageIncomplete): require(sealed(ledger,derive(QUERY,ledger)),ids)

def test_order_is_required_not_just_presence(ledger):
    c=derive(QUERY,ledger); ids=minimal(c)
    with pytest.raises(CoverageIncomplete): require(sealed(ledger,c),list(reversed(ids)))

@pytest.mark.parametrize('query', ['Inspect the completed interaction.', 'Do not infer a producer, rule, mutation, or unavailable event.'])
def test_unrequested_dimensions_not_forced(ledger,query):
    c=derive(query,ledger)
    assert all(d['status']=='NOT_REQUESTED' for d in c['dimensions'])
    assert evaluate(c,ledger,['E001'])['complete']

def test_only_requested_dimension_is_enforced(ledger):
    c=derive('Identify producing components and stages.',ledger)
    assert [d['dimension_id'] for d in c['dimensions'] if d['operator_requested']]==['PRODUCING_COMPONENT']
    assert evaluate(c,ledger,['E027','E039','E051'])['complete']

def test_no_relevant_evidence_is_explicit(ledger):
    ledger['entries']=[e for e in ledger['entries'] if e['field']!='operator_presentation']
    c=derive('Identify operator-facing inconsistency.',ledger)
    assert next(d for d in c['dimensions'] if d['operator_requested'])['status']=='NO_RELEVANT_EVIDENCE'

def test_contract_cannot_be_rebound_or_weakened(ledger):
    c=derive(QUERY,ledger); c['dimensions'][0]['operator_requested']=False
    with pytest.raises(PermissionError): from_prompt(sealed(ledger,c))

def test_exact_render_and_publication_recheck(ledger):
    c=derive(QUERY,ledger); p=sealed(ledger,c); ids=minimal(c)
    text,receipt=render_selection(json.dumps({'ledger_id':ledger['ledger_id'],'statements':ids}),p)
    assert receipt['coverage']['complete']
    require_published(p,text)
    with pytest.raises(PermissionError): require_published(p,'Unsupported fallback answer')
    with pytest.raises(PermissionError): require_published(p,text+'\n'+text)
    with pytest.raises(CoverageIncomplete): require_published(p,line(ledger,ledger['entries'][0]))

def test_scope_and_class_validation_precedes_coverage(ledger):
    p=sealed(ledger,derive(QUERY,ledger))
    with pytest.raises(PermissionError,match='Invalid ledger'):render_selection(json.dumps({'ledger_id':ledger['ledger_id'],'statements':['invented']}),p)

def test_reasoning_stages_receive_contract_and_receipt(ledger):
    from tests.test_cross_thread_downstream_preservation import run
    c=derive(QUERY,ledger); ids=minimal(c); raw=json.dumps({'ledger_id':ledger['ledger_id'],'statements':ids})
    result,calls=run(sealed(ledger,c),['Select ledger entries.','Preserve the required coverage.',raw])
    assert len(calls)==3 and all('InspectionCoverage/1' in prompt for prompt,_ in calls)
    assert result.context_admission[-1]['self_explanation']['coverage']['complete']
    assert result.final_response=='\n'.join(line(ledger,next(e for e in ledger['entries'] if e['entry_id']==i)) for i in ids)

def test_reasoning_missing_selection_cannot_fallback(ledger):
    from tests.test_cross_thread_downstream_preservation import run
    raw=json.dumps({'ledger_id':ledger['ledger_id'],'statements':['E001']})
    with pytest.raises(CoverageIncomplete):
        run(sealed(ledger,derive(QUERY,ledger)),['A plausible draft.','A plausible critique.',raw])

def test_recorded_conflict_is_not_silently_resolved():
    p=json.loads((ROOT/'artifacts/transformation_provenance_20261020/CONTROL_EVIDENCE.json').read_text(encoding='utf-8'))
    p['observed']['public_result']['clarification_required']=True
    ledger=normalize(p); c=derive(QUERY,ledger); ids=minimal(c)
    text,receipt=render_selection(json.dumps({'ledger_id':ledger['ledger_id'],'statements':ids}),sealed(ledger,c))
    assert receipt['coverage']['complete'] and 'CORRELATION_DISAGREEMENT_NOT_ADJUDICATED' in text
    assert '"left_value":false' in text and '"right_value":true' in text
