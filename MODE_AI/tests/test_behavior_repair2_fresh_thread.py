"""Exercise thread creation/selection through the real CLI, with no provider."""
import json
from system_layer.contracts import digest


def test_empty_thread_cli_selection_survives_normal_boot(tmp_path,monkeypatch):
    from interactive_mode_ai import ModeRuntime
    from mode_operator.operator_identity import OperatorIdentity
    from mode_operator.operator_store import OperatorStore
    from memory.thread_store import ThreadStore
    monkeypatch.chdir(tmp_path)
    operators=OperatorStore(str(tmp_path/'operators'))
    identity=OperatorIdentity.create('op')
    profile=operators.create_profile(identity)
    profile.update_operator_managed_info(preferred_name='Operator',timezone='UTC',language='English')
    threads=ThreadStore(str(tmp_path/'threads'))
    old=threads.create_thread('op')
    old.add_message('operator','Old thread private declaration.')
    threads.save_thread(old)
    profile.active_thread_id=old.thread_id
    operators.save_profile(identity,profile)
    r=ModeRuntime('op',str(tmp_path/'operators'),str(tmp_path/'threads'))
    calls=[]
    selected=[]
    def command(prefix,request,action):
        return prefix+json.dumps({'request':request,'approval':{
            'operator_id':'op','action':action,'decision':'APPROVE','hash':digest(request)}})
    def feed(prompt):
        calls.append(prompt)
        if len(calls)==1:
            return command('/thread create ',{'title':'Fresh qualification'},'THREAD_CREATE')
        if len(calls)==2:
            result=r.context.operation_view['result']
            assert result['contract']=='ThreadCreation/1'
            selected.append(result['thread']['thread_id'])
            return command('/thread activate ',{'thread_id':selected[0],
                'expected_hash':result['thread_hash'],'from_thread_id':old.thread_id},'THREAD_ACTIVATE')
        assert len(calls)==3, 'No retry allowed'
        assert r.context.operation_view['result']['contract']=='ThreadActivation/1'
        assert r.context.active_thread.thread_id==selected[0]
        assert r.context.active_thread.messages==[]
        return 'quit'
    monkeypatch.setattr('builtins.input',feed)
    try:
        r.boot();r.run()
    finally:r.shutdown()
    restarted=ModeRuntime('op',str(tmp_path/'operators'),str(tmp_path/'threads'))
    try:
        restarted.boot()
        assert restarted.context.active_thread.thread_id==selected[0]
        assert restarted.context.active_thread.messages==[]
        assert 'Old thread private declaration.' not in str(restarted._build_engine_input('Hello.'))
    finally:restarted.shutdown()
