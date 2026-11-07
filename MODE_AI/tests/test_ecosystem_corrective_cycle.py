"""Offline real-artifact pressure tests; model proposals are deterministic fixtures."""
import json
import sys
from copy import deepcopy
from types import SimpleNamespace as NS

import pytest
from test_execution_spine import runtime, envelope, authorize, CONTENTS
from integration.build_runtime import digest


def setup_cycle(tmp_path, *, final='pass'):
    root = tmp_path / 'artifact'
    root.mkdir()
    for path, content in CONTENTS.items():
        (root / path).write_text(content)
    r = runtime(tmp_path)
    e = envelope(root)
    e['request']['artifact_structure']['existing_files'] = list(CONTENTS)
    e['request']['execution']['authorized_read_scope'] = list(CONTENTS)
    e['request']['execution']['authorized_write_scope'] = list(CONTENTS)
    e['request']['execution']['authorized_create_scope'] = []
    authorize(e)
    e['authorization']['corrective'] = {'attempt_limit': 2, 'adjustment': 'implementation_tactic',
                                       'paths': ['calculator.py']}
    seen = []
    def generate(**kwargs):
        context = json.loads(kwargs['user_input'])
        seen.append(context)
        path = context['target_path']
        content = CONTENTS[path]
        if path == 'calculator.py' and ('provisional_corrective_analysis' not in context or final == 'fail'):
            content = 'def add(a, b):\n    return a - b\n'
        if final == 'unavailable' and 'provisional_corrective_analysis' in context:
            raise OSError('Synthetic generation unavailable')
        return NS(final_response=json.dumps({'path': path, 'content': content}))
    r.build_runtime.provider.agent.generate = generate
    return r, e, seen


def external(r, e, tmp_path):
    from reality_primacy.build_validation import BuildValidationSession
    from reality_primacy import DecisionLedger
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    from integration.reality_primacy import RealityAcceptanceClient
    key = Ed25519PrivateKey.generate()
    grant = {'operator_id': 'operator', 'thread_id': 'thread', 'request_hash': digest(e),
             'root': e['request']['execution']['repository_target'], 'claim_text': 'Calculator adds 2 and 3 to 5.',
             'required_files': list(CONTENTS), 'authority_reference': 'operator:qualification',
             'expected_observation': {'sum': 5}, 'verification_command': [sys.executable, '-B', '-c',
                 "from calculator import add; import json; print(json.dumps({'sum':add(2,3)}))"]}
    service = BuildValidationSession(grant=grant, ledger=DecisionLedger(tmp_path / 'rp.sqlite'), signing_key=key, key_id='test')
    r.prepare_build_reality_request = service.prepare
    r.reality_acceptance_client = RealityAcceptanceClient(service.evaluate,
        {'test': key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)})
    return service


@pytest.mark.parametrize('final,verdict', [('pass', 'CONFIRMED'), ('fail', 'DISCONFIRMED')])
def test_real_corrective_chain(tmp_path, final, verdict):
    r, e, seen = setup_cycle(tmp_path, final=final)
    external(r, e, tmp_path)
    out = r.build_runtime.execute(e)
    assert len(out['attempts']) == 2, out
    assert out['attempts'][0]['build']['validation_status'] == 'FAIL'
    assert out['rp']['rp_state'] == verdict, out.get('reasons')
    assert out['rp']['receipt_id'] and out['rp']['chain_id']
    assert len({a['claim_binding'] for a in out['attempts']}) == 1
    assert len({a['specification_hash'] for a in out['attempts']}) == 1
    correction = out['corrective_analysis']
    assert correction['durable'] is False
    assert 'AssertionError' in str(correction['failure_delta'])
    assert seen[-1]['provisional_corrective_analysis'] == correction
    assert out['attempts'][0]['evidence_snapshots'][0]['content']['final_status'] == 'FAIL'
    assert out['rp']['request']['claim_id'] == 'build-claim:' + out['claim_binding']


@pytest.mark.parametrize('kind', ['claim', 'proof', 'authority'])
def test_corrective_contract_cannot_change(tmp_path, kind):
    from learning.corrective import validate_adjustment
    r, e, _ = setup_cycle(tmp_path)
    out = r.build_runtime.execute(e)
    analysis = deepcopy(out['corrective_analysis'])
    if kind == 'claim': analysis['claim_binding'] = 'different'
    if kind == 'proof': analysis['proof_obligation'] = {'commands': [], 'requirements': []}
    if kind == 'authority': analysis['adjustment']['paths'] = ['outside.py']
    with pytest.raises(PermissionError):
        validate_adjustment(analysis, specification=out['specification'], claim_binding=out['claim_binding'],
                            authorization=e['authorization']['corrective'])


