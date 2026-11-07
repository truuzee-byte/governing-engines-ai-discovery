# Observation v3.2 implementation contract

Authority: supplied Observation Layer v3.2, especially sections 5–11, 25–26, 30–32.
Implementation follows its ten phases. Understanding architecture is unchanged.

## Evidence, not conclusions

`RuntimeObservationRecord` is the serialized contract. `EVIDENCE_GROUPS` declares
all fifteen expanded groups; the five original groups remain in `LEGACY_GROUPS`.
The builder accepts canonical runtime metadata, grouped `evidence_package`, and
source-linked `evidence_events`. It does not derive meaning, chains, essentiality,
mechanism requirements, causal judgments, or Reality confirmations.

An event envelope contains `observation_type`, `source_component`, `timestamp`,
`evidence_reference`, optional `event_id`, and a `fields` object. Conflicting
values survive in `field_sources` and the original event list; the canonical value
is the first supplied value, not a truth decision. Consumers must check CONFLICT.
Metadata keeps original packages, including malformed values and diagnostics.

## Missingness and completeness

Numeric measurements are nullable: null means unavailable, zero means a supplied
or directly measured zero. `field_availability` distinguishes CAPTURED, UNAVAILABLE,
and CONFLICT for canonical fields. Existing empty defaults are not evidence of
observed absence when availability is UNAVAILABLE.

Producers supply `required_evidence_fields` for their event. The collector also
requires runtime component and trace identity. It does not claim COMPLETE without
an explicit expected-field declaration. Missing required structural evidence is
STRUCTURALLY_PARTIAL; absent lineage is TRACE_INCOMPLETE; contradictory values
are EVIDENCE_CONFLICT; assembly/classification failure is PARTIAL; failed storage
is COLLECTION_FAILED with retryable diagnostics returned to the caller. No disk
write can be guaranteed when the storage medium itself is unavailable.

COMPLETE is collection completeness, not execution success. A complete record can
report a failed execution. No receipt or generated output establishes COMPLETION_PROVEN.
An explicit validator event can be preserved without endorsing its authority.

Objective/attempt measurement requires objective and attempt identities, completion
evidence/reference, elapsed time and resource evidence; otherwise productivity is
PARTIAL. Counts are calculated from events only when the producer declares the
interval complete. Elapsed time requires ordered timezone-aware source timestamps.
No efficiency ratios or causal productivity judgments are invented.

## Retrieval and custody

`query_records(operator_id, **criteria)` filters any canonical field. Nested objects
match key/value subsets; lists match exact items. Numeric gt/gte/lt/lte filters
support correction/retry/rework/intervention occurrences. This is not pattern analysis.
Unreadable records raise ObservationRetrievalError containing diagnostics and the
usable records; search/export never silently skips corrupt evidence. Writes replace
atomically using unique temporary filenames. Concurrent updates to the same record
are still last-writer-wins, not a versioned or transactional event journal.

## Connected sources and boundaries

- Normal interactive results: route metadata, actual assembled source presence,
  memory record IDs, runtime transitions, controller authority decisions, trace and
  provider telemetry. Missing document/recovery/validation evidence remains missing.
- Memory consent paths: outcome, authorization state and scope. Session-only facts
  are not copied into persistent observation content by the added consent observer.
- Supervisor: claim, blocked control state, result and failure observations; original
  message ownership and processing behavior are unchanged.
- Builder: passive result/exception wrapper; actual validation results, command
  results, produced receipt, stage history and evidence references. Records live in
  artifact-local `.observations`, with an explicit `__unattributed__` storage scope
  because the existing Builder handoff does not establish an operator identity.
  `acting_identity` stays unavailable. This scope is not an authenticated identity.
- Understanding receives the unchanged record and its complete serialized evidence
  in relevant_context; the existing engine remains responsible for interpretation.
  Reverse Understanding references remain in observation metadata.

The Understanding proof establishes delivery, preservation, governed processing of
an operator statement, and reverse links. Decomposition proof presents observed
parent/child facts to its existing composition input without inferring essentiality.
It does not claim that the current Understanding interpreter automatically analyzes
all raw v3.2 fields or productivity evidence.

## Acceptance and examples

`tests/test_observation_v32.py` explicitly covers specification scenarios 1–21 and
additional contract, runtime, malformed-evidence and failure tests. The five JSON
examples are synthetic acceptance records, not production evidence or capability proof.

## Before Reality Primacy consumption

Reality Primacy still needs its own authorized evidence evaluation and source-trust
contract. Validator claims remain claims until that boundary evaluates them. Builder
operator identity/cross-runtime correlation, atomic cross-store reverse-link updates,
and richer downstream consumption of raw observation evidence remain integration
limits. Historical v2 records cannot gain missing evidence retroactively; missing
v3 fields retain unavailable/default representations. No Reality code was changed.

## Exact expanded fields

### entity_evidence

`observed_entities`, `participating_components`, `acting_entities`, `actor_roles`, `actor_references`, `affected_entities`

### state_evidence

`pre_execution_state`, `post_execution_state`, `intermediate_states`, `requested_state`, `observed_state`, `state_source_references`, `state_evidence_status`

