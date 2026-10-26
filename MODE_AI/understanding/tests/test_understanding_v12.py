from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace as NS
import json

import pytest

from understanding import *
from understanding.understanding_record import normalize_meaning, primitive, digest
from understanding.semantic_transition import is_transition_allowed
from runtime_observation.observation_record import RuntimeObservationRecord


@pytest.fixture
def engine(tmp_path):
    return UnderstandingEngine(UnderstandingStore(tmp_path / "understanding.sqlite3"))


def authority(domain="OPERATOR", level=AuthorityLevel.AUTHORIZED_OPERATOR, **kwargs):
    return AuthorityContext("operator", level, domain, authenticated=True, **kwargs)


def fact(text="I created this runtime.", obs="obs-1", **kwargs):
    return UnderstandingRequest("operator", "thread", text,
        runtime_observation=RuntimeObservationRecord(obs, operator_id="operator", thread_id="thread", input_text=text),
        authority_context=authority(), **kwargs)


def interpreted(meaning, value, *, domain="OPERATOR", **extra):
    return {"subject_id": "project.term", "subject_type": "TERMINOLOGY", "semantic_domain": domain,
            "meaning": meaning, "claim": {"predicate": "definition", "value": value}, **extra}


def request_for(data, *, auth=None, evidence=True, **kwargs):
    return UnderstandingRequest("operator", "thread", data["meaning"], interpreted_input=data,
        authority_context=auth or authority(), evidence=(Evidence("source:term", "DOCUMENT", True,
            data.get("semantic_domain", "OPERATOR"), normalize_meaning(data["meaning"])),) if evidence else (), **kwargs)


def system_data():
    return {
        "subject_id": "versioned_restore", "subject_type": "OPERATOR_REQUIREMENT", "semantic_domain": "OPERATOR",
        "meaning": "Restore prior valid state under operator authority and validate restored state.",
        "objective": "Restore prior valid state", "system_request": True,
        "source_references": ["document:restore-v1"],
        "requirements": [{"requirement_id": "restore", "text": "Restore prior valid state"}],
        "constraints": ["No destructive overwrite"], "invariants": ["Prior valid state survives"],
        "dependencies": ["Prior state"], "actors": ["Operator"], "components": ["Restorer", "Validator"],
        "authority_requirements": ["Operator authorizes restoration"],
        "evidence_requirements": ["Restored state matches approved prior state"],
        "completion_conditions": ["Restored state validated"], "prohibited_states": ["Unrecoverable replacement"],
        "relationships": [
            {"source": "prior", "target": "restored", "type": "PRESERVES", "failure_condition": "Prior state lost"},
            {"source": "operator", "target": "restored", "type": "AUTHORIZES", "failure_condition": "Unauthorized restoration"},
            {"source": "validation", "target": "restored", "type": "VALIDATES", "failure_condition": "Wrong state restored"},
        ],
        "composition": {"versioned_restore": {"children": ["prior", "operator", "validation", "restored"]},
                        "prior": {"classification": "INVARIANT"}},
    }


def system_request(data=None, mechanisms=()):
    data = data or system_data()
    return UnderstandingRequest("operator", "thread", data["meaning"],
        authoritative_document_context={"source_reference": "document:restore-v1", "interpretation": data},
        authority_context=authority(), evidence=(Evidence("document:restore-v1", "DOCUMENT", True, "OPERATOR",
                                                       normalize_meaning(data["meaning"])),),
        existing_mechanisms=tuple(mechanisms))


def supplied_mechanisms(result):
    return [{"relationship_ids": list(m.required_by_relationship_ids), "validated": True, "operational": True,
             "implementation_reference": "verified-system:" + m.mechanism_id,
             "evidence_references": ["proof:" + m.mechanism_id],
             "preserved_invariants": list(m.invariant_protected),
             "enforced_authorities": list(m.authority_requirement),
             "satisfied_evidence_requirements": list(m.evidence_required),
             "enabled_transitions": [list(m.enabled_transition)]}
            for m in result.mechanism_derivation_result.mechanism_requirements]


