"""Synthetic operator authority, real stores, Builder, and external RP contracts."""
from copy import deepcopy
from dataclasses import replace, fields
from datetime import datetime, timezone, timedelta
from pathlib import Path
from types import SimpleNamespace as NS
import hashlib
import sys
import pytest
from system_layer.contracts import Capability, SystemIdentity, QuickSpecification, PRINCIPLES, STAGES, IDENTITY_FIELDS, digest, now
from system_layer.service import SystemLayer
from system_layer.chain import analyze, build_obligations
from system_layer.reality import CapabilityRealityClient


def approval(owner, action, value):
    return {'operator_id': owner, 'action': action, 'decision': 'APPROVE', 'hash': digest(value)}


def capability():
    lists = {f.name: [] for f in fields(Capability) if f.type is list}
    return Capability(**lists, capability_id='calculator', name='calculator', category='tool',
        purpose='Add two numbers', description='Synthetic calculator capability', operator_id='operator',
        scope={'operator_id': 'operator', 'profile': 'INTERNAL', 'deployment': 'local'},
        builder_support={'contract': 'BuildRuntime'}, creation_support={'contract': 'SystemLayer/1'},
        version=1, supersedes=None)


def setup(tmp_path, runtime_profile='INTERNAL'):
    from tests.test_execution_spine import runtime
    runtime = runtime(tmp_path)
    manager = SystemLayer(tmp_path / 'system.sqlite', runtime)
    identity = {k: {'authority_reference': 'operator-fixture'} for k in
        ('name','system_type','version','creator','organization','purpose','construction_method','operational_boundaries')}
    for key, names in IDENTITY_FIELDS.items():
        identity[key].update({name: 'explicit synthetic fixture value' for name in names})
    method = tmp_path / 'construction-method.txt'
    method.write_text('Operator-approved synthetic construction method')
    identity['construction_method'].update(version='1', reference=str(method), sha256=hashlib.sha256(method.read_bytes()).hexdigest())
    identity['operational_boundaries'].update(runtime_profile=runtime_profile, mutable_roots=[str(tmp_path)], protected_paths=[str(tmp_path/'protected')])
    identity['governing_principles'] = list(PRINCIPLES)
    identity = SystemIdentity(**identity).to_dict()
    manager.identity(identity, approval('operator', 'SYSTEM_IDENTITY', identity))
    return manager


def declare(manager, cap=None):
    cap = cap or capability()
    quick = QuickSpecification(cap.name, cap.purpose, 'sum observed', ['local fixture'], 'local', 'normal', [])
    payload = {'capability': cap.to_dict(), 'quick_specification': quick.to_dict()}
    return manager.declare(**payload, approval=approval('operator', 'DECLARE', payload))


@pytest.mark.parametrize('entry', ['execute', 'route'])
def test_public_identity_blocks_ordinary_build_before_generation(tmp_path, entry):
    import json
    from tests.test_execution_spine import envelope
    manager = setup(tmp_path, runtime_profile='PUBLIC')
    manager.runtime.system_layer = manager
    request = envelope(tmp_path / 'artifact')
    builder = manager.runtime.build_runtime
    def forbidden(**kwargs):
        pytest.fail('Public runtime reached generation')
    builder.provider.agent.generate = forbidden
    result = builder.execute(request) if entry == 'execute' else builder.route('/build ' + json.dumps(request))
    assert result['state'] == 'SPECIFICATION_NOT_READY'
    assert any('Only internal runtime execution' in reason for reason in result['reasons'])
    assert not result['execution_attempted']
    assert not (tmp_path / 'artifact').exists()


def test_internal_identity_preserves_approved_ordinary_build(tmp_path):
    from tests.test_execution_spine import envelope
    manager = setup(tmp_path)
    manager.runtime.system_layer = manager
    result = manager.runtime.build_runtime.execute(envelope(tmp_path / 'artifact'))
    assert result['state'] == 'BUILD_PASS_RP_PENDING', result