### transition_evidence

`attempted_transitions`, `completed_transitions`, `rejected_transitions`, `failed_transitions`, `transition_source_state`, `transition_target_state`, `actual_result_state`, `transition_trigger`, `transition_receipts`

### relationship_evidence

`declared_relationships`, `exercised_relationships`, `input_relationships`, `output_relationships`, `upstream_components`, `downstream_components`, `handoff_records`, `relationship_evidence_references`

### dependency_evidence

`declared_dependencies`, `requested_dependencies`, `accessed_dependencies`, `satisfied_dependencies`, `missing_dependencies`, `failed_dependencies`, `dependency_results`, `dependency_receipts`

### constraint_evidence

`declared_constraints`, `triggered_constraints`, `satisfied_constraints`, `violated_constraints`, `unresolved_constraints`, `constraint_sources`, `constraint_receipts`

### invariant_evidence

`declared_invariants`, `invariant_checks_performed`, `preserved_invariants`, `violated_invariants`, `unverified_invariants`, `invariant_check_results`, `invariant_evidence_references`

### authority_evidence

`acting_identity`, `authority_source`, `authority_scope`, `authority_request`, `authority_decision`, `authority_decision_source`, `permitted_actions`, `denied_actions`, `deferred_actions`, `override_attempted`, `override_result`, `authorization_receipts`

### outcome_evidence

`requested_outcome`, `expected_outcome_reference`, `completion_claim`, `observed_outcome`, `output_artifacts`, `produced_receipts`, `validation_results`, `completion_evidence`, `unresolved_outcome_evidence`

### consequence_evidence

`immediate_state_changes`, `directly_observed_effects`, `emitted_events`, `triggered_components`, `downstream_execution_references`, `rollback_events`, `recovery_events`

### composition_boundary_evidence

`structural_elements`, `element_types`, `parent_child_relationships`, `containment_relationships`, `membership_relationships`, `declared_system_boundaries`, `observed_boundary_crossings`, `boundary_events`, `nested_structure_references`, `composition_evidence_references`

### mechanism_evidence

`observed_mechanisms`, `mechanism_ids`, `mechanism_types`, `mechanism_inputs`, `mechanism_outputs`, `mechanism_pre_states`, `mechanism_post_states`, `mechanism_results`, `bypassed_mechanisms`, `failed_mechanisms`, `unavailable_mechanisms`, `missing_mechanism_claims`, `mechanism_evidence_references`

### variation_perturbation_evidence

`changed_elements`, `removed_elements`, `disabled_elements`, `substituted_elements`, `bypassed_elements`, `perturbation_type`, `perturbation_source`, `variation_pre_state`, `variation_post_state`, `observed_variation_effects`, `variation_receipts`, `comparison_group_reference`, `perturbation_evidence_references`

### productivity_evidence

`objective_id`, `objective_reference`, `attempt_id`, `parent_attempt_id`, `objective_state_before`, `objective_state_after`, `objective_completion_claim`, `objective_completion_evidence`, `objective_validation_reference`, `operation_count`, `interaction_turn_count`, `model_response_count`, `operator_message_count`, `clarification_count`, `clarification_loop_count`, `correction_count`, `operator_correction_count`, `system_correction_count`, `retry_count`, `fallback_count`, `rebuild_count`, `rework_count`, `repeated_context_request_count`, `repeated_explanation_count`, `operator_intervention_count`, `manual_intervention_count`, `abandoned_attempt_count`, `usable_output_count`, `discarded_output_count`, `superseded_output_count`, `elapsed_time`, `active_execution_time`, `waiting_time`, `retrieval_time`, `validation_time`, `resource_usage`, `resource_cost_reference`, `external_tool_call_count`, `component_execution_count`, `prior_understanding_references_used`, `prior_context_references_reused`, `comparable_attempt_reference`, `productivity_measurement_reference`, `productivity_evidence_status`

### evidence_lineage

`evidence_ids`, `evidence_sources`, `evidence_types`, `evidence_timestamps`, `source_components`, `source_traces`, `validation_references`, `parent_observation_ids`, `child_observation_ids`, `correlation_id`


## Final verification

Final run: **403 passed in 4.22 seconds**, using the existing Python 3.12 / pytest
installation, with pytest cache disabled and isolated temporary test storage.

Test targets:

- runtime_observation/tests/test_observation_v32.py
- understanding/tests/test_understanding_v12.py
- builder/tests/test_builder_entry.py
- builder/tests/test_build_validator.py
- builder/tests/test_build_plan_generator.py
- builder/tests/test_specification_receiver.py
- builder/tests/test_mode_to_builder_adapter.py
- specs/tests
- persistent_memory/tests
- supervisor_bridge/tests/test_message_claims.py

All 21 numbered Observation scenarios are covered, plus source conflicts,
all-field round trips, malformed evidence, explicit missingness, unreadable storage,
passive failures, occurrence retrieval, package exports, classifier/builder/store
order, real Builder receipts, and the real runtime/Understanding reverse-link path.
The temporary test directories were removed after verification.