def test_missing_observation_cannot_enter_rp(tmp_path):
    r, e, _ = setup_cycle(tmp_path)
    service = external(r, e, tmp_path)
    out = r.build_runtime.execute(e)
    out['observation_evidence'] = []
    with pytest.raises(ValueError): service.prepare(out)


def test_test_artifact_cannot_be_corrected(tmp_path):
    r, e, _ = setup_cycle(tmp_path)
    e['authorization']['corrective']['paths'] = ['test_calculator.py']
    out = r.build_runtime.execute(e)
    assert len(out['attempts']) == 1
    assert 'test artifact' in out['corrective_blocked']


def test_builder_unavailable_does_not_break_chat(tmp_path, monkeypatch):
    import builder.service
    r = runtime(tmp_path)
    def unavailable(*args, **kwargs): raise ImportError('Builder unavailable')
    monkeypatch.setattr(builder.service, 'execute', unavailable)
    out = r.build_runtime.execute(envelope(tmp_path / 'artifact'))
    assert out['state'] == 'CONSTRUCTION_BLOCKED'
    assert r.handle_build_request('Explain addition') is None


def test_unexecuted_correction_is_pending_not_disconfirmed(tmp_path):
    r, e, _ = setup_cycle(tmp_path, final='unavailable')
    external(r, e, tmp_path)
    out = r.build_runtime.execute(e)
    assert len(out['attempts']) == 2
    assert out['attempts'][-1]['execution_status'] == 'NOT_COMPLETED'
    assert out['rp']['rp_state'] == 'PENDING_VALIDATION', out['reasons']
    assert out['rp']['accepted'] is False


def test_durable_eligibility_consumes_complete_attempt_chain(tmp_path):
    from learning.runtime import service
    r, e, _ = setup_cycle(tmp_path)
    external(r, e, tmp_path)
    out = r.handle_build_request('/build ' + json.dumps(e))
    assert out['rp']['rp_state'] == 'CONFIRMED'
    manager = service(r)
    candidate = manager.capture_build(r, out)
    chain = candidate['lineage']['canonical_v2']
    assert len(chain['outcome_analysis']['lineage']['attempt_chain']) == 2
    # A repaired artifact is not, by itself, a validated causal contrast.
    assert candidate['candidate_status'] == 'PENDING_VALIDATION'
    with pytest.raises(PermissionError):
        manager.review('operator', candidate['candidate_id'], digest(candidate), 'APPROVE')


def test_no_mutable_runtime_object_crosses_builder_boundary(tmp_path):
    from builder.service import execute
    r = runtime(tmp_path)
    def adversarial(handoff, root, **kwargs):
        assert 'runtime' not in kwargs and 'context' not in kwargs
        with pytest.raises(ValueError): kwargs['stage_observer']('COMPLETE')
        return execute(handoff, root, **kwargs)
    r.build_runtime.builder = adversarial
    out = r.build_runtime.execute(envelope(tmp_path / 'artifact'))
    assert out['state'] == 'BUILD_PASS_RP_PENDING'


def test_approved_learning_reaches_future_governed_generation(tmp_path):
    from tests.test_learning import built, approve
    from learning.runtime import command
    r, previous, candidate = built(tmp_path)
    record = approve(r, candidate)
    command(r, '/learning use_for_build ' + json.dumps(candidate['scope']))
    e = envelope(tmp_path / 'artifact')
    e['request']['request_id'] = 'next-governed-build'
    e['request']['artifact_structure']['existing_files'] = list(CONTENTS)
    e['request']['execution']['authorized_read_scope'] = list(CONTENTS)
    e['request']['execution']['authorized_write_scope'] = list(CONTENTS)
    e['request']['execution']['authorized_create_scope'] = []
    authorize(e)
    seen = []
    def generate(**kwargs):
        text = str(kwargs['user_input'])
        spec, end = json.JSONDecoder().raw_decode(text)
        assert record['learning_id'] in text[end:]
        assert any(d['artifact_type'] == 'LEARNING' and d['decision'] == 'ADMITTED'
                   for d in kwargs['user_input'].decisions)
        seen.append(record['learning_id'])
        return NS(final_response=json.dumps({'path': spec['target_path'], 'content': CONTENTS[spec['target_path']]}))
    r.build_runtime.provider.agent.generate = generate
    r.prepare_build_reality_request = None
    out = r.handle_build_request('/build ' + json.dumps(e))
    assert out['state'] == 'BUILD_PASS_RP_PENDING', out['reasons']
    assert seen == [record['learning_id']] * len(CONTENTS)
