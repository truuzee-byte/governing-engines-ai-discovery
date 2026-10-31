from __future__ import annotations

import copy
from typing import Any, Dict

from specs.handoff_gate import approve_builder_handoff
from specs.spec_engine import create_specification_object, require_builder_specification, validate_specification_states
from specs.spec_snapshot import create_spec_snapshot


def mode_to_builder_handoff(mode_result: Any) -> Dict[str, Any]:
    manifest = getattr(mode_result, "interaction_manifest", None)
    if manifest is None:
        raise ValueError("missing interaction manifest")
    for name in ("halt_required", "clarification_required", "downstream_authority_allowed"):
        if type(getattr(manifest, name, None)) is not bool:
            raise ValueError(f"invalid or missing manifest.{name}")
    if manifest.halt_required:
        raise ValueError("mode halted; builder handoff blocked")
    if not manifest.downstream_authority_allowed:
        raise ValueError("downstream authority not allowed")
    if manifest.clarification_required:
        raise ValueError("clarification required; builder handoff blocked")
    if getattr(manifest, "selected_posture", None) in {"HALT", "CLARIFY_FIRST"}:
        raise ValueError("posture blocks builder handoff")

    interaction_id = _require_string(getattr(manifest, "interaction_id", None), "manifest.interaction_id")
    session_id = _require_string(getattr(manifest, "session_id", None), "manifest.session_id")
    trace_reference = _require_string(getattr(mode_result, "trace_reference", None), "mode_result.trace_reference")
    operator_intent = _require_string(getattr(mode_result, "raw_input", None), "mode_result.raw_input")

    # MODE may provide a richer BuildSpec directly. Prefer it and preserve it.
    supplied_spec = getattr(mode_result, "builder_specification", None)
    if supplied_spec is None:
        supplied_spec = getattr(mode_result, "specification_object", None)
    if supplied_spec is None:
        supplied_spec = getattr(mode_result, "build_spec", None)
    if supplied_spec is not None:
        if not isinstance(supplied_spec, dict):
            raise ValueError("mode_result.builder_specification must be a dictionary")
        specification_object = copy.deepcopy(supplied_spec)
    else:
        specification_object = _create_minimum_specification_object(
            interaction_id=interaction_id,
            operator_intent=operator_intent,
            mode_result=mode_result,
        )

    require_builder_specification(specification_object)
    payload = approve_builder_handoff(
        specification_object, create_spec_snapshot(specification_object),
    )
    payload.update({
        "specification_id": interaction_id,
        "operator_intent": operator_intent,
        "builder_target": "builder_runtime",
        "lineage": {
            "mode_session_id": session_id,
            "mode_interaction_id": interaction_id,
            "trace_reference": trace_reference,
        },
    })
    return payload
    


def _create_minimum_specification_object(*, interaction_id: str, operator_intent: str, mode_result: Any) -> Dict[str, Any]:
    states = getattr(mode_result, "builder_specification_states", None)
    names = {"authority_state", "validation_state", "readiness_state", "save_ready_state", "clarification_required"}
    if type(states) is not dict or set(states) != names:
        raise ValueError("Explicit builder_specification_states required; manifest permission is not specification approval")
    validate_specification_states(states)
    system_name = _derive_system_name(operator_intent)

    # Optional structured construction payload produced by MODE. This is the
    # bridge for tomorrow: MODE can supply real proposed files without this
    # adapter inventing canned implementation code.
    construction_payload = getattr(mode_result, "builder_files", None)
    if construction_payload is None:
        construction_payload = {}
    if not isinstance(construction_payload, dict):
        raise ValueError("mode_result.builder_files must be a dictionary")

    required_files = list(construction_payload.keys())
    repository_target = str(getattr(mode_result, "builder_repository_target", ""))
    approved_commands = getattr(mode_result, "builder_approved_commands", []) or []
    validation_commands = getattr(mode_result, "builder_validation_commands", []) or []

    return create_specification_object({
            **copy.deepcopy(states),
            "request_id": interaction_id,
            "system_name": system_name,
            "system_purpose": operator_intent,
            "tool_type": "construction_tool",
            "construction_scope": ["component"],
            "execution_authority": "operator_confirmed",
            "runtime_target": "builder_runtime",
            "source_trace_reference": _require_string(mode_result.trace_reference, "trace_reference"),
            "approved_components": [
                "repository_inspector",
                "code_constructor",
                "workspace_manager",
                "file_writer",
                "command_runner",
                "validator",
                "receipt_writer",
                "manifest_validator",
            ],
            "governance_constraints": [
                "component_must_be_registered",
                "approved_files_only",
                "approved_commands_only",
                "receipt_required",
                "manifest_validation_required",
                "spec_only",
            ],
            "receipt_requirements": ["build_receipt"],
        "artifact_structure": {
            "files": required_files,
            "directories": [],
            "approved_files": dict(construction_payload),
            "existing_files": [],
        },
        "execution": {
            "repository_target": repository_target,
            "authorized_read_scope": ["**/*"] if repository_target else [],
            "authorized_write_scope": required_files,
            "authorized_create_scope": required_files,
            "authorized_delete_scope": [],
            "approved_commands": [list(v) for v in approved_commands],
        },
        "validation": {
            "commands": [list(v) for v in validation_commands],
            "requirements": ["required_validation_must_execute"] if validation_commands else [],
        },
        "evidence": {
            "requirements": ["actual_files", "command_results", "build_receipt"],
        },
        "completion": {
            "requirements": ["required_files_exist", "manifest_valid", "validation_not_failed"],
        },
    })


def _derive_system_name(operator_intent: str) -> str:
    normalized = operator_intent.lower().strip()
    ignored = {"build", "create", "make", "a", "an", "the", "tool", "component", "python", "script"}
    words = []
    for raw_word in normalized.replace("-", " ").replace("_", " ").split():
        word = "".join(character for character in raw_word if character.isalnum())
        if word and word not in ignored:
            words.append(word)
    return "_".join(words[:5]) if words else "generated_component"


def _require_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"missing {field_name}")
    return value