def test_01_new_operator_fact(engine):
    result = engine.process(fact())
    assert not result.errors, result.to_dict()
    assert result.state == "CONFIRMED"
    assert result.final_understanding.source_observation_ids == ("obs-1",)
    assert result.final_understanding.custody_holder == "operator"
    assert result.metadata["capability_proven"] is False
    assert result.specification_readiness == SpecificationReadiness.UNPROVEN


def test_02_repeated_fact_is_not_duplicated(engine):
    first = engine.process(fact())
    second = engine.process(fact())
    third = engine.process(fact("I built the runtime.", "obs-2"))
    assert not third.errors, third.to_dict()
    assert second.action == "NO_CHANGE"
    assert third.action == "ADD_EVIDENCE"
    assert first.final_understanding.understanding_id == third.final_understanding.understanding_id
    assert len(engine.store.query("operator")) == 1
    assert len(engine.store.history("operator", first.final_understanding.understanding_id)) == 2


def test_03_contextual_correction_preserves_base(engine):
    first = engine.process(fact("I prefer short technical answers."))
    result = engine.process(fact("For architecture work, give me the complete explanation.", "obs-2"))
    assert not result.errors, result.to_dict()
    assert result.final_understanding.canonical_meaning == first.final_understanding.canonical_meaning
    assert "complete explanation" in result.final_understanding.qualifiers[0]
    assert any(d.drift_type == DriftType.CONTEXT_DRIFT for d in result.drift_records)
    assert len(engine.store.history("operator", first.final_understanding.understanding_id)) == 2


def test_04_contradiction_preserves_confirmed_meaning(engine):
    first = engine.process(request_for(interpreted("Falire exist only on Nova.", "Nova")))
    result = engine.process(request_for(interpreted("Falire exist on Earth.", "Earth")))
    assert result.custody_decision.permitted is False
    assert result.continuity_result.contradiction_detected
    assert result.final_understanding == first.final_understanding
    assert result.specification_readiness == SpecificationReadiness.CONFLICTED


def test_05_unsupported_model_inference_never_confirmed(engine):
    data = interpreted("The operator wants the account permanently deleted.", "delete")
    result = engine.process(request_for(data, auth=AuthorityContext("model", AuthorityLevel.MODEL_INFERENCE, "OPERATOR"), evidence=False))
    assert result.state != "CONFIRMED"
    assert result.review_required
    assert result.custody_decision.confirmation_required
    assert engine.store.query("operator") == []


def test_06_failure_candidate_is_scoped_and_not_learning_execution(engine):
    request = UnderstandingRequest("operator", "thread", "Old account context caused a public knowledge refusal.",
        runtime_metadata={"failure_candidate": True},
        authority_context=AuthorityContext("runtime", AuthorityLevel.VALIDATED_RUNTIME_EVIDENCE, "RUNTIME", True),
        evidence=(Evidence("trace:failure", "RUNTIME_OBSERVATION", False, "RUNTIME"),))
    result = engine.process(request)
    assert not result.errors, result.to_dict()
    assert result.final_understanding.scope == "This observation only; no generalization"
    assert result.final_understanding.semantic_state != SemanticState.CONFIRMED
    assert result.final_understanding.transition_history


def test_07_lower_authority_cannot_replace(engine):
    engine.process(request_for(interpreted("Project term means Alpha.", "Alpha")))
    result = engine.process(request_for(interpreted("Project term means Beta.", "Beta"),
        auth=AuthorityContext("operator", AuthorityLevel.MODEL_INFERENCE, "OPERATOR"), evidence=False))
    assert result.custody_decision.decision == SemanticTransitionDecision.REJECT
    assert result.final_understanding.metadata["claim"]["value"] == "Alpha"