def test_configured_system_layer_without_identity_cannot_execute(tmp_path):
    from tests.test_execution_spine import runtime
    r = runtime(tmp_path)
    r.system_layer = SystemLayer(tmp_path / 'system.sqlite', r)
    with pytest.raises(PermissionError, match='identity required'):
        r.build_runtime._execution_allowed()


def external(tmp_path, cap, observed=True, finding='OPERATIONAL', extra_scope=None, measurement=None):
    # Reuse the existing canonical RP regression fixtures, then supply exact new scope.
    from test_evidence_validation import case, engine
    from test_decision_coordinator import authority
    from reality_primacy import RPClaim, RPTruthCondition, resolve_evidence_requirements, DecisionCoordinator, DecisionLedger, TransitionEndpoint
    from reality_primacy.capability_audit import CapabilityAuditEndpoint
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    stamp = now()
    end = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    r, e = case()
    scope = {**cap.scope, 'capability_id': cap.capability_id, 'capability_version': cap.version, **(extra_scope or {})}
    c = deepcopy(r.claim_snapshot)
    c.update(scope=scope, source_state='DECLARED', proposed_target_state=finding)
    c['claim_text'] = 'Capability ' + cap.capability_id + ' satisfies the ' + scope.get('validation_dimension', finding.lower()) + ' condition in the exact declared scope.'
    if finding == 'NOT_IMPLEMENTED':
        c['claim_text'] = 'Required implementation is absent for capability ' + cap.capability_id
    c['source_specification'] = cap.declaration()
    condition = deepcopy(r.condition_snapshots[0]); condition['scope'] = scope
    condition['condition_text'] = c['claim_text']
    r = resolve_evidence_requirements(RPClaim.from_dict(c), [RPTruthCondition.from_dict(condition)])
    e.update(scope=scope, requirement_id=r.requirements[0]['requirement_id'], observed_at=stamp)
    e['content']['observed'] = observed
    if measurement is not None: e['content']['measurement'] = measurement
    e['content_hash'] = digest(e['content'])
    items = [] if observed is None else [e]
    batch = engine(r, items).validate(r, items, evaluated_at=stamp)
    policy = authority(r, batch); policy.update(valid_from=stamp, valid_until=end)
    coordinator = DecisionCoordinator(ledger=DecisionLedger(tmp_path / ('rp-' + digest(scope) + '.sqlite')),
        issuer='external-rp', governed_authority_hashes=[digest(policy)], trusted_batch_hashes=[batch.content_hash()])
    key = Ed25519PrivateKey.from_private_bytes(b'4'*32)
    endpoint = TransitionEndpoint(coordinator, key, key_id='system-test', clock=lambda: stamp)
    request = {'request_id': 'request:' + digest(scope), 'claim_id': r.claim_id, 'scope': scope,
        'source_state': 'DECLARED', 'target_state': finding, 'evaluated_at': stamp,
        'evaluation': {'resolution': r.to_dict(), 'batch': batch.to_dict(), 'authority': policy}}
    grant = {'claim_hash': digest(c), 'capability_hash': digest(cap.declaration()), 'scope': scope,
        'on_confirmed': finding, 'on_disconfirmed': 'DEGRADED', 'authority_reference': 'operator-fixture', 'valid_until': end}
    grant.update(expected_state='OPERATIONAL', halt_permitted=False, gap_details={
        **{k: [] for k in ('missing_evidence','missing_components','missing_dependencies','missing_chains',
            'missing_mechanisms','integration_defects','validation_defects','specification_requirements','authority_requirements')},
        'operational_consequence': 'Synthetic expected property unsupported', 'severity': 'LOW',
        'severity_basis': 'Isolated fixture has no external consumers', 'recommended_action': 'Operator review'})
    audit = CapabilityAuditEndpoint(endpoint, {r.claim_id: grant}, key, 'system-test')
    keys = {'system-test': key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)}
    return request, audit, keys


def test_declaration_does_not_assert_reality(tmp_path):
    manager = setup(tmp_path)
    result = declare(manager)
    assert result['value']['capability']['operational_state'] == 'UNCONFIRMED'
    assert len(result['value']['stages']) == 3
    assert result['receipt_id']


