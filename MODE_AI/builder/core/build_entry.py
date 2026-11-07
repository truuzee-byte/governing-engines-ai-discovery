from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from builder.components.component_loader import load_components
from builder.components.component_resolver import resolve_components
from builder.components.manifest_validator import validate_manifest_integrity
from builder.construction.code_constructor import (
    CodeGenerationProvider,
    ConstructionProviderRequired,
    construct_code,
)
from builder.core.artifact_recorder import create_build_manifest
from builder.core.build_models import BuilderOutputObject
from builder.core.build_plan_generator import generate_build_plan
from builder.core.build_validator import (
    evaluate_validation_results, validate_build_plan, validate_python_artifacts,
)
from builder.core.receipt_writer import create_build_receipt, write_build_receipt
from builder.handoff.authority_checker import check_builder_authority
from builder.handoff.snapshot_verifier import verify_snapshot_continuity
from builder.handoff.specification_receiver import receive_specification
from builder.kernel.kernel_client import BootstrapKernelClient, KernelClient, OperationBoundKernelClient


from runtime_observation.observation_collector import observe_builder_execution


@observe_builder_execution
def run_builder_core(
    handoff_payload: dict,
    artifact_root: str,
    *,
    code_generation_provider: CodeGenerationProvider | None = None,
    repository_context: Mapping[str, Any] | None = None,
    kernel_client: KernelClient | None = None,
    execution_guard=None,
    require_kernel: bool = False,
    stage_observer=None,
) -> BuilderOutputObject:
    """Execute the real Builder chain.

    Before the Trusted Execution Kernel exists, BootstrapKernelClient reuses the
    existing bounded Builder primitives. After Kernel acceptance, inject the real
    Kernel client and disable bootstrap use at the caller.
    """
    if not isinstance(artifact_root, str) or not artifact_root.strip():
        raise ValueError("artifact_root must not be empty")
    if type(require_kernel) is not bool:
        raise ValueError('Explicit Kernel requirement must be boolean')
    if require_kernel and not isinstance(kernel_client, OperationBoundKernelClient):
        raise PermissionError('Operation-bound Kernel required; bootstrap fallback prohibited')

    stages: list[str] = []
    blocked_conditions: list[str] = []
    evidence_refs: list[str] = []

    received = receive_specification(handoff_payload)
    stages.append("specification_received")

    if not check_builder_authority(received):
        raise ValueError("builder handoff authority denied")
    stages.append("handoff_authority_validated")

    if not verify_snapshot_continuity(received):
        raise ValueError("snapshot continuity failed")
    stages.append("snapshot_continuity_verified")
    if stage_observer is not None:
        stage_observer('BUILDING')

    build_plan = generate_build_plan(handoff_payload)
    if not validate_build_plan(build_plan):
        raise ValueError("invalid build_plan")
    stages.extend(["build_plan_generated", "build_plan_validated"])

    from builder.core.execution_contract import validate_target, validate_operations
    validate_target(build_plan, artifact_root)
    for path in build_plan.required_files + build_plan.required_directories + build_plan.required_outputs:
        if Path(path).parts[0].lower() in {'.builder_metadata', '.builder_evidence', '.observations'}:
            raise ValueError('Artifact overlaps Builder-owned metadata namespace')

    resolved = resolve_components(build_plan)
    load_components(resolved)
    stages.extend(["components_resolved", "components_loaded"])

    try:
        if execution_guard is not None:
            execution_guard()
        proposal = construct_code(
            build_plan,
            repository_context=repository_context or {},
            provider=code_generation_provider,
        )
    except ConstructionProviderRequired as exc:
        blocked_conditions.append(str(exc))
        stages.append("construction_provider_missing")
        return _finalize_blocked(
            build_plan=build_plan,
            artifact_root=artifact_root,
            stages=stages,
            blocked_conditions=blocked_conditions,
        )
    stages.append("construction_proposal_created")

    if proposal.boundary_state or proposal.unresolved_conditions:
        blocked_conditions.extend(proposal.unresolved_conditions)
        if proposal.boundary_state:
            blocked_conditions.append(proposal.boundary_state)
        return _finalize_blocked(
            build_plan=build_plan,
            artifact_root=artifact_root,
            stages=stages,
            blocked_conditions=blocked_conditions,
        )

    _validate_file_authority(proposal.files, build_plan)
    validate_operations(proposal.files, artifact_root)
    stages.append("file_authority_validated")

    proposed_files = proposal.approved_file_map()
    required_files = list(build_plan.required_files)
    if not required_files:
        required_files = list(proposed_files.keys())
    if set(proposed_files) != set(required_files):
        raise ValueError("construction proposal does not exactly match required_files")

    client = kernel_client if kernel_client is not None else BootstrapKernelClient(artifact_root=artifact_root)
    operations = {item.path: item.operation for item in proposal.files}
    if isinstance(client, OperationBoundKernelClient):
        client.bind(artifact_root, dict(operations), build_plan.snapshot_hash)
    elif not isinstance(client, BootstrapKernelClient):
        raise ValueError("Kernel must support operation-bound writes before execution")
    else:
        if Path(client.artifact_root).resolve() != Path(artifact_root).resolve():
            raise ValueError("Kernel root does not match authorized artifact root")
        client.operations = operations
    if execution_guard is not None:
        execution_guard()
    created_directories_abs = client.create_workspace(build_plan.required_directories)
    stages.append("workspace_created")

    written_abs = client.write_files(proposed_files, required_files)
    stages.append("files_written")

    actual_files = [_relative_to_root(path, artifact_root) for path in written_abs]
    actual_directories = [_relative_to_root(path, artifact_root) for path in created_directories_abs]
    materialization_results=[]
    from builder.core.execution_contract import contained
    for name,expected in proposed_files.items():
        check={'validation_type':'artifact_materialization','path':name,'executed':True,
               'comparison':'UTF8_UNIVERSAL_NEWLINE_TEXT',
               'proposed_text_sha256':hashlib.sha256(expected.encode('utf-8')).hexdigest()}
        try:
            target=contained(Path(artifact_root).resolve(),name)
            raw=target.read_bytes()
            observed=raw.decode('utf-8').replace('\r\n','\n').replace('\r','\n')
            check.update(observed_sha256=hashlib.sha256(raw).hexdigest(),
                state='PASSED' if observed==expected.replace('\r\n','\n').replace('\r','\n') else 'FAILED')
        except (OSError,ValueError,UnicodeError) as exc:
            check.update(state='FAILED',error_type=type(exc).__name__)
        materialization_results.append(check)
    materialized=all(check['state']=='PASSED' for check in materialization_results)

    command_requests = [list(item.argv) for item in proposal.commands]
    # Validation commands are requirements even when the constructor did not
    # independently request them.
    commands_to_run = _dedupe_commands(command_requests + build_plan.validation_commands)
    approved_commands = _dedupe_commands(build_plan.approved_commands + build_plan.validation_commands)
    command_results = []
    for command in commands_to_run:
        try:
            if not materialized:
                raise ValueError('Artifact materialization differs from approved proposal; command not executed')
            if execution_guard is not None:
                execution_guard()
            results=client.run_commands([command], approved_commands)
            if isinstance(client, OperationBoundKernelClient):
                if (type(results) is not list or len(results)!=1 or type(results[0]) is not dict
                        or results[0].get('command')!=command
                        or (results[0].get('returncode') is not None and type(results[0]['returncode']) is not int)):
                    raise ValueError('Kernel command result does not match the requested invocation')
            command_results.extend(results)
        except Exception as exc:
            # Preserve earlier results and still write a failure receipt for
            # launch errors, timeouts, or executor rejection.
            command_results.append({
                "command": list(command), "returncode": None,
                "error_type": type(exc).__name__, "error": str(exc),
            })
    stages.append("commands_executed" if commands_to_run else "no_commands_required")

    if stage_observer is not None:
        stage_observer('VALIDATING')
    validation_results = list(materialization_results)
    if isinstance(client, OperationBoundKernelClient):
        for result in command_results:
            references = result.get('evidence_references')
            proven = (result.get('retirement_state') == 'RESOURCE_RELEASE_CONFIRMED'
                      and type(references) is list and bool(references)
                      and all(type(ref) is str and bool(ref.strip()) for ref in references))
            validation_results.append({'validation_type':'kernel_execution_evidence',
                'command':result.get('command'), 'state':'PASSED' if proven else 'UNPROVEN',
                'evidence_references':result.get('evidence_references', []),
                'retirement_state':result.get('retirement_state','UNPROVEN')})
    for command in build_plan.validation_commands:
        matching = _find_command_result(command, command_results)
        if matching is None:
            validation_results.append({"command": list(command), "state": "NOT_EXECUTED"})
        elif matching.get("returncode") == 0:
            validation_results.append({**matching, "command": list(command), "state": "PASSED"})
        else:
            validation_results.append({**matching, "command": list(command), "state": "FAILED"})

    # Commands can modify generated files, so validate the final artifact bytes.
    validation_results.extend(validate_python_artifacts(artifact_root, required_files))
    from builder.core.execution_contract import check_success_requirements
    validation_results.extend(check_success_requirements(build_plan, artifact_root, command_results))
    stages.append("python_artifacts_checked")
    if not build_plan.validation_commands:
        validation_results.append({
            "validation_type": "required_validation", "state": "UNPROVEN",
            "executed": False, "requirements": list(build_plan.validation_requirements),
            "reason": "No executable validation commands declared.",
        })
    if not build_plan.validation_requirements:
        validation_results.append({"validation_type": "required_validation", "state": "UNPROVEN",
            "executed": False, "reason": "No explicit validation requirements declared."})

    build_manifest = create_build_manifest(
        build_plan=build_plan,
        artifact_root=artifact_root,
        actual_files=actual_files,
        actual_directories=actual_directories,
        command_results=command_results,
        validation_results=validation_results,
    )

    manifest_valid = validate_manifest_integrity(build_manifest)
    stages.append("manifest_validated" if manifest_valid else "manifest_failed")
    validation_results.append({
        "validation_type": "manifest_integrity", "executed": True,
        "state": "PASSED" if manifest_valid else ("UNPROVEN" if any(
            r.get("group") in {"required_files", "required_directories", "required_outputs"}
            and r["state"] == "UNPROVEN" for r in validation_results) else "FAILED"),
    })

    validation_status = evaluate_validation_results(build_plan, command_results, validation_results)

    integrity_paths = sorted(set(required_files + build_plan.required_outputs + build_plan.required_directories))
    validated_hashes = _artifact_hashes(artifact_root, integrity_paths)
    obligation_paths = sorted({r['requirement'][5:] for r in validation_results
        if isinstance(r.get('requirement'), str) and r['requirement'].startswith('file:')})
    obligation_hashes = _artifact_hashes(artifact_root, obligation_paths)

    evidence_path = _write_evidence_manifest(
        artifact_root=artifact_root,
        actual_files=actual_files,
        command_results=command_results,
        validation_results=validation_results,
        validation_status=validation_status,
        validation_requirements=build_plan.validation_requirements,
    )
    evidence_refs.append(evidence_path)
    stages.append("evidence_recorded")

    receipt_path = str(_metadata_path(artifact_root, '.builder_metadata/build_receipt.json'))
    receipt = create_build_receipt(
        intent_id=build_plan.spec_id,
        build_id=build_plan.build_id,
        snapshot_hash=build_plan.snapshot_hash,
        stages_checked=stages,
        drift_detected=False,
        final_status=validation_status,
        files_written=actual_files,
        directories_created=actual_directories,
        commands_executed=command_results,
        validation_results=validation_results,
        evidence_references=evidence_refs,
        blocked_conditions=blocked_conditions,
    )
    write_build_receipt(receipt, receipt_path)

    # A receipt-existence requirement is established only after the canonical
    # receipt has actually been persisted, not by promising to write it.
    deferred = [r for r in validation_results if r.get("requirement") == "receipt written"
                and not r.get('obligation', {}).get('unresolved')
                and r.get('obligation', {}).get('polarity', 'POSITIVE') == 'POSITIVE']
    if deferred:
        persisted = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
        for check in deferred:
            if persisted.get("build_id") == build_plan.build_id:
                check.update(state="PASSED", reason="Canonical receipt persisted", evidence_reference=receipt_path)
        validation_status = evaluate_validation_results(build_plan, command_results, validation_results)
        _write_evidence_manifest(artifact_root=artifact_root, actual_files=actual_files,
            command_results=command_results, validation_results=validation_results,
            validation_status=validation_status, validation_requirements=build_plan.validation_requirements)
        from dataclasses import replace
        receipt = replace(receipt, final_status=validation_status, validation_results=validation_results)
        write_build_receipt(receipt, receipt_path)

    # Metadata persistence must not change the bytes whose validation succeeded.
    final_hashes = _artifact_hashes(artifact_root, integrity_paths)
    integrity = {"validation_type": "final_artifact_integrity", "executed": True,
                 "validated_hashes": validated_hashes, "final_hashes": final_hashes,
                 "state": "FAILED" if final_hashes != validated_hashes else "PASSED" if all(final_hashes.values()) else "UNPROVEN"}
    integrity['validated_obligation_hashes'] = obligation_hashes
    integrity['final_obligation_hashes'] = _artifact_hashes(artifact_root, obligation_paths)
    if integrity['final_obligation_hashes'] != obligation_hashes:
        integrity.update(state='FAILED', reason='Obligation subject changed after validation')
    validation_results.append(integrity)
    validation_status = evaluate_validation_results(build_plan, command_results, validation_results)
    from dataclasses import replace
    receipt = replace(receipt, final_status=validation_status, validation_results=validation_results)
    _write_evidence_manifest(artifact_root=artifact_root, actual_files=actual_files,
        command_results=command_results, validation_results=validation_results,
        validation_status=validation_status, validation_requirements=build_plan.validation_requirements)
    # Observation custody is finalized by the wrapper. A crash before that point
    # must not leave a terminal PASS receipt on disk.
    write_build_receipt(replace(receipt, final_status='UNPROVEN') if validation_status == 'PASS' else receipt, receipt_path)
    # Include the final metadata flush in the boundary as well.
    if (_artifact_hashes(artifact_root, integrity_paths) != final_hashes or
            _artifact_hashes(artifact_root, obligation_paths) != obligation_hashes):
        integrity.update(state="FAILED", final_hashes=_artifact_hashes(artifact_root, integrity_paths))
        integrity['final_obligation_hashes'] = _artifact_hashes(artifact_root, obligation_paths)
        validation_status = "FAIL"
        write_build_receipt(replace(receipt, final_status="FAIL", validation_results=validation_results), receipt_path)
        _write_evidence_manifest(artifact_root=artifact_root, actual_files=actual_files,
            command_results=command_results, validation_results=validation_results,
            validation_status="FAIL", validation_requirements=build_plan.validation_requirements)

    return BuilderOutputObject(
        build_id=build_plan.build_id,
        spec_id=build_plan.spec_id,
        artifact_root=artifact_root,
        files_written=actual_files,
        directories_created=actual_directories,
        validation_status=validation_status,
        receipt_path=receipt_path,
        command_results=command_results,
        validation_results=validation_results,
        evidence_references=evidence_refs,
        blocked_conditions=blocked_conditions,
    )