def test_08_governed_rollback_preserves_every_version(engine):
    original = engine.process(fact())
    marked = engine.process(replace(fact(), action="ROLLBACK_REQUIRED",
        authority_context=authority(confirmation_reference="operator:rollback")))
    assert not marked.errors, marked.to_dict()
    assert marked.final_understanding.semantic_state == SemanticState.ROLLBACK_REQUIRED
    restored = engine.process(replace(fact(), action="ROLLBACK", rollback_version=1,
        authority_context=authority(confirmation_reference="operator:rollback")))
    assert not restored.errors, restored.to_dict()
    assert restored.final_understanding.canonical_meaning == original.final_understanding.canonical_meaning
    assert restored.final_understanding.version == 3
    assert len(engine.store.history("operator", original.final_understanding.understanding_id)) == 3


def test_09_requirements_are_not_preferences(engine):
    result = engine.process(fact("MODE must preserve rollback, but I would prefer SQLite for the first version."))
    assert not result.errors, result.to_dict()
    assert result.requirement_state["requirements"][0]["text"] == "preserve rollback"
    assert "SQLite" in result.requirement_state["preferences"][0]["text"]
    assert "SQLite" not in str(result.requirement_state["invariants"])
    assert result.specification_readiness == SpecificationReadiness.STRUCTURALLY_INCOMPLETE


def test_10_relationship_mapping_has_provenance(engine):
    result = engine.process(fact("MODE should learn from failed executions."))
    assert not result.errors, result.to_dict()
    assert len(result.system_relationships) == 12
    assert all(e.governing_requirement_ids and e.source_references for e in result.system_relationships)
    assert any(e.relationship_type == RelationshipType.AUTHORIZES for e in result.system_relationships)


def test_11_chain_recognition_is_structural(engine):
    result = engine.process(fact("MODE should learn from failed executions."))
    types = {c.chain_type for c in result.chain_recognition_result.chain_records}
    assert {ChainType.LEARNING, ChainType.EXECUTION, ChainType.REALITY_EVIDENCE, ChainType.AUTHORITY, ChainType.CONTINUITY} <= types
    assert ChainRecognitionEngine().recognize([], "learning memory authority").chain_records == ()


def test_12_mechanisms_are_justified(engine):
    result = engine.process(fact("MODE should learn from failed executions."))
    mechanisms = result.mechanism_derivation_result.mechanism_requirements
    assert len(mechanisms) == 12
    for m in mechanisms:
        assert m.required_by_requirement_ids and m.required_by_relationship_ids and m.required_by_chain_ids
        assert m.required_stage and m.enabled_transition and m.invariant_protected
        assert m.authority_requirement and m.failure_prevented and m.evidence_required
        assert m.current_implementation_reference is None


def test_13_saving_failure_does_not_complete_learning(engine):
    req = fact("MODE should learn from failed executions.", existing_mechanisms=({"implementation_reference": "save_failure.py", "operational": True},))
    result = engine.process(req)
    assert result.specification_readiness == SpecificationReadiness.STRUCTURALLY_INCOMPLETE
    assert result.structural_gaps
    with pytest.raises(PermissionError): result.specification_handoff()


def test_14_document_to_governed_ready_handoff(engine):
    missing = engine.process(system_request())
    assert not missing.errors, missing.to_dict()
    ready = engine.process(system_request(mechanisms=supplied_mechanisms(missing)))
    assert not ready.errors, ready.to_dict()
    assert ready.specification_readiness == SpecificationReadiness.READY_FOR_SPECIFICATION
    handoff = ready.specification_handoff()
    assert handoff["result"]["requirement_state"]["invariants"] == system_data()["invariants"]
    assert handoff["execution_authority"] is False
    assert handoff["capability_proven"] is False
    assert ready.final_understanding.chain_ids
    assert engine.store.get_bundle("operator", ready.final_understanding.understanding_id)["readiness"] == "READY_FOR_SPECIFICATION"


def test_15_equivalent_structured_requests_repeat(engine):
    a = system_request()
    first = engine.process(a)
    second = engine.process(replace(a, current_input="Please restore the previously accepted version, with authorization and verification."))
    assert not second.errors, second.to_dict()
    assert first.metadata["structural_fingerprint"] == second.metadata["structural_fingerprint"]