@pytest.mark.parametrize('state', ['OPERATIONAL','VALIDATED','IMPLEMENTED','INTEGRATED'])
def test_declaration_rejects_reality_injection(tmp_path, state):
    with pytest.raises(PermissionError):
        declare(setup(tmp_path), replace(capability(), operational_state=state))


@pytest.mark.parametrize('value', [True, False, None])
def test_external_findings_preserve_three_verdicts(tmp_path, value):
    manager = setup(tmp_path); declare(manager)
    request, endpoint, keys = external(tmp_path, capability(), value)
    manager.reality_client = CapabilityRealityClient(endpoint.evaluate, keys)
    result = manager.audit('calculator', request)
    expected = {True: 'CONFIRMED', False: 'DISCONFIRMED', None: 'PENDING_VALIDATION'}[value]
    assert result['value']['reality']['finding']['body']['rp_state'] == expected
    # Even confirmation alone is insufficient for registration.
    assert result['value']['capability']['operational_state'] != 'OPERATIONAL'


def test_modified_external_finding_rejected(tmp_path):
    request, endpoint, keys = external(tmp_path, capability(), False)
    def corrupt(request):
        result = endpoint.evaluate(request); result['body']['finding'] = 'OPERATIONAL'; return result
    with pytest.raises(PermissionError):
        CapabilityRealityClient(corrupt, keys).audit(capability(), request, 'audit-1')


def test_protected_identity_cannot_be_overwritten(tmp_path):
    manager = setup(tmp_path)
    value = manager.store.get('operator', 'identity')['value']
    with pytest.raises(PermissionError):
        manager.identity(value, approval('operator', 'SYSTEM_IDENTITY', value))


def test_quick_spec_cannot_build(tmp_path):
    manager = setup(tmp_path); receipt = declare(manager)
    with pytest.raises((PermissionError, KeyError)):
        manager.construct('calculator', receipt['receipt_id'], {})


def test_history_detects_tampering(tmp_path):
    import sqlite3
    manager = setup(tmp_path); declare(manager)
    with sqlite3.connect(manager.store.path) as db:
        db.execute("UPDATE events SET payload='{}' WHERE subject='calculator'")
    with pytest.raises(ValueError): manager.store.history('operator')


def test_unproven_required_chain(tmp_path):
    assert analyze(replace(capability(), required_chains=['EXECUTION']))['status'] == 'UNPROVEN'


@pytest.mark.parametrize('action', ['PAUSE', 'CANCEL', 'REJECT'])
def test_operator_control_is_receipted(tmp_path, action):
    manager = setup(tmp_path); receipt = declare(manager)
    body = {'capability_id': 'calculator', 'receipt_id': receipt['receipt_id'], 'action': action}
    changed = manager.control('calculator', action, receipt['receipt_id'], approval('operator', action, body))
    assert changed['value']['control'] == action
    assert changed['previous_receipt'] == receipt['receipt_id']


def test_runtime_command_uses_same_service(tmp_path):
    from system_layer.runtime import command
    manager = setup(tmp_path); manager.runtime.system_layer = manager
    receipt = declare(manager)
    assert command(manager.runtime, '/system show calculator') == receipt


def planned_capability():
    from understanding.system_relationship import SystemRelationship
    cap = capability()
    edge = SystemRelationship.create('operator', 'fixture', cap.capability_id, 'request', 'artifact',
        'PRODUCES', ['sum'], ['operator-fixture'], invariants=('file:calculator.py',),
        authority_requirements=('operator-fixture',), evidence_requirements=('command results',),
        failure_condition='Required artifact absent')
    cap = replace(cap, required_chains=['EXECUTION'], chain_relationships=[edge.to_dict()],
        required_outputs=['calculator.py'], required_evidence=['command results'],
        validation_requirements=['validation commands passed'], authority_requirements=['operator-fixture'])
    mechanisms = analyze(cap)['derivation']['mechanism_requirements']
    cap = replace(cap, mechanisms=[{**m, 'completion_requirements': ['file:calculator.py']} for m in mechanisms])
    assert analyze(cap)['status'] == 'STRUCTURALLY_DEFINED'
    return cap


