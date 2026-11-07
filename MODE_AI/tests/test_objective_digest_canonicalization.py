import json
from pathlib import Path
from copy import deepcopy
from types import SimpleNamespace as NS
import pytest
from learning.contracts import digest as objective_digest
from runtime_observation.transformation_provenance import digest as provenance_digest

EXACT=Path('artifacts/learning_diagnosis_routing_20261021/BEHAVIORAL_PROMPT.txt').read_text(encoding='utf-8-sig').strip()

def inspect(tmp_path,query=EXACT):
    from integration.runtime_self_inspection import reasoning_context
    r=NS(context=NS(identity=NS(operator_id='owner'),active_thread=NS(thread_id='fresh')),
         understanding_engine=NS(store=NS(path=tmp_path/'understanding.sqlite3')))
    p=reasoning_context(r,query)
    return r,p

def test_exact_preserved_objective_binds_at_publication_gate(tmp_path):
    from integration.self_inspection_activation import assess
    r,p=inspect(tmp_path)
    assert r.context.self_inspection['evidence_ledger']['objective']['query_hash']==objective_digest(EXACT)
    assert assess(EXACT,p)['allowed']

@pytest.mark.parametrize('suffix',[' plain ASCII',' \u2192 Unicode','\nnext line','\r\nnext line',' e\u0301',' \u00e9'])
def test_both_objective_paths_use_gate_digest_without_text_rewriting(tmp_path,suffix):
    from runtime_observation.inspection_coverage import derive
    from integration.self_inspection_activation import assess
    q=EXACT+suffix;r,p=inspect(tmp_path,q);ledger=r.context.self_inspection['evidence_ledger']
    assert ledger['objective']['query_hash']==objective_digest(q)
    assert derive(q,ledger)['prompt_hash']==objective_digest(q)
    assert assess(q,p)['allowed']

@pytest.mark.parametrize('other',[EXACT.replace('\u2192','->'),EXACT+' ',EXACT+'\n',EXACT.replace('\n','\r\n'),EXACT+' materially different',EXACT.replace('Learning','Memory'),EXACT.replace('operator','other operator')])
def test_different_text_never_silently_collapses_identity(other):
    assert objective_digest(other)!=objective_digest(EXACT)

def test_provenance_and_ascii_objective_digest_contracts_unchanged():
    assert objective_digest('ASCII objective')==provenance_digest('ASCII objective')
    assert objective_digest('ASCII objective')=='f31cfcc96cd003ac75660d152d7d7aa0059cbe672aa91ec751c9c814ecc1bf81'
    assert objective_digest(EXACT)!=provenance_digest(EXACT)

def test_genuine_mismatch_still_fails_closed(tmp_path):
    from integration.self_inspection_activation import assess
    r,p=inspect(tmp_path)
    assert not assess(EXACT+' changed objective',p)['allowed']

def test_full_admission_composition_retains_exact_binding(tmp_path):
    from data_governance.context_admission import Admission
    from integration.self_inspection_activation import assess
    r,p=inspect(tmp_path);a=Admission('owner','fresh')
    a.consider('SYSTEM_POLICY','policy','Use only inspected evidence.',source='Test policy')
    a.include(p);a.consider('OPERATOR_INPUT','current',EXACT,source='OperatorInput')
    assert assess(EXACT,a.finish())['allowed']

def test_no_unrequested_unicode_or_malformed_text_normalization():
    assert objective_digest('caf\u00e9')!=objective_digest('cafe\u0301')
    assert objective_digest('')!=objective_digest(' ')
    assert objective_digest('{"objective":')!=objective_digest('{"objective":""}')
    with pytest.raises(UnicodeEncodeError):objective_digest('\ud800')

def test_registered_capacity_objective_uses_same_unicode_binding(tmp_path,monkeypatch):
    from tests.test_objective_diagnosis_bridge import fixture
    from integration.runtime_self_inspection import reasoning_context
    from integration.self_inspection_activation import assess
    r,q,p,_=fixture(tmp_path,monkeypatch)
    q+=' Evidence \u2192 diagnosis.';p=reasoning_context(r,q)
    assert r.context.self_inspection['evidence_ledger']['objective']['query_hash']==objective_digest(q)
    assert assess(q,p)['allowed']
