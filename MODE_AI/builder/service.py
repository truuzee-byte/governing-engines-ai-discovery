"""Public construction boundary. Builder never receives a Mode runtime object.

The canonical approved handoff is the input contract; BuilderOutputObject is
construction evidence, not an accepted reality or System-state decision.
"""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace


class ConstructionBlocked(ValueError):
    """A valid plan lacks permission or a safe filesystem operation."""


def preflight(handoff, artifact_root):
    """Read-only authority/target check using the same enforcement as execution."""
    from builder.core.build_plan_generator import generate_build_plan
    from builder.core.build_entry import _validate_file_authority
    from builder.core.execution_contract import contained, validate_target, validate_operations
    from builder.handoff.specification_receiver import receive_specification
    from builder.handoff.snapshot_verifier import verify_snapshot_continuity
    from builder.kernel.cutover_preparation import prepare_cutover
    received = receive_specification(deepcopy(handoff))
    if not verify_snapshot_continuity(received):
        raise ValueError('Snapshot continuity failed')
    plan = generate_build_plan(handoff)
    validate_target(plan, artifact_root)
    operations = [SimpleNamespace(path=p, operation='MODIFY' if p in plan.existing_files else 'CREATE')
                  for p in plan.required_files]
    try:
        _validate_file_authority(operations, plan)
        validate_operations(operations, artifact_root)
    except ValueError as exc:
        raise ConstructionBlocked(str(exc)) from exc
    existing = {}
    for path in plan.existing_files:
        if path not in plan.authorized_read_scope or path not in plan.authorized_write_scope:
            raise ValueError('MODIFY requires explicit read and write authority')
        existing[path] = contained(Path(artifact_root).resolve(), path).read_text(encoding='utf-8')
    return {'contract': 'BuilderPreflight/1', 'spec_id': plan.spec_id,
            'snapshot_hash': plan.snapshot_hash, 'existing_files': existing,
            'kernel_cutover_preparation': prepare_cutover(plan)}


def execute(handoff, artifact_root, **dependencies):
    """Lazy loading lets unrelated Mode responsibilities survive unavailability."""
    from builder.core.build_entry import run_builder_core
    return run_builder_core(deepcopy(handoff), artifact_root, **dependencies)


def snapshot_evidence(output):
    """Retain exact per-attempt evidence before a later construction can replace it."""
    import hashlib
    import json
    root = Path(output['artifact_root']).resolve()
    snapshots = []
    for reference in dict.fromkeys([output['receipt_path'], *output['evidence_references']]):
        path = Path(reference).resolve()
        path.relative_to(root)
        raw = path.read_bytes()
        snapshots.append({'reference': reference, 'sha256': hashlib.sha256(raw).hexdigest(),
                          'content': json.loads(raw)})
    return snapshots
