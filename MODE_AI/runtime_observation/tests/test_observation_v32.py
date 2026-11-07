"""Observation v3.2 section 31 acceptance scenarios. All evidence is synthetic.
No test fixture establishes operational capability or Reality confirmation.
"""
from copy import deepcopy
from dataclasses import fields
import json
from pathlib import Path
import pytest
from runtime_observation import RuntimeObservationCollector, RuntimeObservationRecord, RuntimeObservationType
from runtime_observation.observation_record import EVIDENCE_GROUPS
from runtime_observation.observation_builder import RuntimeObservationBuilder, LIST_FIELDS, MEASUREMENTS
from runtime_observation.observation_store import RuntimeObservationStore, ObservationRetrievalError

@pytest.fixture
def collector(tmp_path):
    return RuntimeObservationCollector(store=RuntimeObservationStore(tmp_path / "observations"))

def collect(collector, **evidence):
    return collector.collect(operator_id="operator", thread_id="thread", input_text="I created this runtime.",
        response_text="Recorded statement", runtime_state_start="A", runtime_state_end=evidence.pop("end", "B"),
        context_ready=True, knowledge_domain="OPERATOR", trace_reference="trace:test",
        metadata={"runtime_component": "test.producer", "required_evidence_fields": ["pre_execution_state", "post_execution_state"],
            "pre_execution_state": "A", "post_execution_state": "B", **evidence})

def event(kind, **values):
    return {"observation_type": kind, "source_component": "test.producer", "timestamp": "2026-09-11T00:00:00+00:00",
            "evidence_reference": "evidence:test", "fields": values}

def kinds(record): return {x.value for x in record.observation_types}

def test_01_current_custody_preservation(collector):
    evidence = dict(requested_domain="PRIVATE_DOCUMENT", routed_domain="PRIVATE_DOCUMENT", requested_context_sources=["doc"],
        loaded_context_sources=["doc"], executed_components=["retriever"], execution_time=0,
        retrieval_trace="trace:retrieval", recovery_attempted=True, recovery_action="retry", recovery_status="FAILED",
        custody_type="CONTEXT", drift_type="reported", runtime_component="retriever", affected_runtime_stage="lookup",
        evidence_reference="proof:1", operator_correction_reference="message:2")
    record = collect(collector, **evidence)
    restored = collector.store.load_record("operator", record.observation_id)
    for key, value in evidence.items(): assert getattr(restored, key) == value
    assert restored.retry_count is None
    assert restored.execution_time == 0

def test_02_structural_state(collector):
    r = collect(collector, state_source_references=["state:A", "state:B"])
    assert (r.pre_execution_state, r.post_execution_state) == ("A", "B")
    assert r.state_source_references == ["state:A", "state:B"]
    assert r.evidence_completeness == "COMPLETE"

def test_03_transition_failure(collector):
    r = collect(collector, attempted_transitions=["A->B"], rejected_transitions=["A->B"], actual_result_state="A",
                transition_receipts=["validator:reject"], end="FAILED")
    assert {"TRANSITION_ATTEMPT", "TRANSITION_REJECTED", "EXECUTION_FAILURE"} <= kinds(r)
    assert "NORMAL_EXECUTION" not in kinds(r)
    assert r.actual_result_state == "A"

def test_04_dependency_failure(collector):
    r = collect(collector, requested_dependencies=["B"], missing_dependencies=["B"], directly_observed_effects=["A blocked"])
    assert "DEPENDENCY_MISSING" in kinds(r)
    assert not r.declared_dependencies

def test_05_invariant_violation(collector):
    r = collect(collector, invariant_checks_performed=["operator_authority_preserved"],
                violated_invariants=["operator_authority_preserved"], invariant_evidence_references=["validator:1"])
    assert "INVARIANT_VIOLATED" in kinds(r)
    assert r.invariant_evidence_references == ["validator:1"]

def test_06_authority_denial(collector):
    r = collect(collector, acting_identity="operator", authority_source="gate", authority_scope="write", authority_request="modify",
                authority_decision="DENY", authorization_receipts=["deny:1"], execution_path=["blocked"])
    assert "AUTHORITY_DENY" in kinds(r)
    assert r.execution_path == ["blocked"]