def test_16_recursive_decomposition_does_not_invent_irreducibility():
    result = DecompositionEngine().decompose("Continuity", composition={
        "Continuity": {"children": ["Pattern", "Invariants", "Transition", "Reconstruction", "Validation", "Continuation"]},
        "Reconstruction": {"children": ["Persistence"]},
        "Persistence": {"children": ["SQLite"], "classification": "SUBSTITUTABLE"},
        "SQLite": {"classification": "IMPLEMENTATION_SPECIFIC"}})
    assert result.decomposition_depth == 3
    assert "SQLite" in result.implementation_specific_elements
    assert result.irreducibility_status != IrreducibilityStatus.PROVISIONALLY_IRREDUCIBLE
    assert result.stopping_reason and result.unresolved_questions


def test_17_candidate_principles_require_independent_scoped_evidence(engine):
    data = system_data()
    result = engine.process(system_request(data))
    samples = [{"validated": True, "observation_id": "obs:" + s, "system_id": s,
                "evidence_reference": "proof:" + s, "invariant": data["invariants"][0],
                "scope": "Versioned restoration", "boundary_conditions": ["Prior state validated"],
                "falsification_conditions": ["A validated restore loses prior state"],
                "counterexample_search_completed": True} for s in ("a", "b")]
    principles = GoverningEngine().evaluate(result.decomposition_result, result.chain_recognition_result,
                                            result.system_relationships, samples)
    assert len(principles.candidate_principles) == 1
    assert principles.candidate_principles[0].validation_state == "PROVISIONAL"
    assert principles.candidate_principles[0].authority_status == "UNPROMOTED"
    assert not GoverningEngine().evaluate(result.decomposition_result, result.chain_recognition_result,
                                         result.system_relationships, [samples[0], samples[0]]).candidate_principles
    samples[1]["counterexample"] = True
    assert GoverningEngine().evaluate(result.decomposition_result, result.chain_recognition_result,
                                     result.system_relationships, samples).rejected_candidates


def test_18_mechanism_and_structure_remain_distinct(engine):
    result = engine.process(system_request())
    mechanism = next(m for m in result.mechanism_derivation_result.mechanism_requirements if m.mechanism_type == "PRIOR_STATE_PRESERVATION")
    assert mechanism.required_by_chain_ids != (mechanism.mechanism_id,)
    assert "sqlite" not in mechanism.description.lower()
    decomposed = DecompositionEngine().decompose(mechanism.mechanism_id, target_type="MECHANISM",
        composition={mechanism.mechanism_id: {"children": ["carrier"]}, "carrier": {"classification": "SUBSTITUTABLE"}})
    assert decomposed.target_type == "MECHANISM"
    assert "carrier" in decomposed.substitution_candidates


def test_analysis_failure_writes_no_partial_version(engine):
    initial = engine.process(fact())
    class Broken:
        def recognize(self, *args): raise RuntimeError("recognition failed")
    engine.recognition = Broken()
    result = engine.process(fact(obs="obs-2"))
    assert result.errors and result.retry_information["observation_id"] == "obs-2"
    assert engine.store.get("operator", initial.final_understanding.understanding_id).version == 1
    assert result.final_understanding == initial.final_understanding


def test_atomic_stale_updates_and_isolation(engine):
    initial = engine.process(fact())
    barrier = Barrier(2)
    base = engine.store.commit
    def racing(*args):
        barrier.wait(timeout=5)
        return base(*args)
    engine.store.commit = racing
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda obs: engine.process(fact(obs=obs)), ["obs-2", "obs-3"]))
    assert sum(not r.errors for r in results) == 1
    assert any(r.errors and r.errors[0]["type"] == "StaleUnderstandingError" for r in results)
    assert engine.store.get("other", initial.final_understanding.understanding_id) is None
    assert engine.store.find_by_subject("operator", "other-thread", "", "operator.runtime_creator", "OPERATOR") is None


