import json
from copy import deepcopy
import pytest
from test_execution_spine import runtime, envelope
from interactive_mode_ai import RuntimeState
from memory.thread_store import ThreadStore
from runtime_observation.observation_store import RuntimeObservationStore
from system_layer.contracts import digest


def test_halt_stays_authoritative_and_recovery_is_scoped(tmp_path):
    r = runtime(tmp_path)
    r.thread_store = ThreadStore(str(tmp_path/'threads'))
    r.context.active_thread = r.thread_store.create_thread('operator')
    r._set_state(RuntimeState.HALTED)
    halt = deepcopy(r._halt_latch)
    for state in (RuntimeState.IDLE, RuntimeState.INTERPRETING, RuntimeState.COMPLETE):
        assert not r._set_state(state)
        assert r.context.runtime_state == RuntimeState.HALTED
    saved = r.thread_store.load_thread('operator', r.context.active_thread.thread_id)
    assert saved.halt == halt
    build = envelope(tmp_path/'artifact')
    build['authorization']['thread_id'] = r.context.active_thread.thread_id
    denied = r.build_runtime.execute(build)
    assert denied['state'] == 'SPECIFICATION_NOT_READY'
    assert any('halt' in reason.lower() for reason in denied['reasons'])
    request = {'halt': halt, 'target_state': 'IDLE'}
    approval = {'operator_id':'operator','action':'RUNTIME_HALT_RECOVERY','decision':'APPROVE','hash':digest(request)}
    with pytest.raises(PermissionError): r.recover_halt(request, {})
    assert r.recover_halt(request, approval)['execution_authority'] is False
    assert r.thread_store.load_thread('operator', saved.thread_id).halt is None
    with pytest.raises(PermissionError): r.recover_halt(request, approval)
    assert r.build_runtime.execute(build)['state']=='BUILD_PASS_RP_PENDING'


def test_thread_switch_does_not_clear_runtime_halt(tmp_path):
    r = runtime(tmp_path)
    r._set_state(RuntimeState.HALTED)
    r.context.active_thread.thread_id = 'other'
    assert not r._set_state(RuntimeState.IDLE)
    request = {'halt':r._halt_latch,'target_state':'IDLE'}
    with pytest.raises(PermissionError):
        r.recover_halt(request, {'operator_id':'operator','action':'RUNTIME_HALT_RECOVERY','decision':'APPROVE','hash':digest(request)})


def test_recovery_cannot_clear_latch_when_other_threads_cannot_be_checked(tmp_path, monkeypatch):
    r=runtime(tmp_path)
    r.thread_store=ThreadStore(str(tmp_path/'threads'))
    r.context.active_thread=r.thread_store.create_thread('operator')
    r._set_state(RuntimeState.HALTED)
    request={'halt':deepcopy(r._halt_latch),'target_state':'IDLE'}
    monkeypatch.setattr(r.thread_store,'list_threads',lambda *a: (_ for _ in ()).throw(OSError('unavailable')))
    with pytest.raises(OSError):
        r.recover_halt(request,{'operator_id':'operator','action':'RUNTIME_HALT_RECOVERY','decision':'APPROVE','hash':digest(request)})
    assert r._halt_latch and r.context.runtime_state==RuntimeState.HALTED
    assert r.thread_store.load_thread('operator',r.context.active_thread.thread_id).halt==request['halt']
    assert not r._set_state(RuntimeState.IDLE)


