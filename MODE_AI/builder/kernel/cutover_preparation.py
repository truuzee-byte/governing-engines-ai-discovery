"""Read-only compatibility preparation. Does not activate or implement a Kernel."""
from copy import deepcopy
from pathlib import Path
import hashlib
import json


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def prepare_cutover(build_plan):
    """Inventory the exact existing Builder boundary for later governed admission."""
    from builder.core.build_models import BuildPlan
    from builder.core.execution_contract import contained
    if not isinstance(build_plan, BuildPlan): raise TypeError('Canonical BuildPlan required')
    root = Path(build_plan.repository_target)
    if not root.is_absolute(): raise ValueError('Absolute governed repository target required')
    for path in [*build_plan.required_directories,*build_plan.required_outputs]:
        contained(root.resolve(), path)
    operations = {}
    for path in build_plan.required_files:
        contained(root.resolve(), path)
        operations[path] = 'MODIFY' if path in build_plan.existing_files else 'CREATE'
    value = {'contract':'BuilderKernelCutoverPreparation/1',
        'build_plan_hash':digest(build_plan.to_dict()), 'snapshot_hash':build_plan.snapshot_hash,
        'repository_target':str(root), 'operations':operations,
        'directories':deepcopy(build_plan.required_directories),
        'commands':deepcopy(build_plan.approved_commands),
        'validation_commands':deepcopy(build_plan.validation_commands),
        'required_outputs':deepcopy(build_plan.required_outputs),
        'binding_point':'run_builder_core(require_kernel=True, kernel_client=OperationBoundKernelClient)',
        'host_path':'BootstrapKernelClient -> builder.core command/file/workspace primitives',
        'required_proofs':['AUTHENTICATED_KERNEL','EXACT_OPERATION_BINDING','ADMITTED_ARTIFACT_TRANSFER',
            'OUTPUT_HASH_READBACK','EXECUTION_EVIDENCE','RESOURCE_RELEASE_CONFIRMED',
            'CHECKPOINT_QUALIFIED','EXPLICIT_ACTIVATION_AUTHORITY'],
        'unsupported_current_backend':['Builder file transfer and file/module command profile require deployed compatibility'],
        'boundary_ready_for_activation':False,
        'governing_blockers':['Current Kernel adapter explicitly excludes script/module/pytest launch policy',
            'Protected authenticated deployment and checkpoint qualification not established'],
        'activation':'BLOCKED','execution_authority':False,'execution_attempted':False,
        'state':'CUTOVER_PREPARED_AWAITING_OPERATOR_AUTHORITY'}
    value['preparation_hash'] = digest(value)
    return value