def test_corruption_fails_closed(engine):
    result = engine.process(fact())
    with engine.store.connection() as conn:
        conn.execute("UPDATE versions SET payload='{}'")
    with pytest.raises(UnderstandingStorageError):
        engine.store.get("operator", result.final_understanding.understanding_id)


def test_forged_or_mutated_custody_cannot_write(engine):
    result = engine.process(fact())
    changed = replace(result.candidate_understanding, canonical_meaning="Fabricated", normalized_meaning="fabricated")
    with pytest.raises(ValueError):
        engine.updater.apply(None, changed, result.custody_decision, result.transition, {})
    forged = replace(result.custody_decision, expected_version=99)
    with pytest.raises(ValueError):
        forged.verify(result.candidate_understanding, result.transition)


def test_unknown_transition_and_authority_fail_closed():
    assert not is_transition_allowed(SemanticState.UNOBSERVED, SemanticState.CONFIRMED)
    with pytest.raises(ValueError): AuthorityContext("x", "SYSTEM_LAW", "SYSTEM", True)


def test_runtime_observation_integration(engine, tmp_path):
    from interactive_mode_ai import ModeRuntime
    from runtime_observation.observation_store import RuntimeObservationStore
    runtime = ModeRuntime.__new__(ModeRuntime)
    runtime.understanding_engine = engine
    store = RuntimeObservationStore(tmp_path / "observations")
    runtime.runtime_observation_collector = NS(store=store)
    observation = fact().runtime_observation
    store.save_record(observation)
    result = runtime._understand_observation(observation)
    assert not result.errors, result.to_dict()
    loaded = store.load_record("operator", "obs-1")
    assert loaded.metadata["understanding"]["understanding_id"] == result.final_understanding.understanding_id
    assert result.final_understanding.source_observation_ids == ("obs-1",)


def test_declared_memory_validation_is_not_semantic_truth(engine):
    data = interpreted("The operator wants deletion.", "delete")
    request = replace(request_for(data), evidence=(Evidence("memory:retained", "PERSISTENT_MEMORY", True,
                                                           "OPERATOR", normalize_meaning(data["meaning"])),))
    result = engine.process(request)
    assert result.final_understanding.semantic_state != SemanticState.CONFIRMED
    assert result.review_required


def test_pending_meaning_can_be_confirmed_by_qualifying_evidence(engine):
    data = interpreted("The operator prefers CSV.", "CSV")
    pending = engine.process(request_for(data, evidence=False))
    assert pending.state == "PENDING_VALIDATION"
    confirmed = engine.process(request_for(data))
    assert not confirmed.errors, confirmed.to_dict()
    assert confirmed.state == "CONFIRMED" and confirmed.action == "CONFIRM"


def test_operator_cannot_define_external_truth(engine):
    result = engine.process(request_for(interpreted("External standard permits X.", "X", domain="EXTERNAL")))
    assert result.custody_decision.permitted is False
    assert engine.store.query("operator") == []


def test_rejected_conflict_is_audited_without_replacement(engine):
    original = engine.process(request_for(interpreted("Term means Alpha.", "Alpha")))
    result = engine.process(request_for(interpreted("Term means Beta.", "Beta")))
    audits = engine.store.audit_history("operator", original.final_understanding.understanding_id)
    review = json.loads(audits[-1]["detail"])
    assert audits[-1]["operation"] == "REVIEW"
    assert review["candidate"]["canonical_meaning"] == "Term means Beta."
    assert review["continuity"]["contradiction_detected"]
    assert engine.store.get("operator", original.final_understanding.understanding_id).version == 1


def test_protected_meaning_cannot_expand_scope_silently(engine):
    original = interpreted("Term means Alpha.", "Alpha", protected_meaning=True, scope="project A")
    engine.process(request_for(original))
    result = engine.process(request_for({**original, "scope": "all projects"}))
    assert result.custody_decision.permitted is False
    assert result.final_understanding.scope == "project A"


