"""Normal boot/CLI and prompt assembly: no alternative qualification runtime."""
import json
from pathlib import Path
import pytest

FROZEN=Path(__file__).resolve().parents[1]/'artifacts/behavior_qualification_20260927/frozen60-20260927T170856-29664b20/INPUTS_VERBATIM.json'


def boot(tmp_path,monkeypatch):
    from interactive_mode_ai import ModeRuntime
    from mode_operator.operator_identity import OperatorIdentity
    from mode_operator.operator_store import OperatorStore
    from memory.thread_store import ThreadStore
    monkeypatch.chdir(tmp_path)
    operators=OperatorStore(str(tmp_path/'operators'));identity=OperatorIdentity.create('op')
    profile=operators.create_profile(identity)
    profile.update_operator_managed_info(preferred_name='Operator',timezone='UTC',language='English')
    thread=ThreadStore(str(tmp_path/'threads')).create_thread('op');profile.active_thread_id=thread.thread_id
    operators.save_profile(identity,profile)
    runtime=ModeRuntime('op',str(tmp_path/'operators'),str(tmp_path/'threads'));runtime.boot()
    return runtime


def test_verbatim_memory_requests_through_cli_restart_and_actual_prompt(tmp_path,monkeypatch):
    import interactive_mode_ai as app
    inputs={r['input_number']:r['text'] for r in json.loads(FROZEN.read_text(encoding='utf-8'))}
    r=boot(tmp_path,monkeypatch)
    answers=iter([inputs[16],inputs[17],inputs[20],'exit'])
    monkeypatch.setattr('builtins.input',lambda *a:next(answers))
    monkeypatch.setattr(app,'process_interaction',lambda *a,**k:pytest.fail('Explicit memory command unexpectedly called provider'))
    try:
        r.run()
        records=r.persistent_memory_manager.retrieve_memories('op')
        assert len(records)==1 and records[0].content==inputs[16].split(': ',1)[1]
        assert records[0].evidence.original_operator_statement==inputs[16]
    finally:r.shutdown()
    from memory.thread_store import ThreadStore
    fresh=ThreadStore(str(tmp_path/'threads')).create_thread('op')
    identity=r.context.identity
    profile=r.operator_store.load_profile(identity)
    profile.active_thread_id=fresh.thread_id;r.operator_store.save_profile(identity,profile)
    r=app.ModeRuntime('op',str(tmp_path/'operators'),str(tmp_path/'threads'))
    try:
        r.boot()
        prompt=r._build_engine_input(inputs[23])
        assert records[0].content in str(prompt)
        assert records[0].memory_id in r.context.context_admission['injected_ids']
        assert 'Blue Lantern' not in str(r._build_engine_input(inputs[24]))
    finally:r.shutdown()


def test_verbatim_document_request_reaches_normal_prompt(tmp_path,monkeypatch):
    from integration.content_custody import command
    from system_layer.contracts import digest
    inputs={r['input_number']:r['text'] for r in json.loads(FROZEN.read_text(encoding='utf-8'))}
    r=boot(tmp_path,monkeypatch)
    try:
        req=dict(object_id='blue-lantern-qualification-note',content='Project color label: amber.',kind='DRAFT',
            visual_authority='NOT_APPLICABLE',knowledge_class='INTERNAL',source_reference='operator:note',authority='operator',
            project_id='blue-lantern',thread_id=r.context.active_thread.thread_id,expected_previous=None,validation_references=[])
        record=command(r,'/documents intake '+json.dumps(dict(request=req,approval=dict(operator_id='op',
            action='DOCUMENT_INTAKE',decision='APPROVE',hash=digest(req)))))
        for n in [41,42]:
            prompt=r._build_engine_input(inputs[n])
            assert req['content'] in str(prompt)
            assert record['record_hash'] in r.context.context_admission['injected_ids']
            assert '"claims_validated": false' in str(prompt)
    finally:r.shutdown()