def constructed(tmp_path, manager=None, cap=None, modify=False, commands=None):
    from tests.test_execution_spine import envelope, authorize
    manager = manager or setup(tmp_path); cap = cap or planned_capability(); declare(manager, cap)
    request, endpoint, keys = external(tmp_path, cap, False)
    manager.reality_client = CapabilityRealityClient(endpoint.evaluate, keys)
    audit = manager.audit(cap.capability_id, request)
    e = envelope(tmp_path/'artifact')
    if commands is not None: e['request']['execution']['approved_commands'] = commands
    e['request']['request_id'] = 'calculator-' + str(cap.version)
    if modify:
        paths = e['request']['artifact_structure']['files']
        e['request']['artifact_structure']['existing_files'] = list(paths)
        e['request']['execution'].update(authorized_create_scope=[], authorized_read_scope=list(paths), authorized_write_scope=list(paths))
    e['request']['evidence']['requirements'] += build_obligations(cap)
    authorize(e)
    specs = [{'reference': 'operator-fixture', 'sha256': 'b'*64}]
    search = {k: {'status': 'NOT_APPLICABLE', 'reason': 'Isolated synthetic capability environment',
                 'reference': 'fixture-inventory', 'matches': []} for k in
        ('aliases','unintegrated','builder_library','other_runtimes','approved_modules','conflicts')}
    payload = {'capability_receipt': audit['receipt_id'], 'envelope': e, 'governing_specs': specs, 'reuse_search': search}
    prepared = manager.prepare(cap.capability_id, e, specs, search, approval('operator','SPECIFICATION_APPROVAL',payload))
    payload = {'capability_receipt': prepared['receipt_id'], 'envelope_hash': digest(e)}
    result = manager.construct(cap.capability_id, prepared['receipt_id'], approval('operator','EXECUTION_APPROVAL',payload))
    assert result['value']['build_outcome']['build']['validation_status'] == 'PASS', result
    return manager, result


def validated(tmp_path, manager=None, cap=None, modify=False):
    manager, built = constructed(tmp_path, manager, cap, modify)
    return validate_existing(manager, built, tmp_path)


def validate_existing(manager, built, tmp_path, halt=False):
    cap = Capability(**built['value']['capability'])
    import subprocess
    root = tmp_path/'artifact'
    runtime_check = subprocess.run([sys.executable, '-B', 'main.py'], cwd=root, capture_output=True, text=True, timeout=10)
    functional_check = subprocess.run([sys.executable, '-B', '-c', 'from calculator import add; print(add(-2, 2))'],
        cwd=root, capture_output=True, text=True, timeout=10)
    independently_observed = {'runtime': runtime_check.returncode == 0 and runtime_check.stdout.strip() == '5',
        'functional': functional_check.returncode == 0 and functional_check.stdout.strip() == '0',
        'integration': functional_check.returncode == 0,
        'dependency': not cap.dependencies,
        'governance': [s['stage'] for s in built['value']['stages']] == list(STAGES[:STAGES.index('INTEGRATION')])}
    independently_observed['operational'] = all(independently_observed.values())
    measurement = {'runtime_stdout': runtime_check.stdout, 'runtime_returncode': runtime_check.returncode,
        'functional_stdout': functional_check.stdout, 'functional_returncode': functional_check.returncode,
        'source': 'independent test harness; generated artifact invoked in a separate process'}
    endpoints, requests = {}, {}
    for dimension in ('dependency','integration','functional','runtime','governance','operational'):
        scope = {'validation_dimension': dimension,
            'build_id': built['value']['build_outcome']['build']['build_id'],
            'artifact_hashes': built['value']['rollback_snapshot']['after']}
        request, endpoint, keys = external(tmp_path, cap, independently_observed[dimension], extra_scope=scope, measurement=measurement)
        if halt and dimension == 'governance':
            grant = endpoint._grants[request['claim_id']]
            grant.update(expected_state='VALIDATED', halt_permitted=True)
            grant['gap_details'].update(severity='HIGH', severity_basis='Synthetic governed halt requirement')
        requests[dimension] = request; endpoints[dimension] = endpoint
    manager.reality_client = CapabilityRealityClient(
        lambda request: endpoints[request['transition']['scope']['validation_dimension']].evaluate(request), keys)
    return manager, manager.validate('calculator', requests)


