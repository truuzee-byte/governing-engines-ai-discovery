from types import SimpleNamespace as NS

import pytest

from context_assembly.context_assembler import ContextAssembler
from mode_operator.operator_requirement_engine import OperatorRequirementEngine
from mode_operator.operator_requirement_models import OperatorRequirementDomain as RequirementDomain
from persistent_memory.persistent_memory_manager import PersistentMemoryManager
from persistent_memory.persistent_memory_record import (
    PersistentMemoryDomain as Domain, PersistentMemoryStatus as Status,
    PersistentMemoryConsentStatus as Consent,
)
from persistent_memory.persistent_memory_store import PersistentMemoryStore


def setup_context(tmp_path):
    manager = PersistentMemoryManager(PersistentMemoryStore(tmp_path))
    profile = NS(operator_id="operator", operator_managed=NS())
    plan = NS(included_sources=lambda: [], missing_sources=lambda: [],
              context_ready=lambda: True, source_selections=[])
    return manager, profile, plan


def save(manager, content, **kwargs):
    proposal = manager.propose_create_memory(
        operator_id="operator", content=content, source_thread_id="thread",
        source_message_id="message", original_operator_statement=content, **kwargs)
    return manager.confirm_candidate(proposal.candidate, "yes").record


def assemble(profile, plan, records, session=None):
    return ContextAssembler().assemble(profile, NS(messages=[],thread_id='thread',operator_id=profile.operator_id), None, "LISTENING", plan,
                                       persistent_memories=records, session_answers=session)


def test_retrieval_to_assembled_prompt(tmp_path):
    manager, profile, plan = setup_context(tmp_path)
    save(manager, "Reports should use CSV.")
    save(manager, "My favorite food is pasta.")
    save(manager, "Reports for health.", domain=Domain.HEALTH)
    records = manager.retrieve_memories("operator", query="What format for reports?", domain=Domain.GENERAL)
    prompt = assemble(profile, plan, records).to_prompt_context()
    assert "Reports should use CSV." in prompt
    assert "pasta" not in prompt
    assert "Reports for health" not in prompt


@pytest.mark.parametrize("field,value", [
    ("status", Status.DEPRECATED), ("status", Status.UNDER_REVIEW),
    ("consent_status", Consent.REQUESTED),
    ("expiration_policy", "2000-01-01T00:00:00+00:00"),
    ("expiration_policy", "unknown expiry"),
])
def test_ineligible_memories_excluded_at_retrieval_and_assembly(tmp_path, field, value):
    manager, profile, plan = setup_context(tmp_path)
    record = save(manager, "Excluded fact")
    setattr(record, field, value)
    # v2.0: a caller cannot silently mutate a governed version. Assembly must
    # also reject the altered in-memory object rather than trust its old grant.
    with pytest.raises(PermissionError):manager.store.save_record(record)
    manager.lifecycle('operator',record.memory_id,'ARCHIVE','yes')
    assert manager.retrieve_memories("operator", include_inactive=True) == []
    assert "Excluded fact" not in assemble(profile, plan, [record]).to_prompt_context()


def test_session_answers_satisfy_requirements_without_storage(tmp_path):
    manager, profile, plan = setup_context(tmp_path)
    answers = {"age": "35", "height": "180 cm", "weight": "75 kg", "activity_level": "active"}
    result = OperatorRequirementEngine(manager).evaluate(
        operator_profile=profile, thread_id="thread", input_text="Health guidance",
        domain=RequirementDomain.HEALTH, session_answers=answers)
    assert result.can_continue()
    assert all(r.storage_choice.value == "SESSION_ONLY" for r in result.requirements if r.required)
    assert not list(tmp_path.rglob("*.json"))
    assert "age: 35" in assemble(profile, plan, [], answers).to_prompt_context()


@pytest.mark.parametrize('text', ['Remember my health question', 'Use persistent memory for health guidance'])
def test_memory_words_do_not_remove_domain_requirements(tmp_path,text):
    manager,profile,_=setup_context(tmp_path)
    result=OperatorRequirementEngine(manager).evaluate(operator_profile=profile,thread_id='thread',
        input_text=text,domain=RequirementDomain.HEALTH,persistent_memories=[])
    assert result.domain==RequirementDomain.HEALTH
    assert not result.can_continue()
    assert {r.field_name for r in result.requirements if r.required}=={'age','height','weight','activity_level'}


def test_unknown_requirement_domain_does_not_default_to_no_requirements(tmp_path):
    manager,profile,_=setup_context(tmp_path)
    with pytest.raises(ValueError):
        OperatorRequirementEngine(manager).evaluate(operator_profile=profile,thread_id='thread',
            input_text='Guidance',domain='UNKNOWN',persistent_memories=[])


