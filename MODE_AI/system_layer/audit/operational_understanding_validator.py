"""Assess operational-model completeness without issuing an RP verdict.

System v1.2 §§8A,15,16,36 and Creative v1.2 §§43–53. Knowing a
procedure is distinct from access, authorization, execution and validation.
"""
from ..contracts import digest
from .structural_inventory_auditor import freshness

FIELDS = ('capability_id', 'system_version', 'purpose', 'inputs', 'outputs',
          'dependencies', 'tools', 'runtime_environment', 'access_requirements',
          'authority_requirements', 'implementation_state', 'operational_state',
          'limitations', 'failure_modes', 'evidence_references', 'validation_mechanism',
          'observation_mechanism', 'capability_status', 'starting_state',
          'operation_sequence', 'intermediate_states', 'persistent_side_effects',
          'stop_conditions', 'recovery_boundaries', 'revalidation_conditions')

LIST_FIELDS = {'inputs','outputs','dependencies','tools','access_requirements',
               'authority_requirements','limitations','failure_modes','evidence_references',
               'operation_sequence','intermediate_states','persistent_side_effects',
               'stop_conditions','recovery_boundaries','revalidation_conditions'}


def evaluate(model, inventory, *, current_system_version):
    if type(model) is not dict or type(model.get('definition')) is not dict:
        raise ValueError('Operational understanding definition required')
    if set(model) != {'schema_version', 'version', 'supersedes', 'definition', 'inventory_hash', 'model_hash'}:
        raise ValueError('Unknown or missing operational understanding fields')
    if model['schema_version'] != 'OperationalUnderstanding/1.2' or type(model['version']) is not int or model['version'] < 1:
        raise ValueError('Unsupported operational model version')
    if model['version'] > 1 and not model['supersedes']:
        raise ValueError('Operational model history required')
    if model['model_hash'] != digest({k: v for k, v in model.items() if k != 'model_hash'}):
        raise ValueError('Operational model integrity mismatch')
    data = model['definition']
    if set(data) - set(FIELDS):
        raise ValueError('Unknown operational definition fields')
    for key, value in data.items():
        if value is None:
            continue  # explicitly unresolved, never an inferred default
        if key in LIST_FIELDS:
            if type(value) is not list or any(type(v) is not str or not v.strip() for v in value):
                raise ValueError('Explicit string list required: ' + key)
        elif type(value) is not str:
            raise ValueError('Explicit text required: ' + key)
    unresolved = [key for key in FIELDS if key not in data or data[key] is None or (type(data[key]) is str and not data[key].strip())]
    for key in ('operation_sequence', 'validation_mechanism', 'observation_mechanism', 'evidence_references'):
        if not data.get(key) and key not in unresolved:
            unresolved.append(key)
    reasons = ['UNRESOLVED:' + key for key in unresolved]
    if data.get('system_version') != current_system_version:
        reasons.append('SYSTEM_VERSION_CHANGED')
    if inventory is None:
        reasons.append('STRUCTURAL_INVENTORY_REQUIRED_OR_UNAVAILABILITY_MUST_BE_RECORDED')
    else:
        state = freshness(inventory)
        if model['inventory_hash'] != inventory['inventory_hash']:
            reasons.append('INVENTORY_BINDING_MISMATCH')
        if data.get('capability_id') != inventory['system_id'] or current_system_version != inventory['system_version']:
            reasons.append('INVENTORY_SYSTEM_MISMATCH')
        if state['state'] != 'CURRENT_FOR_SELECTION':
            reasons.append('STRUCTURAL_REVALIDATION_REQUIRED')
    return {'state': 'REVIEW_REQUIRED' if reasons else 'STRUCTURALLY_GROUNDED_MODEL',
            'reasons': reasons, 'model_hash': model['model_hash'],
            'runtime_operability': 'UNPROVEN', 'access': 'NOT_ESTABLISHED',
            'execution_authority': 'NONE', 'rp_verdict': 'NOT_REQUESTED'}
