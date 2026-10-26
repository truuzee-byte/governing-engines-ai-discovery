"""Passive evidence assembly, Observation specification v3.2 sections 8 and 23.

None means unavailable; an explicitly supplied empty list or zero is preserved.
Event envelopes carry source_component, timestamp, evidence_reference, fields,
and optional observation_type. Conflicts retain every source value.
"""
from copy import deepcopy
from dataclasses import fields
from datetime import datetime
import math
from runtime_observation.observation_record import RuntimeObservationRecord, RuntimeObservationType, EVIDENCE_GROUPS

LEGACY_GROUPS = {'context_custody': ['requested_context_sources', 'loaded_context_sources', 'missing_context_sources', 'failed_context_sources', 'retrieval_order', 'context_confidence', 'context_ready'], 'knowledge_custody': ['requested_domain', 'routed_domain', 'routing_confidence', 'routing_reason', 'retrieved_documents', 'rejected_documents', 'fallback_used'], 'decision_custody': ['orchestration_plan_id', 'executed_components', 'skipped_components', 'runtime_decisions', 'execution_path', 'governance_events'], 'runtime_metrics': ['execution_time', 'retrieval_time', 'clarification_count', 'retry_count', 'fallback_count', 'memory_hits', 'memory_misses'], 'trace_references': ['trace_reference', 'orchestration_trace', 'retrieval_trace', 'reasoning_trace', 'governance_trace']}
ALL_GROUPS = {**LEGACY_GROUPS, **EVIDENCE_GROUPS}
CANONICAL_FIELDS = {f.name for f in fields(RuntimeObservationRecord)}
LIST_FIELDS = {f.name for f in fields(RuntimeObservationRecord) if str(f.type).startswith("list[")}
MEASUREMENTS = {n for n in CANONICAL_FIELDS if n.endswith("_count")} | {"execution_time", "retrieval_time", "elapsed_time", "active_execution_time", "waiting_time", "validation_time", "memory_hits", "memory_misses", "context_confidence", "routing_confidence"}

