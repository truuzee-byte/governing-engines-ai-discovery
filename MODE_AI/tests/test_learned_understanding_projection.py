"""Governed inference projection; fixtures test plumbing, not Learning Expression."""
import json
from types import SimpleNamespace as NS
import pytest
from tests.test_learning import built,approve
from tests.test_learning_understanding_bridge import adopt,adoption
from integration.conversation_understanding import prompt_context
from learning.contracts import digest
from data_governance.context_admission import Admission,verify

@pytest.fixture(scope='module')
def learned(tmp_path_factory):
    r,_,candidate=built(tmp_path_factory.mktemp('projection'),'canonical')
    record=approve(r,candidate);receipt=adopt(r,adoption(r,record))
    return r,record,receipt

def test_relevant_projection_and_audit_links(learned):
    r,source,receipt=learned
    before=r.understanding_engine.store.get('operator',receipt['understanding_id']).to_dict()
    p=prompt_context(r,query='Add two numbers')
    verify(p,'thread');payload=json.loads(str(p))
    assert payload['projection_contract']=='LearnedInference/1'
    experience=payload['experiences'][0]
    assert experience['learned_proposition']['contrast']==source['lineage']['canonical_v2']['outcome_analysis']['root_cause']['contrast']
    assert experience['provenance']['source_hash']==digest(source)
    assert experience['provenance']['learning_id']==source['learning_id']
    assert experience['provenance']['rp_decision_id']==source['lineage']['outcome']['rp']['decision_id']
    assert experience['provenance']['evidence_refs']==source['evidence']
    assert experience['admissibility']['source_revalidated'] is True
    assert 'execution authorization' in payload['authority']
    assert r.understanding_engine.store.get('operator',receipt['understanding_id']).to_dict()==before

def test_irrelevant_query_and_missing_query_excluded(learned):
    r,_,_=learned
    assert 'BOUNDED_HISTORICAL_UNDERSTANDING' not in str(prompt_context(r,query='Explain chlorophyll in leaves'))
    assert 'BOUNDED_HISTORICAL_UNDERSTANDING' not in str(prompt_context(r))

def test_inadmissible_source_excluded(learned,monkeypatch):
    r,_,_=learned
    def denied(*args):raise PermissionError('Source no longer admissible')
    monkeypatch.setattr(r.learning_service,'understanding_candidate',denied)
    assert 'BOUNDED_HISTORICAL_UNDERSTANDING' not in str(prompt_context(r,query='Add two numbers'))

def test_snapshot_bodies_removed_and_size_reduced(learned):
    r,source,_=learned
    text=str(prompt_context(r,query='Add two numbers'))
    assert '"observed_outcome"' not in text
    assert '"outcome"' not in text and '"lineage"' not in text
    assert '"record"' not in text
    assert len(text.encode())<16384
    assert len(text)<len(json.dumps(source))/10

def test_oversized_semantics_fail_closed_without_truncation(learned,monkeypatch):
    import integration.conversation_understanding as owner
    r,_,_=learned
    monkeypatch.setattr(owner,'LEARNED_PROJECTION_LIMIT',1)
    text=str(prompt_context(r,query='Add two numbers'))
    assert 'BOUNDED_HISTORICAL_UNDERSTANDING' not in text
    assert 'could not be included' in text

def test_exact_scoped_other_project_excluded(learned):
    r,source,_=learned;selection=r._learned_understanding_scope
    try:
        r._learned_understanding_scope=('thread',{**source['scope'],'project':'unrelated-project'},{'first_operand':2})
        assert 'BOUNDED_HISTORICAL_UNDERSTANDING' not in str(prompt_context(r,query='Add two numbers'))
    finally:r._learned_understanding_scope=selection

def test_reasoning_stages_receive_measured_semantics_not_bodies(learned,monkeypatch):
    from agents.reasoning_agent import ReasoningAgent,ModelCallResult
    r,_,_=learned
    a=Admission('operator','thread');a.consider('OPERATOR_INPUT','q','Add two numbers',source='Test query');a.include(prompt_context(r,query='Add two numbers'))
    agent=ReasoningAgent.__new__(ReasoningAgent);agent.provider='fixture';agent.model='fixture'
    seen=[]
    def call(prompt,**kwargs):
        verify(prompt,'thread');seen.append(str(prompt))
        return ModelCallResult('A bounded proposed response.',NS())
    monkeypatch.setattr(agent,'_call_model',call)
    result=agent.generate('Mode','Reasoning',{'purpose':'Test context delivery','schema':[],'constraints':[]},a.finish())
    assert len(seen)==3
    assert all('"second_operand"' in s and '"baseline"' in s and '"intervention"' in s for s in seen)
    assert all('"observed_outcome"' not in s for s in seen)
    assert result.context_admission


def test_explicit_variable_selects_material_semantics_only(learned):
    from copy import deepcopy
    from integration.conversation_understanding import _relevant_experiences
    r,_,_=learned
    actual=json.loads(str(prompt_context(r,query='Add two numbers')))['experiences'][0]
    other=deepcopy(actual);other['learned_proposition']['measured_variable']='first_operand'
    chosen=_relevant_experiences('What was measured for the second operand?', [actual,other])
    assert chosen==[actual]


def test_duplicate_semantics_need_only_one_source_projection(learned):
    from copy import deepcopy
    from integration.conversation_understanding import _relevant_experiences
    r,_,_=learned
    actual=json.loads(str(prompt_context(r,query='Add two numbers')))['experiences'][0]
    duplicate=deepcopy(actual);duplicate['provenance']['learning_id']='another-approved-source'
    selected=_relevant_experiences('Add two numbers',[actual,duplicate])
    assert selected==[actual]


def test_numeric_coincidence_is_not_query_relevance():
    from integration.conversation_understanding import _query_relevant
    scope={'capability':'Achieve output 43 on disposable amber device'}
    assert not _query_relevant('Explain chlorophyll 43 in leaves',scope)
    assert _query_relevant('Choose the amber setting for output 43',scope)


def test_quantifier_only_match_is_not_query_relevance(learned):
    r,_,_=learned
    assert 'BOUNDED_HISTORICAL_UNDERSTANDING' not in str(prompt_context(r,query='Explain two leaves'))
    assert 'BOUNDED_HISTORICAL_UNDERSTANDING' in str(prompt_context(r,query='Add these numbers'))
