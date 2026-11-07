from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class RuntimeObservationType(str, Enum):
    NORMAL_EXECUTION = "NORMAL_EXECUTION"
    OPERATOR_CHALLENGE = "OPERATOR_CHALLENGE"
    OPERATOR_CORRECTION = "OPERATOR_CORRECTION"
    KNOWLEDGE_ROUTING_ISSUE = "KNOWLEDGE_ROUTING_ISSUE"
    MEMORY_ISSUE = "MEMORY_ISSUE"
    CONTEXT_ASSEMBLY_ISSUE = "CONTEXT_ASSEMBLY_ISSUE"
    RESPONSE_QUALITY_ISSUE = "RESPONSE_QUALITY_ISSUE"
    RUNTIME_ERROR = "RUNTIME_ERROR"
    GOVERNANCE_BOUNDARY_EVENT = "GOVERNANCE_BOUNDARY_EVENT"

    CONTEXT_RETRIEVAL_FAILURE = "CONTEXT_RETRIEVAL_FAILURE"
    PARTIAL_CONTEXT = "PARTIAL_CONTEXT"

    KNOWLEDGE_ROUTING_SUCCESS = "KNOWLEDGE_ROUTING_SUCCESS"
    KNOWLEDGE_ROUTING_FAILURE = "KNOWLEDGE_ROUTING_FAILURE"

    MEMORY_RETRIEVAL_FAILURE = "MEMORY_RETRIEVAL_FAILURE"

    CLARIFICATION_REQUEST = "CLARIFICATION_REQUEST"
    CLARIFICATION_LOOP = "CLARIFICATION_LOOP"

    RUNTIME_RETRY = "RUNTIME_RETRY"
    FALLBACK_EXECUTION = "FALLBACK_EXECUTION"

    INTERPRETATION_CONFLICT = "INTERPRETATION_CONFLICT"
    EVIDENCE_MISSING = "EVIDENCE_MISSING"
    REALITY_CONFLICT = "REALITY_CONFLICT"

    COMPONENT_EXECUTION = "COMPONENT_EXECUTION"
    COMPONENT_SKIPPED = "COMPONENT_SKIPPED"
    COMPONENT_FAILURE = "COMPONENT_FAILURE"
    EXECUTION_SUCCESS = "EXECUTION_SUCCESS"
    EXECUTION_FAILURE = "EXECUTION_FAILURE"
    TRANSITION_ATTEMPT = "TRANSITION_ATTEMPT"
    TRANSITION_COMPLETED = "TRANSITION_COMPLETED"
    TRANSITION_REJECTED = "TRANSITION_REJECTED"
    TRANSITION_FAILED = "TRANSITION_FAILED"
    DEPENDENCY_REQUEST = "DEPENDENCY_REQUEST"
    DEPENDENCY_SATISFIED = "DEPENDENCY_SATISFIED"
    DEPENDENCY_MISSING = "DEPENDENCY_MISSING"
    DEPENDENCY_FAILURE = "DEPENDENCY_FAILURE"
    HANDOFF_ATTEMPT = "HANDOFF_ATTEMPT"
    HANDOFF_SUCCESS = "HANDOFF_SUCCESS"
    HANDOFF_FAILURE = "HANDOFF_FAILURE"
    RELATIONSHIP_EXERCISED = "RELATIONSHIP_EXERCISED"
    CONSTRAINT_TRIGGERED = "CONSTRAINT_TRIGGERED"
    CONSTRAINT_SATISFIED = "CONSTRAINT_SATISFIED"
    CONSTRAINT_VIOLATED = "CONSTRAINT_VIOLATED"
    INVARIANT_CHECK = "INVARIANT_CHECK"
    INVARIANT_PRESERVED = "INVARIANT_PRESERVED"
    INVARIANT_VIOLATED = "INVARIANT_VIOLATED"
    INVARIANT_UNVERIFIED = "INVARIANT_UNVERIFIED"
    AUTHORITY_REQUEST = "AUTHORITY_REQUEST"
    AUTHORITY_ALLOW = "AUTHORITY_ALLOW"
    AUTHORITY_DENY = "AUTHORITY_DENY"
    AUTHORITY_DEFER = "AUTHORITY_DEFER"
    AUTHORITY_MISSING = "AUTHORITY_MISSING"
    OVERRIDE_ATTEMPT = "OVERRIDE_ATTEMPT"
    EVIDENCE_LOCATED = "EVIDENCE_LOCATED"
    EVIDENCE_VALIDATED = "EVIDENCE_VALIDATED"
    EVIDENCE_REJECTED = "EVIDENCE_REJECTED"
    COMPLETION_CLAIM = "COMPLETION_CLAIM"
    COMPLETION_PROVEN = "COMPLETION_PROVEN"
    COMPLETION_UNPROVEN = "COMPLETION_UNPROVEN"
    RECOVERY_ATTEMPT = "RECOVERY_ATTEMPT"
    RECOVERY_SUCCESS = "RECOVERY_SUCCESS"
    RECOVERY_FAILURE = "RECOVERY_FAILURE"
    ROLLBACK_ATTEMPT = "ROLLBACK_ATTEMPT"
    ROLLBACK_COMPLETED = "ROLLBACK_COMPLETED"
    REPLAY_ATTEMPT = "REPLAY_ATTEMPT"
    REPLAY_COMPLETED = "REPLAY_COMPLETED"
    STRUCTURAL_ELEMENT_OBSERVED = "STRUCTURAL_ELEMENT_OBSERVED"
    SYSTEM_BOUNDARY_OBSERVED = "SYSTEM_BOUNDARY_OBSERVED"
    BOUNDARY_CROSSING = "BOUNDARY_CROSSING"
    NESTED_STRUCTURE_OBSERVED = "NESTED_STRUCTURE_OBSERVED"
    STRUCTURAL_ELEMENT_REMOVED = "STRUCTURAL_ELEMENT_REMOVED"
    STRUCTURAL_ELEMENT_DISABLED = "STRUCTURAL_ELEMENT_DISABLED"
    STRUCTURAL_ELEMENT_SUBSTITUTED = "STRUCTURAL_ELEMENT_SUBSTITUTED"
    MECHANISM_EXECUTION = "MECHANISM_EXECUTION"
    MECHANISM_SUCCESS = "MECHANISM_SUCCESS"
    MECHANISM_FAILURE = "MECHANISM_FAILURE"
    MECHANISM_BYPASSED = "MECHANISM_BYPASSED"
    MECHANISM_UNAVAILABLE = "MECHANISM_UNAVAILABLE"
    MECHANISM_SUBSTITUTED = "MECHANISM_SUBSTITUTED"
    VARIATION_OBSERVED = "VARIATION_OBSERVED"
    PERTURBATION_APPLIED = "PERTURBATION_APPLIED"
    PERTURBATION_RESULT = "PERTURBATION_RESULT"
    SUBSTITUTION_OBSERVED = "SUBSTITUTION_OBSERVED"
    OBJECTIVE_ATTEMPT_STARTED = "OBJECTIVE_ATTEMPT_STARTED"
    OBJECTIVE_ATTEMPT_COMPLETED = "OBJECTIVE_ATTEMPT_COMPLETED"
    OBJECTIVE_ATTEMPT_ABANDONED = "OBJECTIVE_ATTEMPT_ABANDONED"
    OBJECTIVE_COMPLETION_CLAIM = "OBJECTIVE_COMPLETION_CLAIM"
    OBJECTIVE_COMPLETION_VALIDATED = "OBJECTIVE_COMPLETION_VALIDATED"
    OBJECTIVE_COMPLETION_UNPROVEN = "OBJECTIVE_COMPLETION_UNPROVEN"
    CORRECTION_REQUIRED = "CORRECTION_REQUIRED"
    REWORK_REQUIRED = "REWORK_REQUIRED"
    REBUILD_REQUIRED = "REBUILD_REQUIRED"
    REPEATED_EXPLANATION = "REPEATED_EXPLANATION"
    OPERATOR_INTERVENTION = "OPERATOR_INTERVENTION"
    MANUAL_INTERVENTION = "MANUAL_INTERVENTION"
    OUTPUT_DISCARDED = "OUTPUT_DISCARDED"
    OUTPUT_SUPERSEDED = "OUTPUT_SUPERSEDED"
    OUTPUT_ACCEPTED = "OUTPUT_ACCEPTED"
    COMPARABLE_ATTEMPT_RECORDED = "COMPARABLE_ATTEMPT_RECORDED"


