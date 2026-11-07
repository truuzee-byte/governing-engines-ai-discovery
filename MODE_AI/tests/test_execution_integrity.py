import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from tests.test_execution_spine import envelope, authorize, runtime, Model, CONTENTS, digest
from builder.tests.test_builder_entry import _valid_handoff_payload
from builder.core.build_entry import run_builder_core


def test_receipt_cannot_overwrite_artifact(tmp_path):
    contents = '{"approved": true}'
    output = run_builder_core(_valid_handoff_payload(root=tmp_path,
        files={'build_receipt.json': contents}, requirements=['approved file contents match'],
        commands=[[sys.executable, '-B', '-c', 'pass']]), str(tmp_path))
    assert output.validation_status == 'PASS'
    assert (tmp_path / 'build_receipt.json').read_text() == contents
    check = next(c for c in output.validation_results if c.get('validation_type') == 'final_artifact_integrity')
    assert check['validated_hashes'] == check['final_hashes']
    assert output.receipt_path != str(tmp_path / 'build_receipt.json')


def test_post_validation_mutation_fails(tmp_path, monkeypatch):
    import builder.core.build_entry as entry
    original = entry.write_build_receipt
    def mutate(receipt, path):
        result = original(receipt, path)
        (tmp_path / 'reports/result.txt').write_text('changed after validation')
        return result
    monkeypatch.setattr(entry, 'write_build_receipt', mutate)
    output = run_builder_core(_valid_handoff_payload(root=tmp_path), str(tmp_path))
    assert output.validation_status == 'FAIL'
    assert json.loads(Path(output.receipt_path).read_text())['final_status'] == 'FAIL'


@pytest.mark.parametrize('field', ['requirements', 'completion_conditions', 'evidence_requirements', 'authority_requirements'])
def test_obligations_cannot_hide_in_metadata(tmp_path, field):
    e = envelope(tmp_path / 'artifact')
    e['understanding'][field] = ([{'requirement_id':'missing', 'text':'unimplemented obligation'}]
        if field == 'requirements' else ['unimplemented obligation'])
    if field == 'requirements':
        e['understanding']['relationships'][0]['requirement_ids'] = ['missing']
    out = runtime(tmp_path).build_runtime.execute(authorize(e))
    assert out['state'] == 'BUILD_UNPROVEN', out
    assert any(c.get('obligation') and c['state'] == 'UNPROVEN' for c in out['build']['validation_results'])


def test_obligation_identity_reaches_enforcement(tmp_path):
    out = runtime(tmp_path).build_runtime.execute(envelope(tmp_path / 'artifact'))
    checks = [c for c in out['build']['validation_results'] if c.get('obligation', {}).get('id') == 'add']
    assert len(checks) == 1 and checks[0]['state'] == 'PASSED'
    assert checks[0]['obligation']['original']['source_references']


def test_unsupported_governance_blocks_pass(tmp_path):
    e = envelope(tmp_path/'artifact')
    e['request']['governance_constraints'] = ['unproved constraint']
    out = runtime(tmp_path).build_runtime.execute(authorize(e))
    assert out['state'] == 'BUILD_UNPROVEN'


@pytest.mark.parametrize('kind,expected', [('failure','EXECUTION_FAILURE'), ('unproven','EVIDENCE_MISSING'), ('pending','EVIDENCE_MISSING'), ('denied','EVIDENCE_MISSING')])
def test_attempt_observations(tmp_path, kind, expected):
    r = runtime(tmp_path); e = envelope(tmp_path / 'artifact')
    if kind == 'failure': e['request']['validation']['commands'] = [[sys.executable, '-B', '-c', 'exit(2)']]
    if kind == 'unproven': e['request']['completion']['requirements'].append('unsupported')
    authorize(e)
    if kind == 'denied': e['authorization']['decision'] = 'DENY'
    out = r.build_runtime.execute(e)
    record = r.runtime_observation_collector.store.load_record('operator', out['observation_ids'][-1])
    assert expected in [t.value for t in record.observation_types]
    assert record.interaction_id and record.correlation_id
    assert record.observed_outcome['state'] == out['state']