def test_complete_bounded_chain_and_rollback(tmp_path):
    manager, value = validated(tmp_path)
    assert value['value']['validation_complete']
    accepted = manager.accept('calculator', value['receipt_id'], approval('operator','OPERATOR_ACCEPTANCE',
        {'capability_receipt': value['receipt_id']}))
    assert accepted['value']['capability']['operational_state'] == 'OPERATIONAL'
    assert [s['stage'] for s in accepted['value']['stages']] == list(STAGES)
    restored = manager.rollback('calculator', accepted['receipt_id'], approval('operator','ROLLBACK',
        {'capability_receipt': accepted['receipt_id']}))
    assert not (tmp_path/'artifact/calculator.py').exists()
    assert restored['value']['capability']['operational_state'] == 'UNCONFIRMED'
    assert restored['previous_receipt']


def test_post_validation_mutation_blocks_registration(tmp_path):
    manager, value = validated(tmp_path)
    (tmp_path/'artifact/calculator.py').write_text('unapproved mutation')
    with pytest.raises(PermissionError, match='changed after validation'):
        manager.accept('calculator', value['receipt_id'], approval('operator','OPERATOR_ACCEPTANCE',
            {'capability_receipt': value['receipt_id']}))


def test_required_mechanisms_reach_builder_evidence(tmp_path):
    manager, built = constructed(tmp_path)
    results = built['value']['build_outcome']['build']['validation_results']
    assert any(r.get('obligation', {}).get('source') == 'SystemLayer/1:calculator' for r in results)


def test_external_capability_process_lifecycle(tmp_path):
    import json
    request, endpoint, keys = external(tmp_path, capability())
    config = {'grants': endpoint._grants,
        'authority_hashes': [digest(request['evaluation']['authority'])],
        'batch_hashes': [], 'execution_hashes': []}
    from reality_primacy.rp_evidence_validator import EvidenceBatch
    config['batch_hashes'] = [EvidenceBatch.from_dict(request['evaluation']['batch']).content_hash()]
    grant = tmp_path/'capability-grant.json'; grant.write_text(json.dumps(config))
    manager = setup(tmp_path); runtime = manager.runtime
    runtime.capability_rp_config = {'repository': r'C:\REALITY_PRIMACY', 'grant': str(grant),
                                    'ledger': str(tmp_path/'process-ledger.sqlite')}
    try:
        runtime._connect_capability_rp()
        assert getattr(runtime, 'capability_reality_client', None), getattr(runtime, 'capability_rp_error', None)
        outcome = runtime.capability_reality_client.audit(capability(), request, 'process-audit')
        assert outcome['finding']['body']['rp_state'] == 'CONFIRMED', outcome['acceptance']['reason']
        process = runtime._capability_rp_process
    finally:
        runtime.shutdown()
    assert process.process.poll() is not None
    assert not process.reader.is_alive()


def test_learning_event_requires_separate_exact_authorization(tmp_path):
    manager, result = validated(tmp_path)
    accepted = manager.accept('calculator', result['receipt_id'], approval('operator', 'OPERATOR_ACCEPTANCE',
        {'capability_receipt': result['receipt_id']}))
    event = {'change_id': 'system-change-1', 'changed_entities': [
        {'type': 'capability', 'id': 'calculator'}, {'type': 'capability', 'id': 'Add two numbers'}],
        'previous_state': 'DECLARED', 'new_state': 'OPERATIONAL',
        'scope': {'operator_id': 'operator', 'capability': 'Add two numbers'},
        'implementation_refs': [accepted['receipt_id']], 'evidence': accepted['references'],
        'timestamp': now(), 'dependency_references': []}
    bad = {**event, 'authority': {}}
    with pytest.raises(PermissionError): manager.learning_change('calculator', bad)
    event['authority'] = {'operator_id': 'operator', 'decision': 'APPROVE', 'change_hash': digest(event)}
    outcome = manager.learning_change('calculator', event)
    assert outcome['event'] == event
    assert outcome['automatic_replacement'] is False