@dataclass
class RuntimeObservationRecord:

    # Identity

    observation_id: str
    runtime_session_id: str = ""
    interaction_id: str = ""
    semantic_state_id: str = ""

    operator_id: str = ""
    thread_id: str = ""

    # Conversation

    input_text: str = ""
    response_text: str = ""

    # Runtime State

    runtime_state_start: str = ""
    runtime_state_end: str = ""

    # Context Custody

    requested_context_sources: list[str] = field(default_factory=list)
    loaded_context_sources: list[str] = field(default_factory=list)
    missing_context_sources: list[str] = field(default_factory=list)
    failed_context_sources: list[str] = field(default_factory=list)

    retrieval_order: list[str] = field(default_factory=list)
    context_confidence: float | None = None

    context_ready: bool | None = None

    # Knowledge Custody

    requested_domain: str = ""
    routed_domain: str = ""
    knowledge_domain: str = ""

    routing_confidence: float | None = None
    routing_reason: str = ""

    retrieved_documents: list[str] = field(default_factory=list)
    rejected_documents: list[str] = field(default_factory=list)

    fallback_used: bool = False

    # Decision Custody

    orchestration_plan_id: str | None = None

    executed_components: list[str] = field(default_factory=list)
    skipped_components: list[str] = field(default_factory=list)

    execution_path: list[str] = field(default_factory=list)
    runtime_decisions: list[str] = field(default_factory=list)

    governance_events: list[str] = field(default_factory=list)

    # Runtime Metrics

    execution_time: float | None = None
    retrieval_time: float | None = None

    clarification_count: int | None = None
    retry_count: int | None = None
    fallback_count: int | None = None

    memory_hits: int | None = None
    memory_misses: int | None = None

    # Trace References

    trace_reference: str | None = None

    orchestration_trace: str | None = None
    retrieval_trace: str | None = None
    reasoning_trace: str | None = None
    governance_trace: str | None = None

    # Observation Classification

    custody_type: str = ""
    drift_type: str = ""

    runtime_component: str = ""
    affected_runtime_stage: str = ""

    # Recovery

    recovery_attempted: bool = False
    recovery_action: str = ""
    recovery_status: str = ""

    # Evidence

    evidence_reference: str | None = None
    operator_correction_reference: str | None = None

    # Legacy Flags

    challenge_detected: bool = False
    correction_detected: bool = False
    unexpected_behavior: bool = False

    observation_types: list[RuntimeObservationType] = field(default_factory=list)

    # entity_evidence
    observed_entities: list[Any] = field(default_factory=list)
    participating_components: list[Any] = field(default_factory=list)
    acting_entities: list[Any] = field(default_factory=list)
    actor_roles: list[Any] = field(default_factory=list)
    actor_references: list[Any] = field(default_factory=list)
    affected_entities: list[Any] = field(default_factory=list)
    # state_evidence
    pre_execution_state: Any | None = None
    post_execution_state: Any | None = None
    intermediate_states: list[Any] = field(default_factory=list)
    requested_state: Any | None = None
    observed_state: Any | None = None
    state_source_references: list[Any] = field(default_factory=list)
    state_evidence_status: Any | None = None
    # transition_evidence
    attempted_transitions: list[Any] = field(default_factory=list)
    completed_transitions: list[Any] = field(default_factory=list)
    rejected_transitions: list[Any] = field(default_factory=list)
    failed_transitions: list[Any] = field(default_factory=list)
    transition_source_state: Any | None = None
    transition_target_state: Any | None = None
    actual_result_state: Any | None = None
    transition_trigger: Any | None = None
    transition_receipts: list[Any] = field(default_factory=list)
    # relationship_evidence
    declared_relationships: list[Any] = field(default_factory=list)
    exercised_relationships: list[Any] = field(default_factory=list)
    input_relationships: list[Any] = field(default_factory=list)
    output_relationships: list[Any] = field(default_factory=list)
    upstream_components: list[Any] = field(default_factory=list)
    downstream_components: list[Any] = field(default_factory=list)
    handoff_records: list[Any] = field(default_factory=list)
    relationship_evidence_references: list[Any] = field(default_factory=list)
    # dependency_evidence
    declared_dependencies: list[Any] = field(default_factory=list)
    requested_dependencies: list[Any] = field(default_factory=list)
    accessed_dependencies: list[Any] = field(default_factory=list)
    satisfied_dependencies: list[Any] = field(default_factory=list)
    missing_dependencies: list[Any] = field(default_factory=list)
    failed_dependencies: list[Any] = field(default_factory=list)
    dependency_results: list[Any] = field(default_factory=list)
    dependency_receipts: list[Any] = field(default_factory=list)
    # constraint_evidence
    declared_constraints: list[Any] = field(default_factory=list)
    triggered_constraints: list[Any] = field(default_factory=list)
    satisfied_constraints: list[Any] = field(default_factory=list)
    violated_constraints: list[Any] = field(default_factory=list)
    unresolved_constraints: list[Any] = field(default_factory=list)
    constraint_sources: list[Any] = field(default_factory=list)
    constraint_receipts: list[Any] = field(default_factory=list)
    # invariant_evidence
    declared_invariants: list[Any] = field(default_factory=list)
    invariant_checks_performed: list[Any] = field(default_factory=list)
    preserved_invariants: list[Any] = field(default_factory=list)
    violated_invariants: list[Any] = field(default_factory=list)
    unverified_invariants: list[Any] = field(default_factory=list)
    invariant_check_results: list[Any] = field(default_factory=list)
    invariant_evidence_references: list[Any] = field(default_factory=list)
    # authority_evidence
    acting_identity: Any | None = None
    authority_source: Any | None = None
    authority_scope: Any | None = None
    authority_request: Any | None = None
    authority_decision: Any | None = None
    authority_decision_source: Any | None = None
    permitted_actions: list[Any] = field(default_factory=list)
    denied_actions: list[Any] = field(default_factory=list)
    deferred_actions: list[Any] = field(default_factory=list)
    override_attempted: Any | None = None
    override_result: Any | None = None
    authorization_receipts: list[Any] = field(default_factory=list)
    # outcome_evidence
    requested_outcome: Any | None = None
    expected_outcome_reference: Any | None = None
    completion_claim: Any | None = None
    observed_outcome: Any | None = None
    output_artifacts: list[Any] = field(default_factory=list)
    produced_receipts: list[Any] = field(default_factory=list)
    validation_results: list[Any] = field(default_factory=list)
    completion_evidence: list[Any] = field(default_factory=list)
    unresolved_outcome_evidence: list[Any] = field(default_factory=list)
    # consequence_evidence
    immediate_state_changes: list[Any] = field(default_factory=list)
    directly_observed_effects: list[Any] = field(default_factory=list)
    emitted_events: list[Any] = field(default_factory=list)
    triggered_components: list[Any] = field(default_factory=list)
    downstream_execution_references: list[Any] = field(default_factory=list)
    rollback_events: list[Any] = field(default_factory=list)
    recovery_events: list[Any] = field(default_factory=list)
    # composition_boundary_evidence
    structural_elements: list[Any] = field(default_factory=list)
    element_types: list[Any] = field(default_factory=list)
    parent_child_relationships: list[Any] = field(default_factory=list)
    containment_relationships: list[Any] = field(default_factory=list)
    membership_relationships: list[Any] = field(default_factory=list)
    declared_system_boundaries: list[Any] = field(default_factory=list)
    observed_boundary_crossings: list[Any] = field(default_factory=list)
    boundary_events: list[Any] = field(default_factory=list)
    nested_structure_references: list[Any] = field(default_factory=list)
    composition_evidence_references: list[Any] = field(default_factory=list)
    # mechanism_evidence
    observed_mechanisms: list[Any] = field(default_factory=list)
    mechanism_ids: list[Any] = field(default_factory=list)
    mechanism_types: list[Any] = field(default_factory=list)
    mechanism_inputs: list[Any] = field(default_factory=list)
    mechanism_outputs: list[Any] = field(default_factory=list)
    mechanism_pre_states: list[Any] = field(default_factory=list)
    mechanism_post_states: list[Any] = field(default_factory=list)
    mechanism_results: list[Any] = field(default_factory=list)
    bypassed_mechanisms: list[Any] = field(default_factory=list)
    failed_mechanisms: list[Any] = field(default_factory=list)
    unavailable_mechanisms: list[Any] = field(default_factory=list)
    missing_mechanism_claims: list[Any] = field(default_factory=list)
    mechanism_evidence_references: list[Any] = field(default_factory=list)
    # variation_perturbation_evidence
    changed_elements: list[Any] = field(default_factory=list)
    removed_elements: list[Any] = field(default_factory=list)
    disabled_elements: list[Any] = field(default_factory=list)
    substituted_elements: list[Any] = field(default_factory=list)
    bypassed_elements: list[Any] = field(default_factory=list)
    perturbation_type: Any | None = None
    perturbation_source: Any | None = None
    variation_pre_state: Any | None = None
    variation_post_state: Any | None = None
    observed_variation_effects: list[Any] = field(default_factory=list)
    variation_receipts: list[Any] = field(default_factory=list)
    comparison_group_reference: Any | None = None
    perturbation_evidence_references: list[Any] = field(default_factory=list)
    # productivity_evidence
    objective_id: Any | None = None
    objective_reference: Any | None = None
    attempt_id: Any | None = None
    parent_attempt_id: Any | None = None
    objective_state_before: Any | None = None
    objective_state_after: Any | None = None
    objective_completion_claim: Any | None = None
    objective_completion_evidence: list[Any] = field(default_factory=list)
    objective_validation_reference: Any | None = None
    operation_count: int | None = None
    interaction_turn_count: int | None = None
    model_response_count: int | None = None
    operator_message_count: int | None = None
    clarification_loop_count: int | None = None
    correction_count: int | None = None
    operator_correction_count: int | None = None
    system_correction_count: int | None = None
    rebuild_count: int | None = None
    rework_count: int | None = None
    repeated_context_request_count: int | None = None
    repeated_explanation_count: int | None = None
    operator_intervention_count: int | None = None
    manual_intervention_count: int | None = None
    abandoned_attempt_count: int | None = None
    usable_output_count: int | None = None
    discarded_output_count: int | None = None
    superseded_output_count: int | None = None
    elapsed_time: Any | None = None
    active_execution_time: Any | None = None
    waiting_time: Any | None = None
    validation_time: Any | None = None
    resource_usage: Any | None = None
    resource_cost_reference: Any | None = None
    external_tool_call_count: int | None = None
    component_execution_count: int | None = None
    prior_understanding_references_used: list[Any] = field(default_factory=list)
    prior_context_references_reused: list[Any] = field(default_factory=list)
    comparable_attempt_reference: Any | None = None
    productivity_measurement_reference: Any | None = None
    productivity_evidence_status: Any | None = None
    # evidence_lineage
    evidence_ids: list[Any] = field(default_factory=list)
    evidence_sources: list[Any] = field(default_factory=list)
    evidence_types: list[Any] = field(default_factory=list)
    evidence_timestamps: list[Any] = field(default_factory=list)
    source_components: list[Any] = field(default_factory=list)
    source_traces: list[Any] = field(default_factory=list)
    validation_references: list[Any] = field(default_factory=list)
    parent_observation_ids: list[Any] = field(default_factory=list)
    child_observation_ids: list[Any] = field(default_factory=list)
    correlation_id: Any | None = None
    evidence_completeness: str = "PARTIAL"
    field_availability: dict[str, str] = field(default_factory=dict)
    missing_fields: list[str] = field(default_factory=list)
    collection_errors: list[dict[str, Any]] = field(default_factory=list)
    evidence_events: list[dict[str, Any]] = field(default_factory=list)
    field_sources: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    required_evidence_fields: list[str] = field(default_factory=list)

    # Versioning

    observation_version: str = "3.2"

    created_at: str = field(default_factory=lambda: utc_now_iso())
    updated_at: str = field(default_factory=lambda: utc_now_iso())

    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["observation_types"] = [
            item.value for item in self.observation_types
        ]
        return data

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "RuntimeObservationRecord":

        observation_types = [
            RuntimeObservationType(item)
            for item in data.get("observation_types", [])
        ]

        return RuntimeObservationRecord(
            **{
                **data,
                "observation_types": observation_types,
            }
        )


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def generate_observation_id() -> str:
    return f"ro-{uuid4().hex}"

