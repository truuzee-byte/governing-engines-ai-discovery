from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from runtime_observation.observation_record import RuntimeObservationType

CHALLENGE_MARKERS=("are you sure","prove it","show evidence","verify","that's wrong","you are wrong")
CORRECTION_MARKERS=("fix this","correct this","actually","i meant","replace")
UNEXPECTED_BEHAVIOR_MARKERS=("you lied","you skipped","you ignored","you assumed")
CLARIFICATION_MARKERS=("clarify","what do you mean","can you clarify","i don't understand")
MEMORY_MARKERS=("remember","you forgot","earlier you said")
CONTEXT_MARKERS=("missing context","out of context","no context")
REALITY_MARKERS=("that's not true","incorrect","not accurate","that never happened")

@dataclass
class RuntimeObservationClassification:
    observation_types:list[RuntimeObservationType]
    challenge_detected:bool
    correction_detected:bool
    unexpected_behavior:bool
    reasons:list[str]=field(default_factory=list)
    metadata:dict[str,Any]=field(default_factory=dict)
    classification_confidence:float=1.0

class RuntimeObservationClassifier:

    def classify(self,*,input_text:str,response_text:str,context_ready:bool,
                 knowledge_domain:str,runtime_error:str|None=None,
                 metadata:dict[str,Any]|None=None)->RuntimeObservationClassification:
        metadata=dict(metadata or {})
        # Read supplied evidence without changing or interpreting its values.
        package = metadata.get("evidence_package", {})
        if isinstance(package, dict):
            for values in package.values():
                if isinstance(values, dict):
                    for key, value in values.items(): metadata.setdefault(key, value)
        raw_events = metadata.get("evidence_events", [])
        if isinstance(raw_events, list):
            for event in raw_events:
                if isinstance(event, dict) and isinstance(event.get("fields", {}), dict):
                    for key, value in event.get("fields", {}).items(): metadata.setdefault(key, value)
        text=input_text.lower()
        obs=[]
        reasons=[]

        challenge=self._contains(text,CHALLENGE_MARKERS)
        correction=self._contains(text,CORRECTION_MARKERS)
        unexpected=self._contains(text,UNEXPECTED_BEHAVIOR_MARKERS)

        if runtime_error:
            obs.append(RuntimeObservationType.RUNTIME_ERROR); reasons.append("Runtime error detected.")
        if challenge:
            obs.append(RuntimeObservationType.OPERATOR_CHALLENGE); reasons.append("Operator challenge detected.")
        if correction:
            obs.append(RuntimeObservationType.OPERATOR_CORRECTION); reasons.append("Operator correction detected.")
        if unexpected:
            obs.append(RuntimeObservationType.RESPONSE_QUALITY_ISSUE); reasons.append("Unexpected behavior detected.")
        if context_ready is False:
            obs.append(RuntimeObservationType.CONTEXT_ASSEMBLY_ISSUE); reasons.append("Context unavailable.")
        if knowledge_domain=="UNKNOWN":
            obs.append(RuntimeObservationType.KNOWLEDGE_ROUTING_ISSUE); reasons.append("Knowledge routing issue.")
        if self._contains(text,CLARIFICATION_MARKERS):
            obs.append(RuntimeObservationType.CLARIFICATION_REQUEST)
        if self._contains(text,MEMORY_MARKERS):
            obs.append(RuntimeObservationType.MEMORY_ISSUE)
        if self._contains(text,CONTEXT_MARKERS):
            obs.append(RuntimeObservationType.CONTEXT_RETRIEVAL_FAILURE)
        if self._contains(text,REALITY_MARKERS):
            obs.append(RuntimeObservationType.REALITY_CONFLICT)
        if metadata.get("fallback_used"):
            obs.append(RuntimeObservationType.FALLBACK_EXECUTION)
        if (metadata.get("retry_count") or 0)>0:
            obs.append(RuntimeObservationType.RUNTIME_RETRY)
        if metadata.get("context_confidence") is not None and metadata["context_confidence"]<0.5:
            obs.append(RuntimeObservationType.PARTIAL_CONTEXT)
        if (metadata.get("memory_misses") or 0)>0:
            obs.append(RuntimeObservationType.MEMORY_RETRIEVAL_FAILURE)

        # Explicit producer events take precedence over supplemental text markers.
        for event in metadata.get("evidence_events", []):
            if isinstance(event, dict) and event.get("observation_type"):
                try:
                    obs.append(RuntimeObservationType(event["observation_type"]))
                except ValueError:
                    obs.append(RuntimeObservationType.EVIDENCE_MISSING)
                    reasons.append("Unknown event type: " + str(event["observation_type"]))
        mappings = {
            "attempted_transitions": "TRANSITION_ATTEMPT", "completed_transitions": "TRANSITION_COMPLETED",
            "rejected_transitions": "TRANSITION_REJECTED", "failed_transitions": "TRANSITION_FAILED",
            "requested_dependencies": "DEPENDENCY_REQUEST", "satisfied_dependencies": "DEPENDENCY_SATISFIED",
            "missing_dependencies": "DEPENDENCY_MISSING", "failed_dependencies": "DEPENDENCY_FAILURE",
            "exercised_relationships": "RELATIONSHIP_EXERCISED", "triggered_constraints": "CONSTRAINT_TRIGGERED",
            "satisfied_constraints": "CONSTRAINT_SATISFIED", "violated_constraints": "CONSTRAINT_VIOLATED",
            "invariant_checks_performed": "INVARIANT_CHECK", "preserved_invariants": "INVARIANT_PRESERVED",
            "violated_invariants": "INVARIANT_VIOLATED", "unverified_invariants": "INVARIANT_UNVERIFIED",
            "executed_components": "COMPONENT_EXECUTION", "skipped_components": "COMPONENT_SKIPPED",
            "failed_mechanisms": "MECHANISM_FAILURE", "bypassed_mechanisms": "MECHANISM_BYPASSED",
            "unavailable_mechanisms": "MECHANISM_UNAVAILABLE", "observed_mechanisms": "MECHANISM_EXECUTION",
            "structural_elements": "STRUCTURAL_ELEMENT_OBSERVED", "declared_system_boundaries": "SYSTEM_BOUNDARY_OBSERVED",
            "observed_boundary_crossings": "BOUNDARY_CROSSING", "nested_structure_references": "NESTED_STRUCTURE_OBSERVED",
            "removed_elements": "STRUCTURAL_ELEMENT_REMOVED", "disabled_elements": "STRUCTURAL_ELEMENT_DISABLED",
            "substituted_elements": "STRUCTURAL_ELEMENT_SUBSTITUTED", "changed_elements": "VARIATION_OBSERVED",
            "operator_correction_reference": "OPERATOR_CORRECTION", "correction_count": "CORRECTION_REQUIRED",
            "rework_count": "REWORK_REQUIRED", "rebuild_count": "REBUILD_REQUIRED",
            "operator_intervention_count": "OPERATOR_INTERVENTION", "manual_intervention_count": "MANUAL_INTERVENTION",
            "discarded_output_count": "OUTPUT_DISCARDED", "superseded_output_count": "OUTPUT_SUPERSEDED",
            "comparable_attempt_reference": "COMPARABLE_ATTEMPT_RECORDED",
        }
        for key, event_type in mappings.items():
            if metadata.get(key): obs.append(RuntimeObservationType(event_type))
        decision = metadata.get("authority_decision")
        if decision in {"ALLOW", "DENY", "DEFER"}:
            obs.append(RuntimeObservationType("AUTHORITY_" + decision))
        if metadata.get("completion_claim") is not None:
            obs.append(RuntimeObservationType.COMPLETION_CLAIM)
        # Preserve validator reports; never infer completion from an output/receipt.
        for validation in metadata.get("validation_results", []):
            if not isinstance(validation, dict): continue
            state = validation.get("state")
            if state in {"FAILED", "DISCONFIRMED", "REJECTED"}:
                obs.append(RuntimeObservationType.EVIDENCE_REJECTED)
            elif state in {"PASSED", "CONFIRMED"}:
                obs.append(RuntimeObservationType.EVIDENCE_VALIDATED)
        stage = metadata.get('runtime_state_end')
        if stage in {'BUILD_UNPROVEN', 'BUILD_PASS_RP_PENDING', 'SPECIFICATION_NOT_READY', 'CONSTRUCTION_BLOCKED'}:
            obs.append(RuntimeObservationType.EVIDENCE_MISSING)
        if stage == 'BUILD_PASS_RP_DISCONFIRMED':
            obs.append(RuntimeObservationType.REALITY_CONFLICT)
        failed = runtime_error or metadata.get("failure_state") or stage in {"ERROR", "FAILED", "FAIL", "HALTED", "BUILD_FAIL", "GENERATION_FAILED"}
        if failed:
            obs.append(RuntimeObservationType.EXECUTION_FAILURE)
        if metadata.get("collection_errors"):
            obs.append(RuntimeObservationType.EVIDENCE_MISSING)
        if any(x != RuntimeObservationType.NORMAL_EXECUTION for x in obs):
            obs = [x for x in obs if x != RuntimeObservationType.NORMAL_EXECUTION]
        obs=list(dict.fromkeys(obs))
        if not obs:
            obs=[RuntimeObservationType.NORMAL_EXECUTION]
            reasons.append("Normal execution.")

        return RuntimeObservationClassification(
            observation_types=obs,
            challenge_detected=challenge,
            correction_detected=correction,
            unexpected_behavior=unexpected,
            reasons=reasons,
            metadata=metadata,
            classification_confidence=1.0 if obs else 0.0,
        )

    @staticmethod
    def _contains(text:str,markers:tuple[str,...])->bool:
        return any(m in text for m in markers)