def test_07_claim_vs_reality(collector):
    r = collect(collector, completion_claim=True, validation_results=[{"state": "DISCONFIRMED", "source": "validator", "artifact_missing": True}])
    assert r.completion_claim is True
    assert r.validation_results[0]["artifact_missing"] is True
    assert "COMPLETION_PROVEN" not in kinds(r)

def test_08_direct_consequence(collector):
    r = collect(collector, completed_transitions=["A->B"], triggered_components=["B"], emitted_events=["C"], source_traces=["trace:ABC"])
    assert r.triggered_components == ["B"] and r.emitted_events == ["C"]
    assert "cause" not in r.to_dict()

def test_09_repeated_pattern_support(collector):
    a=collect(collector, failed_transitions=["A->B"]); b=collect(collector, failed_transitions=["A->B"])
    found=collector.store.query_records("operator", failed_transitions="A->B")
    assert {r.observation_id for r in found} == {a.observation_id,b.observation_id}

def test_10_missing_structural_evidence(collector):
    r=collect(collector, required_evidence_fields=["dependency_results"])
    assert r.evidence_completeness == "STRUCTURALLY_PARTIAL"
    assert "dependency_results" in r.missing_fields
    assert r.field_availability["dependency_results"] == "UNAVAILABLE"
    assert not r.dependency_results

def test_11_understanding_consumption(collector, tmp_path):
    from understanding import UnderstandingEngine, UnderstandingRequest, UnderstandingStore, AuthorityContext, AuthorityLevel
    r=collect(collector, acting_identity="operator", attempted_transitions=["A->B"], declared_dependencies=["state"],
              declared_constraints=["scope"], declared_invariants=["identity"], authority_decision="ALLOW", observed_outcome="B")
    original=r.to_dict()
    engine=UnderstandingEngine(UnderstandingStore(tmp_path / "understanding.sqlite3"))
    result=engine.process(UnderstandingRequest("operator","thread",r.input_text,runtime_observation=r,
        authority_context=AuthorityContext("operator",AuthorityLevel.DIRECT_OPERATOR_STATEMENT,"OPERATOR",authenticated=True),
        relevant_context={"observation_evidence":r.to_dict()}))
    assert not result.errors
    assert result.observation_id == r.observation_id
    assert result.final_understanding.source_observation_ids == (r.observation_id,)
    assert r.to_dict() == original
    assert not any("CHAIN" in k for k in kinds(r))

def test_12_governing_retrieval(collector):
    for i in range(3): collect(collector, mechanism_ids=["retriever"], correlation_id=str(i))
    found=collector.store.query_records("operator",mechanism_ids="retriever")
    assert len(found)==3
    assert all("governing_principle" not in r.to_dict() for r in found)

def test_13_composition(collector):
    r=collect(collector, structural_elements=["A","B","C"], parent_child_relationships=[{"parent":"A","child":"B"},{"parent":"B","child":"C"}],
              containment_relationships=["A contains B"], declared_system_boundaries=["boundary:A"])
    assert r.parent_child_relationships[1] == {"parent":"B","child":"C"}
    assert "essential" not in r.to_dict()

def test_14_mechanism_substitution(collector):
    r=collect(collector, mechanism_ids=["A","B"], substituted_elements=[{"original":"A","substitute":"B"}],
        variation_pre_state="A", variation_post_state="B", observed_variation_effects=["transition completed"], variation_receipts=["test:substitution"])
    assert r.substituted_elements[0]["substitute"]=="B"
    assert "equivalent" not in r.to_dict()

def test_15_decomposition_support(collector):
    from understanding.decomposition_engine import DecompositionEngine
    r=collect(collector, structural_elements=["A","B"], parent_child_relationships=[{"parent":"A","child":"B"}], removed_elements=["B"],
        variation_pre_state="A+B", variation_post_state="A", observed_variation_effects=["execution continued"], validation_results=[{"state":"PASSED","source":"test.validator"}])
    # Mechanical presentation of recorded parent/child edges, no essentiality claim.
    composition={n:{"children":[]} for n in r.structural_elements}
    for link in r.parent_child_relationships: composition[link["parent"]]["children"].append(link["child"])
    result=DecompositionEngine().decompose("A",composition=composition)
    assert ("A","B") in result.parent_child_relationships
    assert not result.essential_elements
    assert r.removed_elements==["B"]