def test_archive_preserves_history_and_delete_requires_explicit_authority(engine):
    first = engine.process(fact())
    archived = engine.process(replace(fact(), action="ARCHIVE", authority_context=authority(confirmation_reference="archive:approved")))
    assert not archived.errors, archived.to_dict()
    assert archived.state == "ARCHIVED"
    assert engine.store.query("operator", active=True) == []
    assert len(engine.store.history("operator", first.final_understanding.understanding_id)) == 2
    with pytest.raises(PermissionError):
        engine.store.delete_permanently("operator", first.final_understanding.understanding_id, authority(), "test")


def test_invalid_supersession_is_not_persisted(engine):
    first = engine.process(fact())
    data = {"subject_id": "operator.runtime_creator", "meaning": first.final_understanding.canonical_meaning,
            "superseded_by_id": "missing-record"}
    result = engine.process(request_for(data, action="SUPERSEDE", auth=authority(confirmation_reference="approved")))
    assert result.errors and engine.store.get("operator", first.final_understanding.understanding_id).version == 1


@pytest.mark.parametrize("component,method", [
    ("continuity", "validate"), ("custody", "evaluate"), ("mapper", "map"),
    ("decomposition", "decompose"), ("governing", "evaluate"), ("mechanisms", "derive"),
    ("updater", "prepare"), ("store", "commit"),
])
def test_every_component_failure_leaves_prior_record_intact(engine, monkeypatch, component, method):
    first = engine.process(fact())
    def fail(*args, **kwargs): raise RuntimeError("injected failure")
    monkeypatch.setattr(getattr(engine, component), method, fail)
    result = engine.process(fact(obs="obs-2"))
    assert result.errors and result.specification_readiness == SpecificationReadiness.UNPROVEN
    assert engine.store.get("operator", first.final_understanding.understanding_id).version == 1


def test_unmapped_document_requirement_cannot_be_handed_off(engine):
    data = system_data()
    data["requirements"].append({"requirement_id": "undeveloped", "text": "Preserve auditability"})
    for relationship in data["relationships"]: relationship["requirement_ids"] = ["restore"]
    result = engine.process(system_request(data))
    assert any(g.gap_type == "UNMAPPED_REQUIREMENT" for g in result.structural_gaps)
    with pytest.raises(PermissionError): result.specification_handoff()


def test_readiness_cannot_be_changed_without_custody(engine):
    result = engine.process(system_request())
    result.specification_readiness = SpecificationReadiness.READY_FOR_SPECIFICATION
    result.structural_gaps = ()
    with pytest.raises(PermissionError): result.specification_handoff()


def test_unknown_document_fields_fail_closed(engine):
    data = system_data()
    data["required_unsupported_authority"] = "must not disappear"
    result = engine.process(system_request(data))
    assert result.errors and engine.store.query("operator") == []


def test_missing_authority_is_explicit_structural_gap(engine):
    data = system_data()
    data["authority_requirements"] = []
    result = engine.process(system_request(data))
    assert any("authority" in g.description for g in result.structural_gaps)
    assert result.specification_readiness == SpecificationReadiness.STRUCTURALLY_INCOMPLETE


def test_decomposition_cycle_and_scoped_removal_evidence():
    cyclic = DecompositionEngine().decompose("a", composition={"a": {"children": ["b"]}, "b": {"children": ["a"]}})
    assert cyclic.irreducibility_status == IrreducibilityStatus.CONFLICTED
    tested = DecompositionEngine().decompose("relation", composition={"relation": {
        "classification": "ESSENTIAL", "removal_invalidates_relationship": True,
        "validated_evidence": ["experiment:scoped-removal"]}})
    assert tested.irreducibility_status == IrreducibilityStatus.PROVISIONALLY_IRREDUCIBLE
    assert tested.essential_elements == ("relation",)