class RuntimeObservationBuilder:
    def build(self, *, orchestration_plan=None, metadata=None):
        data = deepcopy(metadata or {})
        errors = []
        sources = deepcopy(data.get("field_sources", {}))
        events = deepcopy(data.get("evidence_events", []))
        if not isinstance(sources, dict):
            errors.append({"stage": "lineage", "error": "field_sources must be an object"})
            sources = {}
        if not isinstance(events, list):
            errors.append({"stage": "assembly", "error": "evidence_events must be a list"})
            events = []
        conflicts = []
        def merge(name, value, source):
            if name not in CANONICAL_FIELDS or name in {"metadata", "observation_id", "observation_version", "operator_id", "thread_id", "collection_errors", "evidence_completeness", "field_sources", "field_availability", "required_evidence_fields", "evidence_events"}:
                errors.append({"stage": "assembly", "field": name, "error": "Unknown canonical field", "source": source})
                return
            if name in data and data[name] != value:
                conflicts.append(name)
                sources.setdefault(name, []).append({"value": deepcopy(data[name]), "source_component": data.get("runtime_component"), "evidence_reference": data.get("trace_reference")})
            else:
                data[name] = deepcopy(value)
            sources.setdefault(name, []).append({**source, "value": deepcopy(value)})
        package = data.get("evidence_package", {})
        if not isinstance(package, dict):
            errors.append({"stage": "assembly", "error": "evidence_package must be an object"})
            package = {}
        for group, values in package.items():
            if group not in ALL_GROUPS or not isinstance(values, dict):
                errors.append({"stage": "assembly", "group": group, "error": "Unknown or malformed evidence group"})
                continue
            for name, value in values.items():
                if name not in ALL_GROUPS[group]:
                    errors.append({"stage": "assembly", "field": name, "error": "Field in wrong evidence group"})
                    continue
                merge(name, value, {"source_component": data.get("runtime_component"), "evidence_reference": data.get("trace_reference")})
        for event in events:
            if not isinstance(event, dict) or not isinstance(event.get("fields", {}), dict):
                errors.append({"stage": "assembly", "error": "Malformed event envelope"})
                continue
            if event.get("observation_type") not in {x.value for x in RuntimeObservationType}:
                errors.append({"stage": "classification", "error": "Unknown or missing explicit event type", "event": event})
            source = {k: event.get(k) for k in ("source_component", "timestamp", "evidence_reference", "event_id")}
            if not all(source.get(k) for k in ("source_component", "timestamp", "evidence_reference")):
                errors.append({"stage": "lineage", "error": "Event source, timestamp and reference required", "source": source})
            for name, value in event.get("fields", {}).items():
                merge(name, value, source)
        for key in ("required_evidence_fields", "missing_fields"):
            if key in data and (not isinstance(data[key], list) or not all(isinstance(x, str) for x in data[key])):
                errors.append({"stage": "assembly", "error": key + " must contain field names"})
                data[key] = []
        for name in CANONICAL_FIELDS & data.keys():
            value = data[name]
            if name in MEASUREMENTS and value is not None:
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0 or (name.endswith("_count") and not isinstance(value, int)):
                    errors.append({"stage": "assembly", "field": name, "error": "Invalid nonnegative measurement", "value": repr(value)})
                    data[name] = None
            elif name in LIST_FIELDS and not isinstance(value, list):
                errors.append({"stage": "assembly", "field": name, "error": "Expected list", "value": repr(value)})
                data.pop(name)
        if orchestration_plan is not None:
            data.setdefault("orchestration_plan_id", orchestration_plan.plan_id)
        interval = data.get("measurement_interval")
        if isinstance(interval, dict) and interval.get("source_reference"):
            try:
                start = datetime.fromisoformat(interval["started_at"])
                end = datetime.fromisoformat(interval["completed_at"])
                if start.tzinfo is None or end.tzinfo is None or end < start:
                    raise ValueError("ordered timezone-aware timestamps required")
                data.setdefault("elapsed_time", (end - start).total_seconds())
                sources.setdefault("elapsed_time", []).append({"source_component": data.get("runtime_component"),
                    "evidence_reference": interval["source_reference"], "value": data["elapsed_time"]})
            except (KeyError, TypeError, ValueError) as exc:
                errors.append({"stage": "measurement", "error": str(exc)})
        # Counts are derivable only from an explicitly complete event interval.
        if data.get("event_log_complete") is True and isinstance(interval, dict) and interval.get("source_reference"):
            counters = {"OPERATOR_CORRECTION": "operator_correction_count", "RUNTIME_RETRY": "retry_count",
                "CLARIFICATION_REQUEST": "clarification_count", "REBUILD_REQUIRED": "rebuild_count",
                "REWORK_REQUIRED": "rework_count", "OPERATOR_INTERVENTION": "operator_intervention_count",
                "MANUAL_INTERVENTION": "manual_intervention_count", "OUTPUT_DISCARDED": "discarded_output_count",
                "OUTPUT_SUPERSEDED": "superseded_output_count", "COMPONENT_EXECUTION": "component_execution_count"}
            for kind, counter in counters.items():
                data.setdefault(counter, sum(isinstance(e, dict) and e.get("observation_type") == kind for e in events))
                sources.setdefault(counter, []).append({"evidence_reference": interval["source_reference"],
                    "source_component": data.get("runtime_component"), "value": data[counter]})
        result = {group: getattr(self, "_build_" + group)(data) for group in ALL_GROUPS}
        result["_canonical"] = {k: v for k, v in data.items() if k in CANONICAL_FIELDS}
        result["_sources"] = sources
        result["_errors"] = errors
        result["_conflicts"] = sorted(set(conflicts))
        return result

    @staticmethod
    def _group(data, name):
        return {key: deepcopy(data[key]) for key in ALL_GROUPS[name] if key in data}

    def _build_context_custody(self, data):
        return self._group(data, 'context_custody')

    def _build_knowledge_custody(self, data):
        return self._group(data, 'knowledge_custody')

    def _build_decision_custody(self, data):
        return self._group(data, 'decision_custody')

    def _build_runtime_metrics(self, data):
        return self._group(data, 'runtime_metrics')

    def _build_trace_references(self, data):
        return self._group(data, 'trace_references')

    def _build_entity_evidence(self, data):
        return self._group(data, 'entity_evidence')

    def _build_state_evidence(self, data):
        return self._group(data, 'state_evidence')

    def _build_transition_evidence(self, data):
        return self._group(data, 'transition_evidence')

    def _build_relationship_evidence(self, data):
        return self._group(data, 'relationship_evidence')

    def _build_dependency_evidence(self, data):
        return self._group(data, 'dependency_evidence')

    def _build_constraint_evidence(self, data):
        return self._group(data, 'constraint_evidence')

    def _build_invariant_evidence(self, data):
        return self._group(data, 'invariant_evidence')

    def _build_authority_evidence(self, data):
        return self._group(data, 'authority_evidence')

    def _build_outcome_evidence(self, data):
        return self._group(data, 'outcome_evidence')

    def _build_consequence_evidence(self, data):
        return self._group(data, 'consequence_evidence')

    def _build_composition_boundary_evidence(self, data):
        return self._group(data, 'composition_boundary_evidence')

    def _build_mechanism_evidence(self, data):
        return self._group(data, 'mechanism_evidence')

    def _build_variation_perturbation_evidence(self, data):
        return self._group(data, 'variation_perturbation_evidence')

    def _build_productivity_evidence(self, data):
        return self._group(data, 'productivity_evidence')

    def _build_evidence_lineage(self, data):
        return self._group(data, 'evidence_lineage')
