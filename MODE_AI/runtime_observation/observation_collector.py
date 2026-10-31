"""Observation v3.2 collection. Collection errors never control execution."""
from copy import deepcopy
from dataclasses import fields
from runtime_observation.observation_builder import RuntimeObservationBuilder, CANONICAL_FIELDS
from runtime_observation.observation_classifier import RuntimeObservationClassifier
from runtime_observation.observation_record import RuntimeObservationRecord, RuntimeObservationType, generate_observation_id, utc_now_iso
from runtime_observation.observation_store import RuntimeObservationStore


class RuntimeObservationCollector:
    def __init__(self, classifier=None, store=None, builder=None):
        self.classifier = classifier or RuntimeObservationClassifier()
        self.store = store if store is not None else RuntimeObservationStore()
        self.builder = builder or RuntimeObservationBuilder()

    def collect(self, *, operator_id, thread_id, input_text="", response_text="",
                runtime_state_start="", runtime_state_end="", knowledge_domain="",
                orchestration_plan=None, context_ready=None, trace_reference=None,
                runtime_error=None, metadata=None, save=True):
        metadata = deepcopy(metadata or {})
        identity = dict(operator_id=operator_id, thread_id=thread_id,
            input_text=input_text, response_text=response_text,
            runtime_state_start=runtime_state_start, runtime_state_end=runtime_state_end,
            knowledge_domain=knowledge_domain, context_ready=context_ready,
            trace_reference=trace_reference)
        data = {**metadata, **identity}
        if runtime_error: data["failure_state"] = runtime_error
        errors = []
        classification = None
        classification_failure = None
        try:
            classification = self.classifier.classify(input_text=input_text, response_text=response_text,
                context_ready=context_ready, knowledge_domain=knowledge_domain, runtime_error=runtime_error,
                metadata=data)
        except Exception as exc:
            classification_failure = exc
            errors.append({"stage": "classification", "error": type(exc).__name__, "detail": str(exc), "retryable": True})
        conflicts = []
        sources = {}
        try:
            package = self.builder.build(orchestration_plan=orchestration_plan, metadata=data)
            values = dict(package.get("_canonical", {}))
            # Map every evidence group, including knowledge.requested_domain.
            for group, evidence in package.items():
                if not group.startswith("_"): values.update(evidence)
            errors.extend(package.get("_errors", []))
            conflicts = package.get("_conflicts", [])
            sources = package.get("_sources", {})
        except Exception as exc:
            # Preserve original evidence in metadata; do not repeat a failing builder.
            values = dict(identity)
            errors.append({"stage": "assembly", "error": type(exc).__name__, "detail": str(exc), "retryable": True})
        values.update(identity)  # Caller identity is never replaceable by event data.
        values["observation_id"] = generate_observation_id()
        values["observation_version"] = "3.2"
        values["collection_errors"] = list(values.get("collection_errors", [])) + errors
        values["field_sources"] = sources
        captured = set(values)
        values["field_availability"] = {f.name: ("CAPTURED" if f.name in captured and values.get(f.name) is not None else "UNAVAILABLE") for f in fields(RuntimeObservationRecord)}
        # Attach the producer's declared origin, not an invented validator status.
        for key in captured - {"metadata", "field_sources", "evidence_events"}:
            if key not in sources and values.get("runtime_component") and trace_reference:
                sources[key] = [{"source_component": values["runtime_component"], "evidence_reference": trace_reference,
                    "timestamp": utc_now_iso(), "value": deepcopy(values[key])}]
        values["metadata"] = metadata
        if orchestration_plan is not None:
            values["orchestration_plan_id"] = orchestration_plan.plan_id
            values["metadata"]["orchestration_plan"] = orchestration_plan.to_dict()
        if runtime_error: values["metadata"]["runtime_error"] = runtime_error
        required = values.get("required_evidence_fields", [])
        # Producers declare event-specific expected fields. An absent declaration
        # cannot establish completeness. Empty lists and measured zero are evidence.
        required = list(dict.fromkeys(required + ["runtime_component", "trace_reference"]))
        missing = [key for key in required if key not in values or values[key] is None or values[key] == ""]
        values["missing_fields"] = sorted(set(values.get("missing_fields", []) + missing))
        values["required_evidence_fields"] = required
        if any(e.get("stage") == "lineage" for e in errors):
            completeness = "TRACE_INCOMPLETE"
        elif errors:
            completeness = "PARTIAL"
        elif conflicts:
            completeness = "EVIDENCE_CONFLICT"
        elif "trace_reference" in missing or any(e.get("stage") == "lineage" for e in values["collection_errors"]):
            completeness = "TRACE_INCOMPLETE"
        elif missing:
            completeness = "STRUCTURALLY_PARTIAL"
        elif not data.get("required_evidence_fields"):
            completeness = "PARTIAL"
        else:
            completeness = "COMPLETE"
        if values.get("objective_id") or values.get("attempt_id"):
            productivity_required = ["objective_id", "attempt_id", "objective_validation_reference",
                "objective_completion_evidence", "elapsed_time", "resource_usage"]
            unavailable = [key for key in productivity_required if values.get(key) is None or values.get(key) == "" or values.get(key) == []]
            if unavailable:
                values["productivity_evidence_status"] = "PARTIAL"
                values["missing_fields"] = sorted(set(values["missing_fields"] + unavailable))
                if completeness == "COMPLETE": completeness = "PRODUCTIVITY_PARTIAL"
            else:
                # Complete measurement evidence is not a positive outcome judgment.
                values.setdefault("productivity_evidence_status", "COMPLETE")
        values["evidence_completeness"] = completeness
        if conflicts:
            values["metadata"]["conflicting_fields"] = conflicts
            for key in conflicts: values["field_availability"][key] = "CONFLICT"
        try:
            if classification is None:
                raise classification_failure
            if values["collection_errors"]:
                classification.observation_types = [x for x in classification.observation_types if x != RuntimeObservationType.NORMAL_EXECUTION]
                classification.observation_types.append(RuntimeObservationType.EVIDENCE_MISSING)
            values.update(observation_types=classification.observation_types,
                challenge_detected=classification.challenge_detected,
                correction_detected=classification.correction_detected,
                unexpected_behavior=classification.unexpected_behavior)
            values["metadata"]["classification_reasons"] = classification.reasons
        except Exception as exc:
            values["collection_errors"].append({"stage": "classification", "error": type(exc).__name__, "detail": str(exc), "retryable": True})
            values["evidence_completeness"] = "PARTIAL"
            values["observation_types"] = [RuntimeObservationType.EVIDENCE_MISSING]
            if runtime_error or runtime_state_end in {"ERROR", "FAIL", "FAILED", "HALTED"}:
                values["observation_types"].append(RuntimeObservationType.EXECUTION_FAILURE)
        for key in ("evidence_completeness", "missing_fields", "collection_errors", "field_sources",
                    "required_evidence_fields", "observation_types", "metadata", "observation_id", "observation_version",
                    "challenge_detected", "correction_detected", "unexpected_behavior", "orchestration_plan_id",
                    "productivity_evidence_status"):
            if key in values:
                values["field_availability"][key] = "CAPTURED" if values[key] is not None else "UNAVAILABLE"
        values["field_availability"].update(created_at="CAPTURED", updated_at="CAPTURED", field_availability="CAPTURED")
        record = RuntimeObservationRecord(**{k: v for k, v in values.items() if k in CANONICAL_FIELDS})
        if save:
            try:
                self.store.save_record(record)
            except Exception as exc:
                record.collection_errors.append({"stage": "persistence", "error": type(exc).__name__, "detail": str(exc), "retryable": True})
                record.evidence_completeness = "COLLECTION_FAILED"
                record.observation_types = [x for x in record.observation_types if x != RuntimeObservationType.NORMAL_EXECUTION]
                record.observation_types.append(RuntimeObservationType.EVIDENCE_MISSING)
        return record


