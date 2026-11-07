import json
import pytest
from system_layer.contracts import digest
from integration.content_custody import command


def test_onboarding_uses_exact_operator_answers_and_blocks_stale_profile(tmp_path,monkeypatch):
    from interactive_mode_ai import ModeRuntime
    from mode_operator.operator_identity import OperatorIdentity
    from mode_operator.operator_store import OperatorStore
    from memory.thread_store import ThreadStore
    monkeypatch.chdir(tmp_path)
    store=OperatorStore(str(tmp_path/'operators'));identity=OperatorIdentity.create('op');profile=store.create_profile(identity)
    profile.update_operator_managed_info(preferred_name='Before',timezone='UTC',language='English')
    thread=ThreadStore(str(tmp_path/'threads')).create_thread('op');profile.active_thread_id=thread.thread_id;store.save_profile(identity,profile)
    runtime=ModeRuntime('op',str(tmp_path/'operators'),str(tmp_path/'threads'))
    def send(req):
        return command(runtime,'/onboarding '+json.dumps(dict(request=req,approval=dict(operator_id='op',action='OPERATOR_ONBOARDING_UPDATE',decision='APPROVE',hash=digest(req)))))
    try:
        runtime.boot();previous=digest(runtime.context.profile.to_dict())
        request=dict(expected_profile_hash=previous,thread_id=thread.thread_id,answers=dict(preferred_name='Chosen name',timezone='America/New_York',language='English'))
        with pytest.raises(ValueError,match='timezone'):send(dict(request,answers=dict(request['answers'],timezone='Not/Real')))
        assert digest(runtime.context.profile.to_dict())==previous
        result=send(request)
        assert result['answers']==request['answers'] and result['persistent_memory_saved'] is False
        assert runtime.context.active_thread.thread_id==thread.thread_id
        assert store.load_profile(identity).operator_managed.preferred_name=='Chosen name'
        with pytest.raises(ValueError,match='changed'):send(request)
    finally:runtime.shutdown()