def test_16_productivity_baseline(collector):
    r=collect(collector, objective_id="A",attempt_id="1",interaction_turn_count=8,clarification_count=3,correction_count=2,
        retry_count=1,rebuild_count=1,operator_intervention_count=2,objective_validation_reference="validator:1",objective_completion_evidence=["validator:1"],
        measurement_interval={"started_at":"2026-09-11T00:00:00+00:00","completed_at":"2026-09-11T00:01:00+00:00","source_reference":"clock:1"})
    assert r.elapsed_time==60 and r.retry_count==1 and r.interaction_turn_count==8

def test_17_productivity_comparison(collector):
    a=collect(collector,objective_id="A",attempt_id="1",correction_count=3,operator_intervention_count=2)
    b=collect(collector,objective_id="A",attempt_id="2",correction_count=0,operator_intervention_count=0,comparable_attempt_reference=a.observation_id)
    found=collector.store.query_records("operator",objective_id="A")
    assert len(found)==2 and b.correction_count-a.correction_count==-3
    assert b.comparable_attempt_reference==a.observation_id

def test_18_false_productivity(collector):
    a=collect(collector,objective_id="A",attempt_id="1",interaction_turn_count=3,completion_claim=True,validation_results=[{"state":"DISCONFIRMED"}])
    b=collect(collector,objective_id="A",attempt_id="2",interaction_turn_count=7,completion_claim=True,validation_results=[{"state":"CONFIRMED"}])
    assert "COMPLETION_PROVEN" not in kinds(a)
    assert a.validation_results != b.validation_results
    assert "productivity_judgment" not in a.to_dict()

def test_19_rework(collector):
    r=collect(collector,output_artifacts=["old","new"],operator_correction_reference="message:2",superseded_output_count=1,rebuild_count=1)
    assert {"OPERATOR_CORRECTION","OUTPUT_SUPERSEDED","REBUILD_REQUIRED"} <= kinds(r)

def test_20_prior_understanding_reuse(collector):
    r=collect(collector,prior_understanding_references_used=["understanding:1"],operation_count=2,comparable_attempt_reference="attempt:old")
    assert r.prior_understanding_references_used==["understanding:1"]
    assert "UNDERSTANDING_IMPROVED" not in kinds(r)

def test_21_productivity_partial(collector):
    r=collect(collector,objective_id="A",elapsed_time=5,interaction_turn_count=2,correction_count=0)
    assert r.evidence_completeness=="PRODUCTIVITY_PARTIAL"
    assert r.productivity_evidence_status=="PARTIAL"
    assert r.correction_count==0 and r.retry_count is None

def test_all_expanded_fields_survive_package_store_roundtrip(collector):
    package={}
    for group,names in EVIDENCE_GROUPS.items():
        package[group]={n: ([{"source":"test","value":n}] if n in LIST_FIELDS else 0 if n in MEASUREMENTS else "explicit:"+n) for n in names}
    r=collector.collect(operator_id="operator",thread_id="thread",trace_reference="trace:test",
        metadata={"runtime_component":"test", "evidence_package":package})
    restored=collector.store.load_record("operator",r.observation_id)
    for group,values in package.items():
        for name,value in values.items(): assert getattr(restored,name)==value, name

def test_conflicting_sources_preserved(collector):
    r=collect(collector,evidence_events=[event("COMPLETION_CLAIM",observed_outcome="claimed"),event("EVIDENCE_REJECTED",observed_outcome="missing")])
    assert r.evidence_completeness=="EVIDENCE_CONFLICT"
    assert {e["value"] for e in r.field_sources["observed_outcome"]}=={"claimed","missing"}

def test_collection_failure_preserves_partial(collector):
    class Broken:
        def build(self,**kwargs): raise RuntimeError("assembly unavailable")
    collector.builder=Broken()
    r=collect(collector,declared_dependencies=["raw evidence"])
    assert r.collection_errors and r.evidence_completeness=="PARTIAL"
    assert r.metadata["declared_dependencies"]==["raw evidence"]
    assert "NORMAL_EXECUTION" not in kinds(r)
    assert collector.store.load_record("operator",r.observation_id)

def test_unreadable_evidence_is_explicit(collector):
    r=collect(collector)
    (collector.store.storage_dir/"operator"/"bad.json").write_text("broken")
    with pytest.raises(ObservationRetrievalError) as exc: collector.store.load_records_for_operator("operator")
    assert len(exc.value.errors)==1 and exc.value.records[0].observation_id==r.observation_id