def test_unknown_state_and_unknown_chain_rejected():
    with pytest.raises(ValueError): replace(capability(), rp_state='DEGRADED')
    with pytest.raises(ValueError): replace(capability(), operational_state='PASS')
    with pytest.raises(ValueError): analyze(replace(capability(), required_chains=['PLAUSIBLE_NEW_LAW']))


def test_contract_round_trip():
    import json
    cap = planned_capability()
    restored = Capability(**json.loads(json.dumps(cap.to_dict())))
    assert digest(restored.to_dict()) == digest(cap.to_dict())


def test_construction_method_mutation_blocks_identity(tmp_path):
    manager = setup(tmp_path)
    identity = manager.store.get('operator', 'identity')['value']
    Path(identity['construction_method']['reference']).write_text('altered')
    with pytest.raises(PermissionError): manager._verify_method(identity)


def test_independent_observation_is_not_automatic_validation(tmp_path):
    from reality_primacy.capability_audit import inspect_files
    (tmp_path/'present').write_text('real bytes')
    observed = inspect_files(tmp_path, ['present', 'absent'])
    assert [r['state'] for r in observed['observations']] == ['LOCATED', 'MISSING']
    assert observed['validation_state'] == 'NOT_VALIDATED'
    with pytest.raises(Exception): inspect_files(tmp_path, ['../outside'])


def test_identity_context_is_governed_and_not_execution_authority(tmp_path):
    from system_layer.runtime import prompt_context
    from data_governance.context_admission import verify
    manager = setup(tmp_path); manager.runtime.system_layer = manager
    prompt = prompt_context(manager.runtime)
    verify(prompt, 'thread')
    assert 'approved_system_identity' in prompt
    assert '"grants_execution_authority": false' in prompt
    assert prompt.decisions[0]['decision'] == 'ADMITTED'


def test_external_gap_preserves_evidence_and_uncertainty(tmp_path):
    for observed in (False, None):
        root = tmp_path/str(observed); root.mkdir()
        manager = setup(root); declare(manager)
        request, endpoint, keys = external(root, capability(), observed)
        manager.reality_client = CapabilityRealityClient(endpoint.evaluate, keys)
        result = manager.audit('calculator', request)['value']
        assert result['gap']['audit_evidence']['receipt_id']
        assert result['review_state'] == 'SYSTEM_LAYER_REVIEW_REQUIRED'
        assert result['gap']['completeness'] == ('COMPLETE' if observed is False else 'UNRESOLVED')


def test_capability_halt_requires_external_governing_authority(tmp_path):
    manager = setup(tmp_path); declare(manager)
    request, endpoint, keys = external(tmp_path, capability(), False)
    grant = endpoint._grants[request['claim_id']]
    grant['halt_permitted'] = True
    grant['gap_details'].update(severity='HIGH', severity_basis='Explicit synthetic critical dependency failure')
    manager.reality_client = CapabilityRealityClient(endpoint.evaluate, keys)
    result = manager.audit('calculator', request)
    assert result['value']['control'] == 'CAPABILITY_HALT'


def test_library_admission_cannot_precede_registration(tmp_path):
    manager = setup(tmp_path); declare(manager)
    with pytest.raises((ValueError, PermissionError)):
        manager.admit_library('calculator', {}, {})


def test_unapproved_learning_cannot_authorize_capability(tmp_path):
    manager = setup(tmp_path)
    with pytest.raises(PermissionError):
        manager.recommend('unknown-learning', {})


