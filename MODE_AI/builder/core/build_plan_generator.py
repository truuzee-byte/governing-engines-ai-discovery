from __future__ import annotations

from typing import Any

from builder.core.build_models import BuildPlan


def generate_build_plan(handoff_payload: dict) -> BuildPlan:
    if not isinstance(handoff_payload, dict):
        raise ValueError("invalid handoff payload")
    if handoff_payload.get("handoff_status") != "APPROVED":
        raise ValueError("handoff not approved")
    if handoff_payload.get("handoff_type") != "builder_execution":
        raise ValueError("handoff not approved")

    specification_object = handoff_payload.get("specification_object")
    snapshot = handoff_payload.get("snapshot")
    spec_hash = handoff_payload.get("spec_hash")
    if not isinstance(specification_object, dict):
        raise ValueError("missing specification_object")
    if not isinstance(snapshot, dict):
        raise ValueError("missing snapshot")
    if not _is_non_empty_string(spec_hash):
        raise ValueError("missing spec_hash")

    structure = specification_object.get("structure")
    artifact_structure = specification_object.get("artifact_structure")
    execution = specification_object.get("execution", {})
    validation = specification_object.get("validation", {})
    evidence = specification_object.get("evidence", {})
    completion = specification_object.get("completion", {})

    if not isinstance(structure, dict):
        raise ValueError("missing structure")
    
    if artifact_structure is None:
        raise ValueError("missing artifact_structure")

    if not isinstance(artifact_structure, dict):
        raise ValueError("invalid artifact_structure")
    
    if not isinstance(execution, dict) or not isinstance(validation, dict):
        raise ValueError("invalid execution or validation block")

    # These blocks are the executable contract, not extension bags. Reject
    # unrepresentable requirements rather than silently omitting them.
    blocks = {
        "artifact_structure": (artifact_structure, {"files", "directories", "approved_files", "existing_files", "required_outputs"}),
        "execution": (execution, {"repository_target", "authorized_read_scope", "authorized_write_scope", "authorized_create_scope", "authorized_delete_scope", "approved_commands"}),
        "validation": (validation, {"requirements", "commands"}),
        "evidence": (evidence, {"requirements"}),
        "completion": (completion, {"requirements"}),
    }
    for name, (block, supported) in blocks.items():
        if not isinstance(block, dict):
            raise ValueError(f"invalid {name} block")
        if block.keys() - supported:
            raise ValueError(f"unsupported {name} fields: {block.keys() - supported}")
        for field, value in block.items():
            if field == "repository_target":
                if not isinstance(value, str):
                    raise ValueError("invalid repository_target")
            elif field == "approved_files":
                if not isinstance(value, dict) or any(
                    not _is_non_empty_string(path) or not isinstance(content, str)
                    for path, content in value.items()
                ):
                    raise ValueError("invalid approved_files")
            elif field in {"approved_commands", "commands"}:
                if not isinstance(value, list):
                    raise ValueError(f"invalid {name}.{field}")
                for command in value:
                    if (not isinstance(command, list) or not command
                            or not _is_non_empty_string(command[0])
                            or any(not isinstance(arg, str) for arg in command)):
                        raise ValueError(f"invalid {name}.{field}")
            else:
                _require_string_list(value, f"{name}.{field}")
    for name in ("system_name", "tool_type"):
        if not _is_non_empty_string(structure.get(name)):
            raise ValueError(f"invalid or missing structure.{name}")
    for name in ("approved_components", "governance_constraints", "receipt_requirements"):
        _require_string_list(structure.get(name), f"structure.{name}")
    for name in ("files", "directories"):
        _require_string_list(artifact_structure.get(name), f"artifact_structure.{name}")

    required_files = artifact_structure.get("files", [])
    required_directories = artifact_structure.get("directories", [])
    approved_files = artifact_structure.get("approved_files", {})
    if not isinstance(required_files, list) or not isinstance(required_directories, list):
        raise ValueError("invalid artifact_structure")
    if not isinstance(approved_files, dict):
        raise ValueError("invalid approved_files")

    approved_commands = execution.get("approved_commands", [])
    validation_commands = validation.get("commands", [])

    from builder.core.understanding_obligations import obligation_requirements
    obligations = obligation_requirements(structure)
    return BuildPlan(
        build_id=f"build_{specification_object['spec_id']}",
        spec_id=specification_object["spec_id"],
        snapshot_hash=spec_hash,
        target_name=structure["system_name"],
        tool_type=structure["tool_type"],
        approved_components=list(structure.get("approved_components", [])),
        required_files=list(required_files),
        required_directories=list(required_directories),
        required_outputs=list(artifact_structure.get("required_outputs", [])),
        governance_constraints=list(structure.get("governance_constraints", [])),
        receipt_requirements=list(structure.get("receipt_requirements", [])),
        repository_target=execution.get("repository_target", ""),
        authorized_read_scope=list(execution.get("authorized_read_scope", [])),
        authorized_write_scope=list(execution.get("authorized_write_scope", [])),
        authorized_create_scope=list(execution.get("authorized_create_scope", [])),
        authorized_delete_scope=list(execution.get("authorized_delete_scope", [])),
        approved_commands=[list(v) for v in approved_commands],
        validation_commands=[list(v) for v in validation_commands],
        validation_requirements=list(validation.get("requirements", [])),
        evidence_requirements=list(evidence.get("requirements", [])) + obligations,
        completion_requirements=list(completion.get("requirements", [])),
        approved_files=dict(approved_files),
        existing_files=list(artifact_structure.get("existing_files", [])),
    )


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _require_string_list(value: Any, name: str) -> None:
    if not isinstance(value, list) or any(not _is_non_empty_string(item) for item in value):
        raise ValueError(f"invalid or missing {name}")