def observe_builder_execution(function):
    """Finalize Builder success only after its Observation is retrievable.

    A missing operator identity stays explicitly unattributed, in artifact-local
    storage. Receipt status remains a claim; individual validation reports retain
    their original scope. No receipt is promoted to a Reality confirmation.
    """
    from functools import wraps
    @wraps(function)
    def observed(handoff_payload, artifact_root, *args, **kwargs):
        import time
        import logging
        from pathlib import Path
        started = time.monotonic()
        output = None
        failure = None
        attempt = generate_observation_id()
        try:
            output = function(handoff_payload, artifact_root, *args, **kwargs)
        except Exception as exc:
            failure = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            try:
                raw = handoff_payload if isinstance(handoff_payload, dict) else {}
                spec = raw.get("specification_object", {})
                if not isinstance(spec, dict): spec = {}
                status = output.validation_status if output else "FAILED"
                trace = output.receipt_path if output else f"builder-attempt:{attempt}"
                validations = output.validation_results if output else []
                commands = output.command_results if output else []
                receipt_data = {}
                if output:
                    import json
                    receipt_data = json.loads(Path(output.receipt_path).read_text(encoding="utf-8"))
                data = {
                    "runtime_component": "builder.core.build_entry", "affected_runtime_stage": "build_result",
                    "attempt_id": output.build_id if output else attempt,
                    "objective_id": output.spec_id if output else spec.get("spec_id"),
                    "objective_reference": spec.get("spec_id"),
                    "completion_claim": status, "observed_outcome": {"builder_returned": output is not None, "status": status},
                    "output_artifacts": output.files_written if output else [],
                    "produced_receipts": [output.receipt_path] if output else [],
                    "validation_results": validations,
                    "validation_references": output.evidence_references if output else [],
                    "completion_evidence": validations,
                    "mechanism_results": [{"source": "builder.command_executor", "results": commands},
                        {"source": "builder.validator", "results": validations}],
                    "runtime_decisions": list(receipt_data.get("stages_checked", [])),
                    "executed_components": ["builder.core.build_entry"],
                    "authority_source": "builder.handoff.authority_checker",
                    "authority_decision": "ALLOW" if "handoff_authority_validated" in receipt_data.get("stages_checked", []) else None,
                    "authority_decision_source": trace if receipt_data else None,
                    "authorization_receipts": [trace] if "handoff_authority_validated" in receipt_data.get("stages_checked", []) else [],
                    "mechanism_ids": ["builder.command_executor", "builder.validator"],
                    "elapsed_time": time.monotonic() - started,
                    "external_tool_call_count": len(commands),
                    "evidence_sources": ["builder.core.build_entry"],
                    "source_traces": [trace], "evidence_timestamps": [utc_now_iso()],
                    "correlation_id": output.build_id if output else attempt,
                    "required_evidence_fields": ["acting_identity", "validation_results", "observed_outcome"],
                    "unresolved_outcome_evidence": ([failure] if failure else []),
                    "handoff_records": [{"source": "specification", "receiver": "builder", "spec_id": spec.get("spec_id")}],
                    "metadata": {"authority_state_supplied": spec.get("authority_state")},
                }
                # A rejected root cannot acquire files through instrumentation.
                target = spec.get("execution", {}).get("repository_target", "")
                if not target or not Path(target).is_absolute() or Path(target).resolve() != Path(artifact_root).resolve():
                    raise ValueError("Observation output root lacks canonical target authority")
                from builder.core.build_entry import _metadata_path
                collector = RuntimeObservationCollector(store=RuntimeObservationStore(_metadata_path(artifact_root, '.observations')))
                record = collector.collect(operator_id="__unattributed__", thread_id="", runtime_state_end=status,
                    trace_reference=trace, runtime_error=failure, metadata=data)
                persisted = collector.store.load_record('__unattributed__', record.observation_id)
                from system_layer.contracts import digest
                if record.collection_errors or persisted is None or digest(persisted.to_dict()) != digest(record.to_dict()):
                    raise OSError('Builder Observation was not completely persisted and retrieved')
                if output is not None:
                    output = _finalize_observation_custody(output,
                        str(collector.store._record_path('__unattributed__', record.observation_id)))
            except Exception as exc:
                logging.getLogger(__name__).warning("Builder observation collection failed: %s: %s", type(exc).__name__, exc)
                if output is not None:
                    output = _finalize_observation_custody(output, None, type(exc).__name__)
        return output
    return observed