@pytest.mark.parametrize('failure', ['raise','no_write','partial'])
def test_observation_custody_failure_cannot_pass(tmp_path, monkeypatch, failure):
    original = RuntimeObservationStore.save_record
    def save(store, record):
        if store.storage_dir.name != '.observations': return original(store, record)
        if failure == 'raise': raise OSError('injected save failure')
        if failure == 'partial':
            path = store._record_path(record.operator_id, record.observation_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('{')
        return record
    monkeypatch.setattr(RuntimeObservationStore, 'save_record', save)
    result = runtime(tmp_path).build_runtime.execute(envelope(tmp_path/'artifact'))
    assert result['build']['validation_status'] == 'FAIL', result
    receipt = json.loads((tmp_path/'artifact/.builder_metadata/build_receipt.json').read_text())
    assert receipt['final_status'] == 'FAIL'
    assert not any('.observations' in ref for ref in receipt['evidence_references'])
    assert any(c.get('validation_type')=='observation_persistence' and c['state']=='FAILED' for c in receipt['validation_results'])


def test_unpersisted_runtime_event_is_not_sent_to_learning(tmp_path,monkeypatch):
    r=runtime(tmp_path)
    monkeypatch.setattr(RuntimeObservationStore,'save_record',lambda *a:None)
    monkeypatch.setattr('integration.interaction_learning.evaluate',lambda *a:pytest.fail('Unstored evidence reached Learning'))
    assert r._observe_runtime_event('custody_operation',{'operation_id':'test','state':'COMPLETED'}) is None


def test_observation_receipt_and_result_agree(tmp_path):
    from pathlib import Path
    result = runtime(tmp_path).build_runtime.execute(envelope(tmp_path/'artifact'))
    assert result['build']['validation_status'] == 'PASS', result
    receipt = json.loads((tmp_path/'artifact/.builder_metadata/build_receipt.json').read_text())
    assert receipt['evidence_references'] == result['build']['evidence_references']
    refs = [ref for ref in receipt['evidence_references'] if '.observations' in ref]
    assert len(refs) == 1
    assert json.loads(Path(refs[0]).read_text())['observation_id']


def test_finalization_mutation_downgrades_manifest_and_receipt(tmp_path, monkeypatch):
    from builder.core.build_entry import run_builder_core
    from builder.tests.test_builder_entry import _valid_handoff_payload
    from pathlib import Path
    original=RuntimeObservationStore.load_record
    def load(store,*args,**kwargs):
        record=original(store,*args,**kwargs)
        if store.storage_dir.name=='.observations' and record and record.output_artifacts:
            artifact=Path(record.output_artifacts[0])
            if not artifact.is_absolute():artifact=tmp_path/artifact
            artifact.write_text('post-validation mutation',encoding='utf-8')
        return record
    monkeypatch.setattr(RuntimeObservationStore,'load_record',load)
    result=run_builder_core(_valid_handoff_payload(root=tmp_path),str(tmp_path))
    assert result.validation_status=='FAIL'
    assert json.loads(Path(result.receipt_path).read_text())['final_status']=='FAIL'
    from builder.core.build_entry import _metadata_path
    manifest=_metadata_path(str(tmp_path),'.builder_evidence/evidence_manifest.json')
    assert json.loads(manifest.read_text())['validation_status']=='FAIL'


def test_runtime_observation_failure_blocks_before_execution(tmp_path, monkeypatch):
    monkeypatch.setattr(RuntimeObservationStore, 'save_record', lambda *args: (_ for _ in ()).throw(OSError('failed')))
    result = runtime(tmp_path).build_runtime.execute(envelope(tmp_path/'artifact'))
    assert not result['execution_attempted']
    assert result['state']=='CONSTRUCTION_BLOCKED'
    assert not result['observation_ids']
    assert not (tmp_path/'artifact/calculator.py').exists()


def test_postbuild_runtime_observation_failure_updates_receipt(tmp_path, monkeypatch):
    original=RuntimeObservationStore.save_record
    def save(store, record):
        if store.storage_dir.name=='observations' and record.metadata.get('affected_runtime_stage','').startswith('BUILD_PASS'):
            raise OSError('post-build persistence failure')
        return original(store,record)
    monkeypatch.setattr(RuntimeObservationStore,'save_record',save)
    result=runtime(tmp_path).build_runtime.execute(envelope(tmp_path/'artifact'))
    assert result['state']=='BUILD_FAIL'
    assert result['build']['validation_status']=='FAIL'
    assert json.loads((tmp_path/'artifact/.builder_metadata/build_receipt.json').read_text())['final_status']=='FAIL'


def test_normal_boot_and_input_loop_keep_persisted_halt(tmp_path, monkeypatch):
    from interactive_mode_ai import ModeRuntime
    from mode_operator.operator_identity import OperatorIdentity
    from mode_operator.operator_store import OperatorStore
    from agents.reasoning_agent import ReasoningResult
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr('runtime_logging.trace_logger.TRACE_OUTPUT_PATH',tmp_path/'traces.jsonl')
    monkeypatch.setattr('runtime_logging.response_logger.RESPONSE_OUTPUT_PATH',tmp_path/'responses.jsonl')
    monkeypatch.setattr('context.context_resolver.RUNTIME_STATE_ROOT',tmp_path/'context')
    for key in ('MODE_RP_CONFIG','MODE_CAPABILITY_RP_CONFIG','MODE_SUPERVISOR_DB'):
        monkeypatch.delenv(key,raising=False)
    operators=OperatorStore(str(tmp_path/'operators'))
    identity=OperatorIdentity.create('operator');profile=operators.create_profile(identity)
    profile.update_operator_managed_info(preferred_name='Operator',timezone='UTC',language='English')
    store=ThreadStore(str(tmp_path/'threads'));thread=store.create_thread('operator')
    profile.active_thread_id=thread.thread_id;operators.save_profile(identity,profile)
    r=ModeRuntime('operator',str(tmp_path/'operators'),str(tmp_path/'threads'))
    r.boot();r._set_state(RuntimeState.HALTED);r.shutdown()
    fresh=ModeRuntime('operator',str(tmp_path/'operators'),str(tmp_path/'threads'))
    monkeypatch.setattr('core.mode_controller._generate_reasoning_result',
        lambda *a,**k:ReasoningResult('fixture','fixture','offline','','','Hello! How can I help?',0))
    build=envelope(tmp_path/'artifact')
    build['authorization']['thread_id']=thread.thread_id
    inputs=iter(['Hello.','/build '+json.dumps(build),'exit'])
    monkeypatch.setattr('builtins.input',lambda _:next(inputs))
    try:
        fresh.boot()
        from test_execution_spine import Model
        from integration.mode_generation import ModeGenerationProvider
        fresh.build_runtime.provider=ModeGenerationProvider(Model())
        fresh.run()
        assert fresh.context.runtime_state==RuntimeState.HALTED
        assert fresh.context.build_result['state']=='SPECIFICATION_NOT_READY'
        assert not fresh.context.build_result['execution_attempted']
        assert store.load_thread('operator',thread.thread_id).halt
    finally:fresh.shutdown()