def _finalize_blocked(*, build_plan, artifact_root: str, stages: list[str], blocked_conditions: list[str]) -> BuilderOutputObject:
    receipt_path = str(_metadata_path(artifact_root, '.builder_metadata/build_receipt.json'))
    receipt = create_build_receipt(
        intent_id=build_plan.spec_id,
        build_id=build_plan.build_id,
        snapshot_hash=build_plan.snapshot_hash,
        stages_checked=stages,
        drift_detected=False,
        final_status="BLOCKED",
        blocked_conditions=blocked_conditions,
    )
    write_build_receipt(receipt, receipt_path)
    return BuilderOutputObject(
        build_id=build_plan.build_id,
        spec_id=build_plan.spec_id,
        artifact_root=artifact_root,
        files_written=[],
        directories_created=[],
        validation_status="BLOCKED",
        receipt_path=receipt_path,
        blocked_conditions=blocked_conditions,
    )


def _relative_to_root(path: str, root: str) -> str:
    return str(Path(path).resolve().relative_to(Path(root).resolve())).replace("\\", "/")


def _artifact_hashes(root, paths):
    from builder.core.execution_contract import contained
    result = {}
    for path in paths:
        try:
            target = contained(Path(root).resolve(), path)
            result[path] = hashlib.sha256(target.read_bytes()).hexdigest() if target.is_file() else 'DIRECTORY' if target.is_dir() else None
        except (OSError, ValueError):
            result[path] = None
    return result


