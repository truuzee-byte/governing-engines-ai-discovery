import json
import pytest
from system_layer.contracts import digest
from integration.content_custody import execute


def test_thread_resumption_preserves_scope_and_survives_boot(tmp_path,monkeypatch):
    from interactive_mode_ai import ModeRuntime,RuntimeState
    from mode_operator.operator_identity import OperatorIdentity
    from mode_operator.operator_store import OperatorStore
    from memory.thread_store import ThreadStore
    monkeypatch.chdir(tmp_path)
    operators=OperatorStore(str(tmp_path/'operators'));identity=OperatorIdentity.create('op')
    profile=operators.create_profile(identity)
    profile.update_operator_managed_info(preferred_name='Operator',timezone='UTC',language='English')
    threads=ThreadStore(str(tmp_path/'threads'));first=threads.create_thread('op');past=threads.create_thread('op','Resume me')
    past.add_message('user','Exact prior conversation.');threads.save_thread(past)
    original=past.to_dict();profile.active_thread_id=first.thread_id;operators.save_profile(identity,profile)
    runtime=ModeRuntime('op',str(tmp_path/'operators'),str(tmp_path/'threads'))
    request=dict(thread_id=past.thread_id,expected_hash=digest(original),from_thread_id=first.thread_id)
    approval=dict(operator_id='op',action='THREAD_ACTIVATE',decision='APPROVE',hash=digest(request))
    text='/thread activate '+json.dumps(dict(request=request,approval=approval))
    try:
        runtime.boot()
        runtime._knowledge_context_selection='old';runtime._vault_context_selection='old'
        runtime.context.understanding_result='old meaning';runtime._reality_requirements={'COMPLETE':'old authority'}
        runtime.session_answers={('op',first.thread_id):{'private':'first thread only'}}
        with pytest.raises(PermissionError):execute(runtime,text.replace('APPROVE','REJECT'))
        runtime.pending_action=object()
        with pytest.raises(PermissionError,match='pending consent'):execute(runtime,text)
        runtime.pending_action=None
        runtime.context.runtime_state=RuntimeState.HALTED
        with pytest.raises(PermissionError,match='halt'):execute(runtime,text)
        runtime.context.runtime_state=RuntimeState.IDLE
        saved=runtime.context.active_thread
        runtime.context.active_thread.add_message('user','Unpersisted exact answer')
        with pytest.raises(PermissionError,match='unpersisted'):execute(runtime,text)
        assert runtime.context.active_thread is saved
        assert runtime.context.active_thread.messages[-1].content=='Unpersisted exact answer'
        threads.save_thread(runtime.context.active_thread)
        with monkeypatch.context() as scoped:
            scoped.setattr(runtime.operator_store,'_write_json',lambda *a:(_ for _ in ()).throw(OSError('write failed')))
            with pytest.raises(OSError):execute(runtime,text)
        assert runtime.context.active_thread.thread_id==first.thread_id
        assert json.loads(operators._profile_path('op').read_text())['active_thread_id']==first.thread_id
        result=execute(runtime,text)
        assert result['profile_persisted'] and runtime.context.active_thread.to_dict()==original
        assert runtime.context.understanding_result is None and not runtime._reality_requirements
        assert runtime._knowledge_context_selection is None and runtime._vault_context_selection is None
        prompt=str(runtime._build_engine_input('Continue this conversation.'))
        assert 'Exact prior conversation.' in prompt and 'first thread only' not in prompt
        assert threads.load_thread('op',past.thread_id).to_dict()==original
        with pytest.raises(ValueError,match='Active thread changed'):execute(runtime,text)
    finally:runtime.shutdown()
    restarted=ModeRuntime('op',str(tmp_path/'operators'),str(tmp_path/'threads'))
    try:
        restarted.boot();assert restarted.context.active_thread.to_dict()==original
    finally:restarted.shutdown()
