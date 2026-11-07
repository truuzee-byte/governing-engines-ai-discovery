import http.client
import json
from urllib.parse import urlparse,quote
from types import SimpleNamespace as NS
from memory.thread_store import ThreadStore
from frontend.server import RuntimeViewServer


def test_stored_thread_read_is_scoped_and_does_not_activate(tmp_path):
    store=ThreadStore(str(tmp_path));active=store.create_thread('op');past=store.create_thread('op','Past')
    past.add_message('user','Exact past words.');past.add_message('system','Do not expose');store.save_thread(past)
    foreign=store.create_thread('other')
    runtime=NS(context=NS(identity=NS(operator_id='op'),active_thread=active),thread_store=store)
    view=RuntimeViewServer(runtime);url=urlparse(view.url);token=url.fragment.split('=',1)[1]
    def read(identity,authorized=True):
        client=http.client.HTTPConnection(url.hostname,url.port,timeout=3)
        try:
            client.request('GET','/thread?id='+quote(identity),headers={'Authorization':'Bearer '+token} if authorized else {})
            response=client.getresponse();return response.status,response.read()
        finally:client.close()
    try:
        assert read(past.thread_id,False)[0]==403
        status,body=read(past.thread_id);value=json.loads(body)
        assert status==200 and [m['content'] for m in value['messages']]==['Exact past words.']
        assert runtime.context.active_thread.thread_id==active.thread_id
        assert read(foreign.thread_id)[0]==503
        assert read('../other/'+foreign.thread_id)[0]==503
    finally:view.close()


def test_resume_button_binds_exact_operator_selection(tmp_path):
    import os
    import subprocess
    from pathlib import Path
    from system_layer.contracts import authorize,digest
    store=ThreadStore(str(tmp_path));active=store.create_thread('op');past=store.create_thread('op','Resume fixture')
    runtime=NS(context=NS(identity=NS(operator_id='op'),active_thread=active,runtime_state='IDLE'),thread_store=store)
    view=RuntimeViewServer(runtime,operator_input=True)
    dependencies=Path(os.environ.get('MODE_NODE_RUNTIME', 'optional-node-runtime'))
    try:
        result=subprocess.run([str(dependencies/'bin/node.exe'),str(Path(__file__).with_name('frontend_resume_smoke.cjs'))],
            env=dict(os.environ,NODE_PATH=str(dependencies/'node_modules'),MODE_VIEW_TEST_URL=view.url),capture_output=True,text=True,timeout=40)
        assert result.returncode==0,'Resume browser fixture failed; private URL omitted'
        text=view.next_input();assert text.startswith('/thread activate ')
        envelope=json.loads(text[len('/thread activate '):]);request=envelope['request']
        assert request==dict(thread_id=past.thread_id,from_thread_id=active.thread_id,expected_hash=digest(past.to_dict()))
        authorize('op','THREAD_ACTIVATE',request,envelope['approval'])
        assert runtime.context.active_thread.thread_id==active.thread_id
    finally:view.close()