def _metadata_path(root, relative):
    root = Path(root).resolve()
    target = root / relative
    for parent in (target, *target.parents):
        if parent == root:
            break
        if parent.is_symlink() or (hasattr(parent, 'is_junction') and parent.is_junction()):
            raise ValueError('Builder metadata path must not redirect artifact writes')
    if not target.resolve().is_relative_to(root):
        raise ValueError('Builder metadata escapes artifact root')
    return target


def _dedupe_commands(commands: list[list[str]]) -> list[list[str]]:
    seen: set[tuple[str, ...]] = set()
    result: list[list[str]] = []
    for command in commands:
        signature = tuple(command)
        if signature not in seen:
            seen.add(signature)
            result.append(list(command))
    return result


def _find_command_result(command: list[str], results: list[dict]) -> dict | None:
    for result in results:
        if list(result.get("command", [])) == list(command):
            return result
    return None


def _write_evidence_manifest(*, artifact_root: str, actual_files: list[str], command_results: list[dict], validation_results: list[dict], validation_status: str, validation_requirements: list[str]) -> str:
    root = Path(artifact_root)
    evidence_dir = _metadata_path(root, '.builder_evidence')
    evidence_dir.mkdir(parents=True, exist_ok=True)

    file_hashes = {}
    for relative_path in actual_files:
        target = root / relative_path
        if target.is_file():
            file_hashes[relative_path] = hashlib.sha256(target.read_bytes()).hexdigest()

    payload = {
        "actual_files": actual_files,
        "file_hashes": file_hashes,
        "command_results": command_results,
        "validation_results": validation_results,
        "validation_status": validation_status,
        "validation_requirements": list(validation_requirements),
    }
    output = _metadata_path(root, '.builder_evidence/evidence_manifest.json')
    from uuid import uuid4
    temporary = output.with_name(output.name + '.' + uuid4().hex + '.tmp')
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(output)
    return str(output)


def _validate_file_authority(file_proposals: list, build_plan) -> None:
    create_scope = {str(path).replace("\\", "/") for path in build_plan.authorized_create_scope}
    write_scope = {str(path).replace("\\", "/") for path in build_plan.authorized_write_scope}
    required_files = {str(path).replace("\\", "/") for path in build_plan.required_files}

    for proposal in file_proposals:
        path = str(proposal.path).replace("\\", "/")
        if path not in required_files:
            raise ValueError("file proposal outside required_files")
        if proposal.operation == "CREATE" and path not in create_scope:
            raise ValueError(f"create authority denied for {path}")
        if proposal.operation == "MODIFY" and path not in write_scope:
            raise ValueError(f"write authority denied for {path}")