def test_event_measurements_require_complete_interval(collector):
    events=[event("RUNTIME_RETRY"),event("RUNTIME_RETRY")]
    r=collect(collector,evidence_events=events)
    assert r.retry_count is None
    r=collect(collector,evidence_events=events,event_log_complete=True,
        measurement_interval={"started_at":"2026-09-11T00:00:00+00:00","completed_at":"2026-09-11T00:00:05+00:00","source_reference":"clock"})
    assert r.retry_count==2 and r.rebuild_count==0 and r.elapsed_time==5

@pytest.mark.parametrize("state",["FAILED","FAIL","ERROR","HALTED"])
def test_failure_never_normal(collector,state):
    assert "NORMAL_EXECUTION" not in kinds(collect(collector,end=state))

def test_persistence_failure_is_visible(collector):
    collector.store.save_record=lambda record: (_ for _ in ()).throw(OSError("disk full"))
    r=collect(collector)
    assert r.evidence_completeness=="COLLECTION_FAILED"
    assert r.collection_errors[-1]["retryable"] is True


def test_real_runtime_understanding_bridge_retains_complete_record(collector,tmp_path):
    from types import SimpleNamespace
    from interactive_mode_ai import ModeRuntime
    from understanding import UnderstandingEngine, UnderstandingStore
    class CapturingEngine(UnderstandingEngine):
        def process(self,request):
            self.received=deepcopy(request)
            return super().process(request)
    engine=CapturingEngine(UnderstandingStore(tmp_path / "understanding.sqlite3"))
    runtime=ModeRuntime.__new__(ModeRuntime)
    runtime.understanding_engine=engine
    runtime.runtime_observation_collector=collector
    evidence={}
    for names in EVIDENCE_GROUPS.values():
        for name in names:
            evidence[name]=[] if name in LIST_FIELDS else 0 if name in MEASUREMENTS else "source:"+name
    observation=collect(collector,**evidence)
    before=observation.to_dict()
    result=runtime._understand_observation(observation)
    assert not result.errors
    assert engine.received.runtime_observation.to_dict()==before
    assert engine.received.relevant_context["observation_evidence"]==before
    loaded=collector.store.load_record("operator",observation.observation_id)
    assert loaded.metadata["understanding"]["understanding_id"]==result.final_understanding.understanding_id
    for names in EVIDENCE_GROUPS.values():
        for name in names: assert getattr(loaded,name)==getattr(engine.received.runtime_observation,name)


def test_builder_real_receipts_feed_observation(tmp_path):
    from builder.tests.test_builder_entry import _valid_handoff_payload
    from builder.core.build_entry import run_builder_core
    result=run_builder_core(_valid_handoff_payload(root=tmp_path),str(tmp_path))
    records=RuntimeObservationStore(tmp_path/".observations").load_records_for_operator("__unattributed__")
    assert len(records)==1
    r=records[0]
    assert r.completion_claim==result.validation_status=="PASS"
    # The saved event precedes its own persistence verification. The terminal
    # receipt adds that check only after independently retrieving this record.
    assert r.validation_results==[v for v in result.validation_results
        if v.get('validation_type') != 'observation_persistence']
    custody=[v for v in result.validation_results if v.get('validation_type')=='observation_persistence']
    assert len(custody)==1 and custody[0]['state']=='PASSED'
    assert Path(custody[0]['evidence_reference']).is_file()
    assert r.produced_receipts==[result.receipt_path]
    assert "COMPLETION_PROVEN" not in kinds(r)
    assert "acting_identity" in r.missing_fields


def test_builder_failure_keeps_original_exception_and_observation(tmp_path, monkeypatch):
    from builder.core.build_entry import run_builder_core
    from builder.tests.test_builder_entry import _valid_handoff_payload
    def fail(*args, **kwargs):
        raise ValueError("construction failed")
    monkeypatch.setattr("builder.core.build_entry.construct_code", fail)
    with pytest.raises(ValueError, match="construction failed"):
        run_builder_core(_valid_handoff_payload(root=tmp_path),str(tmp_path))
    r=RuntimeObservationStore(tmp_path/".observations").load_records_for_operator("__unattributed__")[0]
    assert "EXECUTION_FAILURE" in kinds(r)
    assert not r.produced_receipts


