import http.client
import json
from types import SimpleNamespace as NS
from urllib.parse import urlparse,parse_qs
import pytest
from frontend.server import RuntimeViewServer


def test_separate_input_scope_queues_without_execution_and_rejects_replay():
    runtime=NS(context=NS(identity=NS(operator_id='op'),active_thread=NS(thread_id='t')))
    view=RuntimeViewServer(runtime,operator_input=True);url=urlparse(view.url);tokens=parse_qs(url.fragment)
    def post(token,data,origin=None):
        c=http.client.HTTPConnection(url.hostname,url.port,timeout=3)
        try:
            c.request('POST','/input',body=json.dumps(data),headers={'Authorization':'Bearer '+token,
                'Content-Type':'application/json','Origin':origin or 'http://'+url.netloc})
            r=c.getresponse();status=r.status;r.read();return status
        finally:c.close()
    try:
        req={'request_id':'one','thread_id':'t','text':'Explain this.'}
        assert post(tokens['access'][0],req)==403
        assert post(tokens['operator_access'][0],req,'https://unrelated.example')==403
        assert post(tokens['operator_access'][0],dict(req,thread_id='other'))==409
        assert post(tokens['operator_access'][0],req)==202
        assert post(tokens['operator_access'][0],req)==409
        assert view.next_input()=='Explain this.'
        assert post(tokens['operator_access'][0],dict(req,request_id='oversized-chat',text='x'*70000))==413
        document=dict(req,request_id='bounded-document',text='/documents intake '+'x'*70000)
        assert post(tokens['operator_access'][0],document)==202
        assert view._input_bytes>65536
        assert view.next_input()==document['text'] and view._input_bytes==0
        assert post(tokens['operator_access'][0],dict(req,request_id='old-consent',text='yes'))==202
        runtime.pending_action=NS(action_id='new-proposal')
        with pytest.raises(PermissionError,match='consent context'):view.next_input()
        assert post(tokens['operator_access'][0],dict(req,request_id='wrong-proposal',text='yes',pending_action_id='old-proposal'))==409
        assert post(tokens['operator_access'][0],dict(req,request_id='bound-consent',text='no',pending_action_id='new-proposal'))==202
        assert view.next_input()=='no'
        runtime.pending_action=None
        assert post(tokens['operator_access'][0],dict(req,request_id='two'))==202
        runtime.context.active_thread.thread_id='changed'
        with pytest.raises(PermissionError):view.next_input()
    finally:view.close()
    assert view.next_input()=='exit'


def test_queue_runs_through_normal_runtime_custody_and_observation(tmp_path,monkeypatch):
    from interactive_mode_ai import ModeRuntime
    import interactive_mode_ai as app
    from mode_operator.operator_identity import OperatorIdentity
    from mode_operator.operator_store import OperatorStore
    from memory.thread_store import ThreadStore
    from system_layer.contracts import digest
    monkeypatch.chdir(tmp_path)
    operators=OperatorStore(str(tmp_path/'operators'));identity=OperatorIdentity.create('op')
    profile=operators.create_profile(identity);profile.update_operator_managed_info(preferred_name='Operator',timezone='UTC',language='English')
    thread=ThreadStore(str(tmp_path/'threads')).create_thread('op');profile.active_thread_id=thread.thread_id
    operators.save_profile(identity,profile)
    runtime=ModeRuntime('op',str(tmp_path/'operators'),str(tmp_path/'threads'))
    monkeypatch.setattr(app,'process_interaction',lambda *a,**k:pytest.fail('Custody command reached model'))
    try:
        runtime.boot();view=RuntimeViewServer(runtime,operator_input=True);runtime._frontend_view=view
        request=dict(object_id='kept',content='Explicit preserved fact.',kind='CANON',project_id='p',thread_id=thread.thread_id,
            source_reference='operator:ui',authority='operator',expected_previous=None)
        text='/vault preserve '+json.dumps(dict(request=request,approval=dict(operator_id='op',action='VAULT_PRESERVE',decision='APPROVE',hash=digest(request))))
        view._inputs.put({'thread_id':thread.thread_id,'text':text,'request_id':'fixture-one'})
        view._inputs.put({'thread_id':thread.thread_id,'text':'exit','request_id':'fixture-two'})
        runtime.run()
        records=runtime.runtime_observation_collector.store.load_records_for_operator('op')
        event=next(r for r in records if r.metadata.get('affected_runtime_stage')=='custody_operation')
        assert event.metadata['observed_outcome']['state']=='COMPLETED'
        assert event.metadata['observed_outcome']['record_references']
        assert request['content'] not in str(event.to_dict())
        from frontend.runtime_view import snapshot
        projection=snapshot(runtime,expected_owner='op')
        assert projection['operation']['result']['content']==request['content']
        assert projection['operation']['state']=='RETURNED'
    finally:runtime.shutdown()


def test_browser_submits_to_input_queue():
    import os
    import subprocess
    from pathlib import Path
    from memory.thread_memory import ThreadMemory
    thread=ThreadMemory.create('op')
    runtime=NS(context=NS(identity=NS(operator_id='op'),active_thread=thread,runtime_state='IDLE'))
    view=RuntimeViewServer(runtime,operator_input=True)
    dependencies=Path(os.environ.get('MODE_NODE_RUNTIME', 'optional-node-runtime'))
    try:
        result=subprocess.run([str(dependencies/'bin/node.exe'),str(Path(__file__).with_name('frontend_input_smoke.cjs'))],
            env=dict(os.environ,NODE_PATH=str(dependencies/'node_modules'),MODE_VIEW_TEST_URL=view.url),
            capture_output=True,text=True,timeout=40)
        assert result.returncode==0,'Input browser fixture failed; private URL omitted'
        assert view.next_input()=='A queued fixture message.'
    finally:view.close()
