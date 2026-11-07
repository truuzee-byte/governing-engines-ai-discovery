"""Provisional, evidence-bound correction. Never writes a durable Learning record."""
from copy import deepcopy
from learning.contracts import digest


def analyze_attempt(*, specification, claim_binding, attempt, observation, authorization):
    """Only a completed failed command supports this bounded implementation tactic.

    This is a hypothesis to regenerate explicitly authorized implementation paths
    using the captured validator delta, not a claim that causation is established.
    """
    if observation.get('collection_errors'):
        raise PermissionError('Incomplete Observation cannot authorize correction')
    observed = observation.get('metadata', {}).get('observed_outcome', {})
    if (observed.get('attempt_id') != attempt['attempt_id'] or
            observed.get('build') != attempt['build']):
        raise PermissionError('Failure evidence does not describe this attempt')
    failures = [deepcopy(c) for c in attempt['build']['command_results']
                if type(c.get('returncode')) is int and c['returncode'] != 0]
    # Command executors use exit_code in their canonical records.
    if not failures:
        failures = [deepcopy(c) for c in attempt['build']['command_results']
                    if type(c.get('exit_code')) is int and c['exit_code'] != 0]
    if attempt['build']['validation_status'] != 'FAIL' or not failures:
        raise PermissionError('No completed failing test with actionable evidence')
    if (type(authorization) is not dict or set(authorization) != {'attempt_limit', 'adjustment', 'paths'}
            or authorization['attempt_limit'] != 2 or type(authorization['attempt_limit']) is not int
            or authorization['adjustment'] != 'implementation_tactic'):
        raise PermissionError('Explicit one-correction authority required')
    paths = authorization['paths']
    execution = specification['execution']
    existing = specification['artifact_structure']['existing_files']
    files = specification['artifact_structure']['files']
    if (type(paths) is not list or not paths or len(set(paths)) != len(paths)
            or any(type(p) is not str or p not in existing or p not in execution['authorized_write_scope']
                   or p not in execution['authorized_read_scope'] for p in paths)
            or set(existing) != set(files)):
        raise PermissionError('Correction requires existing MODIFY authority; CREATE is not upgraded')
    proof_arguments = [a for c in specification['validation']['commands'] for a in c]
    if any(p in proof_arguments for p in paths):
        raise PermissionError('Correction cannot replace a governing test artifact')
    return {'contract': 'CorrectiveRuntimeAnalysis/1', 'status': 'PROVISIONAL',
            'claim_binding': claim_binding, 'specification_hash': digest(specification),
            'attempt_id': attempt['attempt_id'], 'observation_id': observation['observation_id'],
            'observation_hash': digest(observation), 'failure_delta': failures,
            'hypothesis': 'The authorized implementation does not satisfy the recorded test; use its exact failure to revise only the approved implementation paths.',
            'causal_status': 'HYPOTHESIS_NOT_VALIDATED', 'authority': deepcopy(authorization),
            'adjustment': {'kind': 'implementation_tactic', 'paths': deepcopy(paths)},
            'proof_obligation': deepcopy(specification['validation']), 'durable': False}


def validate_adjustment(analysis, *, specification, claim_binding, authorization):
    if (analysis.get('contract') != 'CorrectiveRuntimeAnalysis/1'
            or analysis.get('claim_binding') != claim_binding
            or analysis.get('specification_hash') != digest(specification)
            or analysis.get('proof_obligation') != specification['validation']
            or analysis.get('authority') != authorization
            or analysis.get('adjustment') != {'kind': 'implementation_tactic', 'paths': authorization['paths']}
            or analysis.get('durable') is not False):
        raise PermissionError('Correction changed the claim, proof, specification or authority')