def test_chain_mapper_reports_cycles_and_missing_precedence_authority():
    edges = [SystemRelationship.create("operator", "", "system", a, b, RelationshipType.DEPENDS_ON,
             ["req"], ["doc"], authority_requirements=("policy",)) for a, b in (("a", "b"), ("b", "a"))]
    def chain(name):
        return SystemChain(name, ChainType.EXECUTION, ChainRole.PRIMARY, name, name, name, (name,), (), (), (), (), (), (), name)
    recognition = ChainRecognitionResult(chain_records=(chain("a"), chain("b")))
    mapping = ChainRelationshipMapper().map(recognition, edges)
    assert mapping.circular_dependencies == ("a", "b")
    assert mapping.unresolved_conflicts
    no_authority = ChainRelationshipMapper().map(recognition, [replace(edges[0], authority_requirements=())])
    assert not no_authority.precedence_rules and no_authority.unresolved_conflicts


def test_full_record_serialization_round_trip(engine):
    result = engine.process(system_request())
    record = result.final_understanding
    restored = UnderstandingRecord.from_dict(json.loads(json.dumps(primitive(record))))
    assert record == restored


def test_materially_equivalent_prose_has_same_structure(engine):
    first = engine.process(fact("MODE should learn from failed executions."))
    second = engine.process(fact("MODE should improve based on failed executions.", "obs-2"))
    assert not second.errors, second.to_dict()
    assert first.metadata["structural_fingerprint"] == second.metadata["structural_fingerprint"]
    assert "obs-2" in second.final_understanding.source_observation_ids


def test_irrelevant_greeting_does_not_create_understanding(engine):
    result = engine.process(fact("Hello!"))
    assert result.state == "NO_RELEVANT_UNDERSTANDING"
    assert engine.store.query("operator") == []


def test_protected_flag_cannot_be_cleared_through_explicit_action(engine):
    original = interpreted("Term means Alpha.", "Alpha", protected_meaning=True)
    first = engine.process(request_for(original))
    result = engine.process(request_for({**original, "protected_meaning": False}, action="REFINE"))
    assert not result.custody_decision.permitted
    assert engine.store.get("operator", first.final_understanding.understanding_id).protected_meaning


def test_complete_review_examples_have_all_pipeline_outputs():
    from understanding.tests.examples import examples
    sample = examples()
    ready = sample["ready_for_specification"]
    assert all(ready[key] is not None for key in (
        "requirement_state", "system_relationships", "chain_recognition_result", "chain_relationship_map",
        "decomposition_result", "governing_principle_result", "mechanism_derivation_result", "structural_gaps",
        "continuity_result", "custody_decision", "transition", "update_result", "final_understanding"))
    assert sample["specification_handoff"]["execution_authority"] is False
    assert "prior" in sample["ready_explanation"]


def test_runtime_system_explanation_without_reasoning_model(engine, tmp_path, monkeypatch):
    from interactive_mode_ai import ModeRuntime
    from runtime_observation.observation_store import RuntimeObservationStore
    from agents.reasoning_agent import ReasoningAgent
    monkeypatch.setattr(ReasoningAgent, "generate", lambda *a, **kw: pytest.fail("Understanding must not call a model in deterministic tests"))
    runtime = ModeRuntime.__new__(ModeRuntime)
    runtime.understanding_engine = engine
    runtime.runtime_observation_collector = NS(store=RuntimeObservationStore(tmp_path / "observations"))
    observation = fact("MODE should learn from failed executions.").runtime_observation
    runtime.runtime_observation_collector.store.save_record(observation)
    result = runtime._understand_observation(observation)
    assert not result.errors, result.to_dict()
    assert result.specification_readiness == SpecificationReadiness.STRUCTURALLY_INCOMPLETE
    explanation = result.explain()
    for section in ("requirements", "preferences", "constraints", "invariants", "dependencies", "actors", "components",
                    "Relationship:", "Chain:", "Chain handoffs:", "Decomposition:", "Stopping reason:", "Mechanism:", "Blocking gap:"):
        assert section in explanation