def test_complete_failure_is_not_success(collector):
    r=collect(collector,end="FAILED",failed_transitions=["A->B"])
    assert r.evidence_completeness=="COMPLETE"
    assert "EXECUTION_FAILURE" in kinds(r)
    assert "NORMAL_EXECUTION" not in kinds(r)

@pytest.mark.parametrize("field,value",[("retry_count",-1),("elapsed_time",float("nan")),("operation_count",True),("operation_count",1.5)])
def test_invalid_measurement_not_captured(collector,field,value):
    r=collect(collector,**{field:value})
    assert getattr(r,field) is None
    assert r.collection_errors
    assert r.evidence_completeness!="COMPLETE"

@pytest.mark.parametrize("data",[{"evidence_events":"bad"},{"required_evidence_fields":[{}]},
    {"evidence_package":{"unknown":{}}},{"evidence_events":[event("GOVERNING_LAW_DISCOVERED")]},
    {"evidence_events":[{"observation_type":"AUTHORITY_DENY","fields":{"authority_decision":"DENY"}}]}])
def test_malformed_evidence_fails_partial(collector,data):
    r=collect(collector,**data)
    assert r.collection_errors
    assert r.evidence_completeness!="COMPLETE"
    assert "NORMAL_EXECUTION" not in kinds(r)


def test_explicit_event_vocabulary_roundtrips(collector):
    for kind in RuntimeObservationType:
        if kind==RuntimeObservationType.NORMAL_EXECUTION: continue
        r=collect(collector,evidence_events=[event(kind.value)])
        assert kind in r.observation_types
        assert kind in collector.store.load_record("operator",r.observation_id).observation_types


def test_structural_filters_and_operator_isolation(collector):
    r=collect(collector,mechanism_results=[{"mechanism_id":"m","state":"FAILED"}],authority_decision="DENY",attempt_id="a")
    assert collector.store.query_records("operator",mechanism_results={"mechanism_id":"m"},authority_decision="DENY")[0].observation_id==r.observation_id
    assert collector.store.query_records("another",attempt_id="a")==[]
    with pytest.raises(ValueError): collector.store.query_records("operator",made_up="x")


def test_public_exports():
    import runtime_observation as package
    for name in package.__all__: assert getattr(package,name)


def test_occurrence_retrieval(collector):
    collect(collector,retry_count=0)
    a=collect(collector,retry_count=1)
    b=collect(collector,retry_count=3)
    assert {r.observation_id for r in collector.store.query_records("operator",retry_count={"gt":0})}=={a.observation_id,b.observation_id}


def test_supervisor_observation_failure_does_not_escape():
    from types import SimpleNamespace
    from supervisor_bridge.mode_adapter import ModeAdapter
    runtime=SimpleNamespace(_observe_runtime_event=lambda *a,**k: (_ for _ in ()).throw(OSError("disk full")))
    ModeAdapter._observe(runtime,"supervisor_result",{})


def test_memory_observation_preserves_scope_without_copying_session_fact(collector):
    from types import SimpleNamespace
    from interactive_mode_ai import ModeRuntime
    from interactive_mode_ai import RuntimeState
    runtime=ModeRuntime.__new__(ModeRuntime)
    runtime.context=SimpleNamespace(identity=SimpleNamespace(operator_id="operator"),active_thread=SimpleNamespace(thread_id="thread"),runtime_state=RuntimeState.IDLE)
    runtime.runtime_observation_collector=collector
    r=runtime._observe_runtime_event("memory_result",{"authorization_state":"NOT_REQUIRED","scope":"SESSION_ONLY","session_only":True})
    assert r.authority_scope=="SESSION_ONLY" and r.authority_decision is None
    assert r.input_text==""


def test_authoritative_collection_order(collector):
    from runtime_observation.observation_classifier import RuntimeObservationClassifier
    order=[]
    class Classifier(RuntimeObservationClassifier):
        def classify(self,**kwargs):
            order.append("classifier")
            return super().classify(**kwargs)
    class Builder(RuntimeObservationBuilder):
        def build(self,**kwargs):
            order.append("builder")
            return super().build(**kwargs)
    collector.classifier=Classifier()
    collector.builder=Builder()
    original=collector.store.save_record
    def save(record):
        order.append("store")
        return original(record)
    collector.store.save_record=save
    collect(collector)
    assert order==["classifier","builder","store"]
