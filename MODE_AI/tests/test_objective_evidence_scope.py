"""Fail-closed objective scope, not generalized evidence discovery qualification."""
from pathlib import Path
from types import SimpleNamespace as NS
import pytest
from integration.self_inspection_activation import objective_evidence_requirements, assess, bounded_result
from integration.runtime_self_inspection import reasoning_context
from data_governance.response_gate import governed_interaction

PROMPT=Path('artifacts/learning_objective_self_diagnosis_20261020/BEHAVIORAL_PROMPT.txt').read_text(encoding='utf-8')

def runtime():
    return NS(context=NS(identity=NS(operator_id='owner'),active_thread=NS(thread_id='thread')))

@pytest.mark.parametrize('subject',['Learning','Memory','Retrieval','Understanding'])
def test_subject_independent_objective_requirements(subject):
    q=PROMPT.replace('Learning',subject)
    r=objective_evidence_requirements(q)
    assert r['subject']==subject
    assert set(r['required_classes'])=={'SYSTEM_CAPABILITY','IMPLEMENTATION','INTEGRATION','RUNTIME_BEHAVIOR','QUALIFICATION_VALIDATION'}
    assert r['resolution']=='UNAVAILABLE' and r['execution_authority'] is False

@pytest.mark.parametrize('q',[
    'Inspect your current capability state recorded in your System Layer.',
    'Explain how learning improves memory.',
    'Help me inspect a learning system against this objective and determine its implementation gaps.',
    'Translate "Inspect your current Learning system against this objective" into French.',
])
def test_non_diagnostic_questions_do_not_acquire_scope(q):
    assert objective_evidence_requirements(q) is None

def test_unavailable_scope_does_not_invoke_registry_or_model(monkeypatch):
    import runtime_observation.capability_ledger as registry
    monkeypatch.setattr(registry,'reasoning_context',lambda *a:pytest.fail('Generic registry is insufficient'))
    r=runtime(); before=dict(vars(r))
    p=reasoning_context(r,PROMPT,selector=lambda *a:pytest.fail('No provider call'))
    access=r.context.self_inspection
    assert access['tool_request'] is None and access['provider_calls']==0
    assert access['prerequisite']['status']=='UNAVAILABLE'
    assert access['objective_evidence']['required_classes']
    assert vars(r)==before  # No service/store initialization or Learning mutation.
    gate=assess(PROMPT,p)
    assert not gate['allowed'] and gate['reason']=='OBJECTIVE_EVIDENCE_DOMAINS_UNRESOLVED'
    assert gate['execution_authority'] is False

def test_registry_ledger_cannot_satisfy_objective_via_publication_bypass(tmp_path):
    from tests.test_capability_registry_inspection import routed
    r,q,p=routed(tmp_path)
    assert not assess(PROMPT,p,'invented diagnosis')['allowed']

def test_unavailable_is_published_without_reasoning_or_state_promotion():
    r=runtime(); p=reasoning_context(r,PROMPT)
    result=governed_interaction(r,NS(raw_input=PROMPT,session_id='thread'),p,
                               lambda *a,**k:pytest.fail('No diagnosis without evidence'))
    assert result.response_text==bounded_result(PROMPT)
    assert result.response_text.startswith('UNAVAILABLE:')
    assert 'IMPLEMENTATION' in result.response_text and 'RUNTIME_BEHAVIOR' in result.response_text
    assert not r.context.response_governance['execution_authority_granted']
    assert not hasattr(r,'learning_service') and not hasattr(r,'system_layer')

def test_generic_registry_question_keeps_existing_route(monkeypatch):
    import runtime_observation.capability_ledger as registry
    sentinel=object()
    monkeypatch.setattr(registry,'reasoning_context',lambda *a:sentinel)
    assert reasoning_context(runtime(),'Inspect your current capability state recorded in your System Layer.') is sentinel

def test_ordinary_question_has_no_discovery_route():
    assert reasoning_context(NS(),'What is 2 + 2?') is None

def test_reported_classes_are_obligations_not_admitted_evidence():
    r=runtime(); p=reasoning_context(r,PROMPT)
    assert [s['record']['source'] for s in p.sources]==['SelfInspectionPrerequisite/1']
    assert 'not semantic completeness' in r.context.self_inspection['objective_evidence']['limits']