def test_prior_validated_state_can_be_restored_and_revalidated(tmp_path):
    import json
    from tests.test_execution_spine import CONTENTS
    manager, checked = validated(tmp_path)
    accepted = manager.accept('calculator', checked['receipt_id'], approval('operator', 'OPERATOR_ACCEPTANCE',
        {'capability_receipt': checked['receipt_id']}))
    class ChangedModel:
        def generate(self, **kwargs):
            path = json.loads(kwargs['user_input'])['target_path']
            return NS(final_response=json.dumps({'path': path, 'content': CONTENTS[path] + '\n# second capability version\n'}))
    manager.runtime.build_runtime.provider.agent = ChangedModel()
    cap = replace(planned_capability(), version=2, supersedes=accepted['receipt_id'])
    manager, checked = validated(tmp_path, manager, cap, True)
    second = manager.accept('calculator', checked['receipt_id'], approval('operator', 'OPERATOR_ACCEPTANCE',
        {'capability_receipt': checked['receipt_id']}))
    restored = manager.rollback('calculator', second['receipt_id'], approval('operator', 'ROLLBACK',
        {'capability_receipt': second['receipt_id']}))
    assert 'second capability version' not in (tmp_path/'artifact/calculator.py').read_text()
    assert restored['value']['capability']['version'] == 3
    assert restored['value']['capability']['operational_state'] == 'UNCONFIRMED'
    manager, checked = validate_existing(manager, restored, tmp_path)
    result = manager.accept('calculator', checked['receipt_id'], approval('operator', 'OPERATOR_ACCEPTANCE',
        {'capability_receipt': checked['receipt_id']}))
    assert result['value']['capability']['operational_state'] == 'OPERATIONAL'


def test_public_runtime_cannot_construct(tmp_path):
    manager = setup(tmp_path, 'PUBLIC'); declare(manager)
    with pytest.raises(PermissionError, match='internal'):
        manager.prepare('calculator', {}, [], {}, {})


def test_missing_dependency_blocks_readiness(tmp_path):
    assert not setup(tmp_path)._dependencies_current(replace(capability(), dependencies=['absent']))


def test_not_implemented_is_a_finding_not_a_fourth_verdict(tmp_path):
    manager = setup(tmp_path); declare(manager)
    request, endpoint, keys = external(tmp_path, capability(), True, 'NOT_IMPLEMENTED')
    manager.reality_client = CapabilityRealityClient(endpoint.evaluate, keys)
    value = manager.audit('calculator', request)['value']['capability']
    assert value['implementation_state'] == 'NOT_IMPLEMENTED'
    assert value['rp_state'] == 'CONFIRMED'
    assert value['operational_state'] != 'OPERATIONAL'


def test_library_update_has_distinct_operator_gate(tmp_path):
    manager, checked = validated(tmp_path)
    registered = manager.accept('calculator', checked['receipt_id'], approval('operator', 'OPERATOR_ACCEPTANCE',
        {'capability_receipt': checked['receipt_id']}))
    cap = registered['value']['capability']
    descriptor = {'identity': 'calculator', 'inputs': ['numbers'], 'outputs': ['sum'], 'supported_parameters': [],
        'execution_contract': 'local calculator function', 'dependencies': [], 'compatibility': 'Python',
        'validation': registered['references'], 'failure_behavior': 'invalid input raises', 'limitations': ['synthetic fixture'],
        'deployment_scope': cap['scope'], 'mutation_boundaries': registered['value']['envelope']['request']['execution'],
        'version': cap['version'], 'receipt_requirements': ['registration receipt']}
    with pytest.raises(PermissionError): manager.admit_library('calculator', descriptor, {})
    value = {'capability_receipt': registered['receipt_id'], 'descriptor': descriptor}
    receipt = manager.admit_library('calculator', descriptor, approval('operator', 'LIBRARY_UPDATE', value))
    assert receipt['action'] == 'LIBRARY_UPDATE'