def _finalize_observation_custody(output, reference, error=None):
    """One canonical receipt; finalization failure raises, never returns PASS."""
    import json
    from pathlib import Path
    from dataclasses import replace
    from builder.core.build_models import BuildReceipt
    from builder.core.receipt_writer import write_build_receipt
    from builder.core.build_entry import _write_evidence_manifest, _metadata_path, _artifact_hashes
    receipt = BuildReceipt(**json.loads(Path(output.receipt_path).read_text(encoding='utf-8')))
    check = {'validation_type': 'observation_persistence', 'executed': True,
             'state': 'PASSED' if reference else 'FAILED',
             'reason': 'Persisted and retrieved exact Observation' if reference else 'Observation custody failed: '+str(error),
             'retry': 'Explicit new governed attempt; no automatic execution retry'}
    if reference: check['evidence_reference'] = reference
    refs = list(output.evidence_references)
    if reference and reference not in refs: refs.append(reference)
    checks = [*output.validation_results, check]
    status = output.validation_status if reference else 'FAIL'
    conditions = list(output.blocked_conditions)
    if not reference: conditions.append(check['reason'])
    # Refresh the canonical manifest, then verify the already validated artifacts.
    manifest = _metadata_path(output.artifact_root, '.builder_evidence/evidence_manifest.json')
    requirements = json.loads(manifest.read_text(encoding='utf-8')).get('validation_requirements', []) if manifest.exists() else []
    _write_evidence_manifest(artifact_root=output.artifact_root, actual_files=output.files_written,
        command_results=output.command_results, validation_results=checks,
        validation_status=status, validation_requirements=requirements)
    for integrity in output.validation_results:
        if integrity.get('validation_type') == 'final_artifact_integrity':
            expected = integrity.get('final_hashes', {})
            if _artifact_hashes(output.artifact_root, expected) != expected:
                status = 'FAIL'
                conditions.append('Artifact changed during Observation finalization')
    # A late integrity downgrade must also reach the canonical manifest.
    _write_evidence_manifest(artifact_root=output.artifact_root, actual_files=output.files_written,
        command_results=output.command_results, validation_results=checks,
        validation_status=status, validation_requirements=requirements)
    final = replace(receipt, final_status=status, validation_results=checks,
                    evidence_references=refs, blocked_conditions=conditions)
    write_build_receipt(final, output.receipt_path)
    from system_layer.contracts import digest
    if digest(json.loads(Path(output.receipt_path).read_text(encoding='utf-8'))) != digest(final.to_dict()):
        raise OSError('Final receipt retrieval mismatch')
    if status == 'PASS':
        for ref in refs:
            if not Path(ref).is_file():
                raise OSError('Final evidence target unavailable')
            with Path(ref).open('rb') as handle: handle.read(1)
        for integrity in output.validation_results:
            if integrity.get('validation_type') == 'final_artifact_integrity':
                for key in ('final_hashes','final_obligation_hashes'):
                    expected = integrity.get(key, {})
                    if _artifact_hashes(output.artifact_root, expected) != expected:
                        raise OSError('Artifact changed after final receipt persistence')
    return replace(output, validation_status=status, validation_results=checks,
                   evidence_references=refs, blocked_conditions=conditions)