@pytest.mark.parametrize('outcome', ['CONFIRMED', 'DISCONFIRMED', 'PENDING_VALIDATION', 'STALE', 'UNAVAILABLE', 'PROHIBITED', 'UNRESOLVED'])
def test_booted_runtime(tmp_path, monkeypatch, outcome):
    from interactive_mode_ai import ModeRuntime, RuntimeState
    from mode_operator.operator_identity import OperatorIdentity
    from mode_operator.operator_store import OperatorStore
    from memory.thread_store import ThreadStore
    monkeypatch.chdir(tmp_path)
    store = OperatorStore(str(tmp_path/'operators'))
    identity = OperatorIdentity.create('operator')
    profile = store.create_profile(identity)
    profile.update_operator_managed_info(preferred_name='Operator', timezone='UTC', language='English')
    threads = ThreadStore(str(tmp_path/'threads'))
    thread = threads.create_thread('operator')
    profile.active_thread_id = thread.thread_id
    store.save_profile(identity, profile)
    e = envelope(tmp_path/'artifact')
    if outcome == 'PROHIBITED':
        e['understanding']['requirements'][0]['prohibited_states'] = ['file:calculator.py']
    if outcome == 'UNRESOLVED':
        e['understanding']['completion_conditions'] = [{'kind':'PREFERENCE','text':'file:absent.txt'}]
    e['authorization']['thread_id'] = thread.thread_id
    authorize(e)
    verifier = "from calculator import add; import json; print(json.dumps({'sum':add(2,3)}))"
    if outcome == 'DISCONFIRMED': verifier = "import json; print(json.dumps({'sum':6}))"
    if outcome == 'PENDING_VALIDATION': verifier = "print('PASS')"
    grant = {'operator_id':'operator', 'thread_id':thread.thread_id, 'request_hash':digest(e),
        'root':str(tmp_path/'artifact'), 'claim_text':'2+3=5', 'required_files':list(CONTENTS),
        'authority_reference':'operator:boot-proof', 'expected_observation':{'sum':5},
        'verification_command':[sys.executable,'-B','-c',verifier]}
    grant_path = tmp_path/'grant.json'; grant_path.write_text(json.dumps(grant))
    config = {'repository':r'C:\REALITY_PRIMACY' if outcome != 'UNAVAILABLE' else str(tmp_path/'absent'),
              'grant':str(grant_path), 'ledger':str(tmp_path/'rp.sqlite')}
    config_path=tmp_path/'rp-config.json';config_path.write_text(json.dumps(config))
    monkeypatch.setenv('MODE_RP_CONFIG', str(config_path))
    r=ModeRuntime('operator',str(tmp_path/'operators'),str(tmp_path/'threads'))
    r.build_runtime.provider.agent=Model()
    try:
        r.boot()
        process=r._rp_process
        if outcome == 'STALE':
            r.reality_acceptance_client._clock=lambda: datetime.now(timezone.utc)+timedelta(days=1)
        # Exercise the ordinary input loop after real boot, not the manual launcher.
        observed_states=[]
        def inputs(_):
            if not observed_states:
                observed_states.append(None)
                return '/build '+json.dumps(e)
            raise KeyboardInterrupt
        monkeypatch.setattr('builtins.input', inputs)
        r.run()
        out=r.context.build_result
        if outcome in {'PROHIBITED', 'UNRESOLVED'}:
            assert out['build']['validation_status'] == ('FAIL' if outcome == 'PROHIBITED' else 'UNPROVEN'), out
            assert out['rp']['rp_state'] == 'CONFIRMED', out
            assert out['state'] == ('BUILD_FAIL' if outcome == 'PROHIBITED' else 'BUILD_UNPROVEN'), out
            assert r.context.runtime_state != RuntimeState.COMPLETE
            return
        assert out['build']['validation_status'] == 'PASS', out
        assert out.get('rp', {}).get('accepted', False) == (outcome == 'CONFIRMED'), out
        assert out['state'] == ('BUILD_PASS_RP_'+outcome if outcome in {'CONFIRMED','DISCONFIRMED'} else 'BUILD_PASS_RP_PENDING'), out
        if process:
            assert process.process.pid != __import__('os').getpid()
            replay=r.reality_acceptance_client.evaluate(out['rp']['request'])
            assert not replay['accepted']
        record=r.runtime_observation_collector.store.load_record('operator',out['observation_ids'][-1])
        assert record.observed_outcome['build']['spec_id'] == out['specification']['spec_id']
        assert record.observed_outcome['understanding']
        if outcome in {'CONFIRMED','DISCONFIRMED','PENDING_VALIDATION'}:
            assert record.observed_outcome['rp']['receipt_id']
    finally:
        r.shutdown()
    assert r._supervisor_thread is None
    if process: assert process.process.poll() is not None and not process.reader.is_alive()


def test_mechanism_obligation_is_not_metadata_only():
    from builder.core.understanding_obligations import obligation_requirements
    values=obligation_requirements({'mechanism_requirements':{'mechanism_requirements':[
        {'mechanism_id':'mechanism:1','description':'required gate','status':'EXISTING_SUFFICIENT'}]}})
    value=json.loads(values[0].removeprefix('obligation:'))
    assert value['source']=='mechanism:mechanism:1' and value['predicate']==''


@pytest.mark.parametrize('value,clarify', [(0.50,False),(0.5001,True),(0.64,True),(0.65,True)])
def test_canonical_clarification_threshold(value, clarify):
    from models.runtime_models import CanonicalInteractionState
    from clarification.clarification_engine import evaluate_clarification_state
    from posture.response_posture_engine import determine_posture
    state=CanonicalInteractionState('id','thread','Build a thing')
    state.ambiguity_score=value
    evaluate_clarification_state(state)
    assert state.clarification_required is clarify
    assert not state.downstream_authority_allowed
    if clarify: assert determine_posture(state)=='CLARIFY_FIRST'