@pytest.mark.parametrize('present,expected', [(False, 'PASSED'), (True, 'FAILED')])
def test_prohibited_outcomes_keep_negative_polarity(tmp_path, present, expected):
    from builder.core.execution_contract import check_success_requirements
    cap = replace(capability(), prohibited_behavior=['file:forbidden.txt'])
    if present: (tmp_path/'forbidden.txt').write_text('prohibited')
    plan = NS(required_files=[], required_directories=[], required_outputs=[], validation_requirements=[],
        evidence_requirements=build_obligations(cap), completion_requirements=[], governance_constraints=[], receipt_requirements=[])
    result = check_success_requirements(plan, tmp_path, [])
    assert result[0]['state'] == expected
    assert result[0]['obligation']['polarity'] == 'NEGATIVE'


@pytest.mark.parametrize('finding,field', [('IMPLEMENTED','implementation_state'),
    ('INTEGRATED','integration_state'), ('VALIDATED','validation_state')])
def test_partial_capability_evidence_does_not_promote_operational_state(tmp_path, finding, field):
    manager = setup(tmp_path); declare(manager)
    request, endpoint, keys = external(tmp_path, capability(), True, finding)
    manager.reality_client = CapabilityRealityClient(endpoint.evaluate, keys)
    cap = manager.audit('calculator', request)['value']['capability']
    assert cap[field] == finding
    assert cap['operational_state'] == 'UNCONFIRMED'


def test_external_validation_halt_blocks_registration(tmp_path):
    manager, built = constructed(tmp_path)
    manager, checked = validate_existing(manager, built, tmp_path, halt=True)
    assert checked['value']['control'] == 'CAPABILITY_HALT'
    assert checked['value']['validation_complete'] is False
    with pytest.raises(PermissionError):
        manager.accept('calculator', checked['receipt_id'], approval('operator', 'OPERATOR_ACCEPTANCE',
            {'capability_receipt': checked['receipt_id']}))


def test_command_mutation_requires_a_rollback_adapter(tmp_path):
    with pytest.raises(PermissionError, match='rollback adapter'):
        constructed(tmp_path, commands=[[sys.executable, '-c', 'raise SystemExit(99)']])
    assert not (tmp_path/'artifact').exists()


def test_disabled_target_cannot_be_silently_registered_operational(tmp_path):
    cap = replace(planned_capability(), declared_state='DISABLED')
    manager, built = constructed(tmp_path, cap=cap)
    manager, checked = validate_existing(manager, built, tmp_path)
    assert checked['value']['target_state'] == 'DISABLED'
    assert checked['value']['validation_complete'] is False
    with pytest.raises(PermissionError):
        manager.accept('calculator', checked['receipt_id'], approval('operator', 'OPERATOR_ACCEPTANCE',
            {'capability_receipt': checked['receipt_id']}))


def test_system_build_uses_normal_learning_capture(tmp_path):
    manager, built = constructed(tmp_path)
    candidate = manager.runtime.context.learning_candidate
    assert candidate['source_build_id'] == built['value']['build_outcome']['build']['build_id']
    assert candidate.get('status', candidate.get('candidate_status')) != 'APPROVED'


def test_system_observation_has_canonical_rp_and_receipt_links(tmp_path):
    manager, checked = validated(tmp_path)
    registered = manager.accept('calculator', checked['receipt_id'], approval('operator', 'OPERATOR_ACCEPTANCE',
        {'capability_receipt': checked['receipt_id']}))
    observation = manager.runtime.context.runtime_observation
    assert registered['receipt_id'] in observation.produced_receipts
    assert observation.validation_references
    assert observation.metadata['rp_request']['claim_id']
    assert observation.metadata['rp_receipt']
    assert observation.metadata['rp_receipt'] == checked['value']['validations']['operational']['acceptance']['receipt_id']
    manager.rollback('calculator', registered['receipt_id'], approval('operator', 'ROLLBACK',
        {'capability_receipt': registered['receipt_id']}))
    assert manager.runtime.context.runtime_observation.metadata['rp_result'] is None


def test_mechanism_identity_cannot_hide_removed_invariants():
    cap = planned_capability()
    mechanisms = deepcopy(cap.mechanisms)
    mechanisms[0]['invariant_protected'] = []
    assert analyze(replace(cap, mechanisms=mechanisms))['status'] == 'UNPROVEN'
