"""Real external RP coordinator, isolated synthetic authority; no providers."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace as NS
import pytest

from data_governance.material_admission import (MaterialProposal, MaterialAdmissionGate,
    required_scope, uncertainty_disclosure)
from integration.reality_primacy import RealityAcceptanceClient, digest
from system_layer.creation.service import SystemLayer


def proposal(**changes):
    scope = {'operator_id': 'operator', 'project_id': 'synthetic'}
    p = MaterialProposal('object:1', 'WorldState', 'claim:1',
        'The isolated fixture observed the required state.', 'OBJECT_STATE', scope,
        {'references': ['source-record:7'], 'version': 1},
        {'reference': 'authority:7', 'operator_id': 'operator', 'scope': scope},
        None, {'location': 'hall'}, 'ESTABLISHED', {'source_bound': True})
    return replace(p, **changes)


def external(tmp_path, p, observed=True, mutate_request=None):
    from test_evidence_validation import case, engine
    from test_decision_coordinator import authority
    from reality_primacy import (RPClaim, RPTruthCondition, resolve_evidence_requirements,
        DecisionCoordinator, DecisionLedger, TransitionEndpoint)
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    stamp = datetime.now(timezone.utc).isoformat()
    end = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    old, evidence = case()
    claim = deepcopy(old.claim_snapshot)
    claim.update(claim_id=p.claim_id, claim_text=p.claim_text, scope=required_scope(p),
        source_authority=p.authority, source_state=digest(p.prior_state),
        proposed_target_state=digest(p.candidate_state))
    condition = deepcopy(old.condition_snapshots[0])
    condition.update(claim_id=p.claim_id, scope=required_scope(p), condition_text=p.claim_text)
    resolution = resolve_evidence_requirements(RPClaim.from_dict(claim), [RPTruthCondition.from_dict(condition)])
    evidence.update(claim_id=p.claim_id, scope=required_scope(p),
        requirement_id=resolution.requirements[0]['requirement_id'], observed_at=stamp)
    evidence['content']['observed'] = observed
    evidence['content_hash'] = digest(evidence['content'])
    items = [] if observed is None else [evidence]
    batch = engine(resolution, items).validate(resolution, items, evaluated_at=stamp)
    policy = authority(resolution, batch)
    policy.update(valid_from=stamp, valid_until=end)
    coordinator = DecisionCoordinator(ledger=DecisionLedger(tmp_path / 'rp.sqlite'),
        issuer='external-rp', governed_authority_hashes=[digest(policy)],
        trusted_batch_hashes=[batch.content_hash()])
    key = Ed25519PrivateKey.from_private_bytes(b'7' * 32)
    endpoint = TransitionEndpoint(coordinator, key, key_id='synthetic', clock=lambda: stamp)
    client = RealityAcceptanceClient(endpoint.evaluate,
        {'synthetic': key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)})
    request = {'request_id': 'material-test:' + digest(p.binding()), 'claim_id': p.claim_id,
        'scope': required_scope(p), 'source_state': digest(p.prior_state),
        'target_state': digest(p.candidate_state), 'evaluated_at': stamp,
        'evaluation': {'resolution': resolution.to_dict(), 'batch': batch.to_dict(), 'authority': policy}}
    if mutate_request: mutate_request(request)
    return client, request


@pytest.mark.parametrize('observed,state,decision', [
    (True, 'CONFIRMED', 'APPLY'), (False, 'DISCONFIRMED', 'DENY'),
    (None, 'PENDING_VALIDATION', 'HOLD_PENDING_VALIDATION')])
def test_real_external_decision(tmp_path, observed, state, decision):
    p = proposal(); client, request = external(tmp_path, p, observed)
    result = MaterialAdmissionGate(client).evaluate(p, request)
    assert result['rp_state'] == state, result
    assert result['decision'] == decision, result
    assert result['external_receipt_id'] and result['external_chain_id']
    assert result['resulting_state'] == (p.candidate_state if observed is True else None)
    assert result['external_acceptance']['response']['body']['show_chain']['status'] == 'VERIFIED'


@pytest.mark.parametrize('state', ['INFERRED', 'PROPOSED', 'UNKNOWN', 'CONFLICTED'])
def test_supported_epistemic_status_is_not_promoted(tmp_path, state):
    p = proposal(epistemic_state=state); client, request = external(tmp_path, p)
    result = MaterialAdmissionGate(client).evaluate(p, request)
    assert result['rp_state'] == 'CONFIRMED'
    assert not result['accepted'] and result['resulting_state'] is None
    assert result['epistemic_state'] == state


@pytest.mark.parametrize('changes,reason', [
    ({'transition_class': 'UNRECOGNIZED'}, 'UNKNOWN_TRANSITION_CLASS'),
    ({'source': {}}, 'SOURCE_UNBOUND'), ({'authority': {}}, 'AUTHORITY_UNBOUND'),
    ({'preconditions': {}}, 'PRECONDITIONS_UNRESOLVED'),
    ({'preconditions': {'ready': 'PASS'}}, 'PRECONDITIONS_NOT_SATISFIED'),
    ({'preconditions': {'ready': False}}, 'PRECONDITIONS_NOT_SATISFIED')])
def test_fail_closed_contract(changes, reason):
    r = MaterialAdmissionGate().evaluate(proposal(**changes))
    assert r['decision'] == 'GOVERNANCE_BLOCK' and r['reason_code'] == reason
    assert r['rp_verdict'] is None and r['rp_state'] == 'PENDING_VALIDATION'


def test_missing_external_service_does_not_disconfirm():
    r = MaterialAdmissionGate().evaluate(proposal())
    assert not r['accepted'] and r['rp_verdict'] is None
    assert r['decision'] == 'HOLD_PENDING_VALIDATION'


def test_unknown_disclosure_is_not_unsupported_fact():
    assert uncertainty_disclosure({'epistemic_state': 'UNKNOWN', 'value': None})
    assert not uncertainty_disclosure({'epistemic_state': 'UNKNOWN', 'value': 'rain'})


@pytest.mark.parametrize('field,value', [
    ('claim_id', 'other'), ('source_state', 'other'), ('target_state', 'other'),
    ('scope', {'operator_id': 'other'})])
def test_request_substitution_blocked(tmp_path, field, value):
    p = proposal(); client, request = external(tmp_path, p)
    request[field] = value
    result = MaterialAdmissionGate(client).evaluate(p, request)
    assert result['decision'] == 'GOVERNANCE_BLOCK' and not result['accepted']
    assert not client._used  # Never asks RP to validate the wrong mutation.


def manager(tmp_path, client=None):
    outcomes = []
    runtime = NS(context=NS(identity=NS(operator_id='operator')), reality_acceptance_client=client,
        understanding_engine=NS(receive_rp_outcome=outcomes.append))
    return SystemLayer(tmp_path / 'system.sqlite', runtime), outcomes


def apply(manager, p, request=None, previous=None):
    payload = {'proposal': p.binding(), 'expected_receipt': previous}
    approval = {'operator_id': 'operator', 'action': 'MATERIAL_ADMISSION',
        'decision': 'APPROVE', 'hash': digest(payload)}
    return manager.admit_material(**payload, approval=approval, rp_request=request)


def test_apply_receipt_restart_and_stale_prior(tmp_path):
    p = proposal(); client, request = external(tmp_path, p)
    m, outcomes = manager(tmp_path, client)
    result = apply(m, p, request)
    assert result['applied'], result
    stored = m.store.get('operator', 'material:object:1')
    assert stored['value']['state'] == {'location': 'hall'}
    assert stored['value']['admission_receipt'] == result['admission']['receipt_id']
    assert outcomes[0]['rp_state'] == 'CONFIRMED'
    restarted, _ = manager(tmp_path)
    assert restarted.store.get('operator', 'material:object:1') == stored
    with pytest.raises(PermissionError, match='Stale'): apply(m, p, request)


def test_hold_retains_prior_and_audit_receipt(tmp_path):
    p = proposal(); client, request = external(tmp_path, p)
    m, _ = manager(tmp_path, client)
    old = apply(m, p, request)['object']
    q = proposal(claim_id='claim:2', prior_state=p.candidate_state, candidate_state={'location': 'garden'})
    result = apply(m, q, previous=old['receipt_id'])
    assert not result['applied'] and result['object'] == old
    assert result['admission']['value']['decision'] == 'HOLD_PENDING_VALIDATION'
    assert m.store.get('operator', 'material:object:1') == old


def test_direct_store_cannot_bypass_material_gate(tmp_path):
    m, _ = manager(tmp_path)
    with pytest.raises(PermissionError, match='requires external RP'):
        with m.store.transaction('operator') as (_, __, append):
            append('material:object:1', {'state': 'CONFIRMED'}, 'MATERIAL_STATE_APPLIED', {})
    assert not m.store.history('operator')


def test_unauthorized_write_cannot_call_external_rp(tmp_path):
    p = proposal(); client, request = external(tmp_path, p)
    m, _ = manager(tmp_path, client)
    with pytest.raises(PermissionError):
        m.admit_material(p.binding(), None, {}, request)
    assert not client._used and not m.store.history('operator')


def test_story_cannot_inject_upstream_rp_label():
    from understanding.story_contracts import StoryClaim
    from understanding.cinematic_models import Fact
    with pytest.raises(ValueError, match='RP verdict'):
        StoryClaim('c', 'IDENTITY', 'entrant', 'name', 'Mara', 'ESTABLISHED', ['s'], 'asserted', 'CONFIRMED')
    with pytest.raises(ValueError, match='RP verdict'):
        Fact('Mara', 'ESTABLISHED', ['s'], [], 'SUPPORTED', 'CONFIRMED')


def test_specification_cannot_promote_unknown_disposition():
    from tests.test_cinematic_infrastructure import story
    from understanding.cinematic_derivation import parse_story, derive_requirements, candidates
    from specs.cinematic_specification import generate, executor_handoff
    models, policies, _ = parse_story(story(), 'p')
    requirements = derive_requirements(models, policies)
    spec = generate(models, requirements, candidates(requirements[0], models['beats'][0]), [], 'understanding:1', {})
    path = next(p for p, value in spec.dispositions.items() if value == 'UNRESOLVED')
    spec.dispositions[path] = 'REQUIRED'
    with pytest.raises(PermissionError, match='promoted'):
        executor_handoff(spec, 'BUILDER', [])


def test_normal_system_command_retains_pending_receipt_and_observation(tmp_path):
    import json
    from system_layer.runtime import execute
    m, _ = manager(tmp_path)
    events = []
    m.runtime.system_layer = m
    m.runtime._observe_runtime_event = lambda name, payload, **kw: events.append((name, payload))
    p = proposal()
    payload = {'proposal': p.binding(), 'expected_receipt': None}
    payload['approval'] = {'operator_id': 'operator', 'action': 'MATERIAL_ADMISSION',
        'decision': 'APPROVE', 'hash': digest(payload)}
    result = execute(m.runtime, '/system admit_material ' + json.dumps(payload))
    assert not result['applied']
    assert events[-1][1]['result_state'] == 'HOLD_PENDING_VALIDATION'
    assert events[-1][1]['record_references'] == [result['admission']['receipt_id']]
    assert events[-2][1]['rp_receipt'] is None


def test_coverage_inventory_detects_unclassified_system_mutation():
    import ast
    from pathlib import Path
    from data_governance.material_coverage import coverage, SYSTEM_MUTATIONS, SYSTEM_READS, STATUS
    root = Path(__file__).resolve().parents[1]
    tree = ast.parse((root / 'system_layer/creation/service.py').read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'SystemLayer')
    public = {n.name for n in cls.body if isinstance(n, ast.FunctionDef) and not n.name.startswith('_')}
    assert public == set(SYSTEM_MUTATIONS) | set(SYSTEM_READS) | {'owner', 'require_internal_execution', 'admit_material'}
    rows = coverage()
    assert all(row['status'] in STATUS for row in rows)
    assert all((root / row['file']).is_file() for row in rows)
    # An inventory must not relabel legacy gaps as green merely because the
    # new material route exists alongside them.
    assert next(r for r in rows if r['entry_point'] == 'run_builder_core')['status'] == 'UNRESOLVED_GAP'
    assert next(r for r in rows if r['entry_point'] == 'SystemLayer.record_capability_evidence')['status'] == 'UNRESOLVED_GAP'
    read = next(r for r in rows if r['entry_point'] == 'SystemLayer.inspect_capabilities')
    assert read['status'] == 'NON_MATERIAL_EXEMPT' and not read['material_transition']


@pytest.mark.parametrize('predicate', ['ARRIVED', 'SHOT_VALID', 'CHARACTER_VISIBLE'])
def test_process_success_cannot_establish_artifact_semantics(predicate):
    from tests.test_cinematic_infrastructure import prepared
    from understanding.cinematic_validation import compare
    _, requirements, _ = prepared()
    requirements[0].required_evidence = [predicate]
    result = compare(requirements[0])
    assert result['comparison'] == 'UNRESOLVED'
    assert result['claim_state'] == 'PENDING_VALIDATION'
    assert not result['cinematic_success_proven']


def test_decision_tampering_and_replay_do_not_apply(tmp_path):
    p = proposal(); client, request = external(tmp_path, p)
    gate = MaterialAdmissionGate(client)
    accepted = gate.evaluate(p, request)
    assert accepted['accepted']
    accepted['proposed_state'] = {'location': 'elsewhere'}
    with pytest.raises(PermissionError, match='changed'): accepted.verify()
    replay = gate.evaluate(p, request)
    assert not replay['accepted'] and replay['decision'] == 'GOVERNANCE_BLOCK'