# Specification v3.2 section 5: canonical evidence package membership.
EVIDENCE_GROUPS = {
    'entity_evidence': ['observed_entities', 'participating_components', 'acting_entities', 'actor_roles', 'actor_references', 'affected_entities'],
    'state_evidence': ['pre_execution_state', 'post_execution_state', 'intermediate_states', 'requested_state', 'observed_state', 'state_source_references', 'state_evidence_status'],
    'transition_evidence': ['attempted_transitions', 'completed_transitions', 'rejected_transitions', 'failed_transitions', 'transition_source_state', 'transition_target_state', 'actual_result_state', 'transition_trigger', 'transition_receipts'],
    'relationship_evidence': ['declared_relationships', 'exercised_relationships', 'input_relationships', 'output_relationships', 'upstream_components', 'downstream_components', 'handoff_records', 'relationship_evidence_references'],
    'dependency_evidence': ['declared_dependencies', 'requested_dependencies', 'accessed_dependencies', 'satisfied_dependencies', 'missing_dependencies', 'failed_dependencies', 'dependency_results', 'dependency_receipts'],
    'constraint_evidence': ['declared_constraints', 'triggered_constraints', 'satisfied_constraints', 'violated_constraints', 'unresolved_constraints', 'constraint_sources', 'constraint_receipts'],
    'invariant_evidence': ['declared_invariants', 'invariant_checks_performed', 'preserved_invariants', 'violated_invariants', 'unverified_invariants', 'invariant_check_results', 'invariant_evidence_references'],
    'authority_evidence': ['acting_identity', 'authority_source', 'authority_scope', 'authority_request', 'authority_decision', 'authority_decision_source', 'permitted_actions', 'denied_actions', 'deferred_actions', 'override_attempted', 'override_result', 'authorization_receipts'],
    'outcome_evidence': ['requested_outcome', 'expected_outcome_reference', 'completion_claim', 'observed_outcome', 'output_artifacts', 'produced_receipts', 'validation_results', 'completion_evidence', 'unresolved_outcome_evidence'],
    'consequence_evidence': ['immediate_state_changes', 'directly_observed_effects', 'emitted_events', 'triggered_components', 'downstream_execution_references', 'rollback_events', 'recovery_events'],
    'composition_boundary_evidence': ['structural_elements', 'element_types', 'parent_child_relationships', 'containment_relationships', 'membership_relationships', 'declared_system_boundaries', 'observed_boundary_crossings', 'boundary_events', 'nested_structure_references', 'composition_evidence_references'],
    'mechanism_evidence': ['observed_mechanisms', 'mechanism_ids', 'mechanism_types', 'mechanism_inputs', 'mechanism_outputs', 'mechanism_pre_states', 'mechanism_post_states', 'mechanism_results', 'bypassed_mechanisms', 'failed_mechanisms', 'unavailable_mechanisms', 'missing_mechanism_claims', 'mechanism_evidence_references'],
    'variation_perturbation_evidence': ['changed_elements', 'removed_elements', 'disabled_elements', 'substituted_elements', 'bypassed_elements', 'perturbation_type', 'perturbation_source', 'variation_pre_state', 'variation_post_state', 'observed_variation_effects', 'variation_receipts', 'comparison_group_reference', 'perturbation_evidence_references'],
    'productivity_evidence': ['objective_id', 'objective_reference', 'attempt_id', 'parent_attempt_id', 'objective_state_before', 'objective_state_after', 'objective_completion_claim', 'objective_completion_evidence', 'objective_validation_reference', 'operation_count', 'interaction_turn_count', 'model_response_count', 'operator_message_count', 'clarification_count', 'clarification_loop_count', 'correction_count', 'operator_correction_count', 'system_correction_count', 'retry_count', 'fallback_count', 'rebuild_count', 'rework_count', 'repeated_context_request_count', 'repeated_explanation_count', 'operator_intervention_count', 'manual_intervention_count', 'abandoned_attempt_count', 'usable_output_count', 'discarded_output_count', 'superseded_output_count', 'elapsed_time', 'active_execution_time', 'waiting_time', 'retrieval_time', 'validation_time', 'resource_usage', 'resource_cost_reference', 'external_tool_call_count', 'component_execution_count', 'prior_understanding_references_used', 'prior_context_references_reused', 'comparable_attempt_reference', 'productivity_measurement_reference', 'productivity_evidence_status'],
    'evidence_lineage': ['evidence_ids', 'evidence_sources', 'evidence_types', 'evidence_timestamps', 'source_components', 'source_traces', 'validation_references', 'parent_observation_ids', 'child_observation_ids', 'correlation_id'],
}