def test_requirement_satisfaction_preserves_source_without_copying_facts(tmp_path):
    from system_layer.contracts import digest
    manager,profile,_=setup_context(tmp_path)
    profile.operator_managed.height='Profile height fact'
    memory=save(manager,'Approved weight fact',domain=Domain.HEALTH,data_category='weight')
    result=OperatorRequirementEngine(manager).evaluate(operator_profile=profile,thread_id='thread',input_text='Health',
        domain=RequirementDomain.HEALTH,session_answers={'age':'Session age fact'},persistent_memories=[memory])
    sources={r.field_name:r.metadata['satisfaction_source'] for r in result.requirements}
    assert sources['age']==dict(source='ACTIVE_SESSION',field_name='age',thread_id='thread',value_hash=digest('Session age fact'))
    assert sources['height']['source']=='OPERATOR_PROFILE' and sources['height']['value_hash']==digest('Profile height fact')
    assert sources['weight']['memory_id']==memory.memory_id and sources['weight']['version']==memory.version
    assert sources['weight']['governance_decision_id']==memory.governance_decision['decision_id']
    assert sources['activity_level'] is None and not result.can_continue()
    assert all(fact not in str(sources) for fact in ('Session age fact','Profile height fact','Approved weight fact'))


def test_dedup_and_empty_context(tmp_path):
    manager, profile, plan = setup_context(tmp_path)
    record = save(manager, "CSV reports")
    prompt = assemble(profile, plan, [record, record], {"format": "CSV reports"}).to_prompt_context()
    assert prompt.count("CSV reports") == 1
    assert "PERSISTENT MEMORY (" not in prompt
    empty = assemble(profile, plan, []).to_prompt_context()
    assert "PERSISTENT MEMORY (" not in empty
    assert "ACTIVE SESSION ANSWERS:" not in empty


def test_excluded_thread_artifact_cannot_suppress_approved_memory_or_session_fact(tmp_path):
    from memory.thread_memory import ThreadMemory
    from context_orchestration.context_source import ContextSource
    manager,profile,plan=setup_context(tmp_path)
    record=save(manager,'Approved selected fact')
    thread=ThreadMemory.create(profile.operator_id)
    thread.add_message('assistant',record.content,{'memory_id':'unadmitted-copy'})
    thread.add_message('assistant','Session fact',{'artifact_id':'unadmitted-copy'})
    plan.included_sources=lambda:[ContextSource.THREAD_MEMORY]
    context=ContextAssembler().assemble(profile,thread,None,'LISTENING',plan,
        persistent_memories=[record],session_answers={'fact':'Session fact'})
    assert context.thread.recent_messages==[]
    prompt=context.to_prompt_context()
    assert prompt.count(record.content)==1 and prompt.count('Session fact')==1
    assert context.persistent_memory_contents==[record.content]
    assert context.session_answers=={'fact':'Session fact'}


@pytest.mark.parametrize('invalid_first',[False,True])
def test_invalid_duplicate_does_not_suppress_independently_admitted_memory(tmp_path,invalid_first):
    from copy import deepcopy
    manager,profile,plan=setup_context(tmp_path)
    valid=save(manager,'Independently approved fact');invalid=deepcopy(valid)
    invalid.status=Status.DEPRECATED
    records=[invalid,valid] if invalid_first else [valid,invalid]
    context=assemble(profile,plan,records)
    assert context.persistent_memory_contents==[valid.content]
    prompt=context.to_prompt_context()
    assert str(prompt).count(valid.content)==1
    memory_decisions=[d for d in prompt.decisions if d['artifact_type']=='MEMORY']
    assert [d['decision'] for d in memory_decisions].count('ADMITTED')==1
    assert [d['decision'] for d in memory_decisions].count('EXCLUDED')==1


def test_runtime_prompt_uses_single_retrieval(tmp_path, monkeypatch):
    from interactive_mode_ai import ModeRuntime, RuntimeState
    from knowledge.knowledge_domain import KnowledgeDomain
    manager, profile, plan = setup_context(tmp_path)
    save(manager, "Reports use CSV.")
    runtime = ModeRuntime.__new__(ModeRuntime)
    runtime.context = NS(profile=profile, identity=NS(operator_id="operator"),
                         active_thread=NS(thread_id="thread", operator_id='operator',messages=[]),
                         temporal_context=None, runtime_state=RuntimeState.LISTENING)
    runtime.pending_action = None
    runtime.knowledge_classifier = NS(classify=lambda _: NS(primary_domain=KnowledgeDomain.PUBLIC))
    runtime.knowledge_router = NS(route=lambda _: None)
    runtime._resolve_operator_requirement_domain = lambda **_: RequirementDomain.GENERAL
    runtime._available_context_sources = lambda: []
    runtime.context_orchestrator = NS(build_plan=lambda **_: plan)
    runtime.context_assembler = ContextAssembler()
    runtime.operator_requirement_engine = OperatorRequirementEngine(manager)
    runtime.persistent_memory_manager = manager
    for name in ("_build_knowledge_context", "_build_operator_requirement_context", "_build_orchestration_context"):
        setattr(runtime, name, lambda: "")
    calls = []
    original = manager.retrieve_memories
    def retrieve(**kwargs):
        calls.append(kwargs)
        return original(**kwargs)
    monkeypatch.setattr(manager, "retrieve_memories", retrieve)
    prompt = runtime._build_engine_input("What format for reports?")
    assert prompt.count("Reports use CSV.") == 1
    assert len(calls) == 1
    assert calls[0]["query"] == "What format for reports?"
    from learning.contracts import digest
    assert runtime.context.context_admission['prompt_hash']==digest(str(prompt))
    assert runtime.context.context_admission['decisions']==prompt.decisions
    assert any(d['artifact_type']=='MEMORY' and d['decision']=='ADMITTED' for d in prompt.decisions)
