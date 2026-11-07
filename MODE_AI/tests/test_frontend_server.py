import http.client
import json
from types import SimpleNamespace as NS
from urllib.parse import urlparse
from frontend.server import RuntimeViewServer
from memory.thread_memory import ThreadMemory

def test_loopback_view_requires_read_token_and_has_no_command_authority():
    thread=ThreadMemory.create('op');thread.add_message('user','local only')
    runtime=NS(context=NS(identity=NS(operator_id='op'),active_thread=thread,runtime_state='IDLE'))
    view=RuntimeViewServer(runtime)
    url=urlparse(view.url);token=url.fragment.split('=',1)[1]
    def call(method,path,headers=None):
        client=http.client.HTTPConnection(url.hostname,url.port,timeout=3)
        try:
            client.request(method,path,headers=headers or {})
            response=client.getresponse();return response.status,response.read()
        finally:client.close()
    try:
        assert call('GET','/state')[0]==403
        headers={'Authorization':'Bearer '+token}
        status,body=call('GET','/state',headers)
        assert status==200 and json.loads(body)['messages'][0]['content']=='local only'
        assert call('POST','/advance',headers)[0]==405
        assert call('GET','/state',dict(headers,Origin='https://unrelated.example'))[0]==403
        runtime.context.runtime_state='CLARIFYING'
        assert json.loads(call('GET','/state',headers)[1])['state']=='CLARIFYING'
        runtime.context.identity.operator_id='other'
        assert call('GET','/state',headers)[0]==403
    finally:view.close()
    assert not view.thread.is_alive()


def test_browser_binds_to_local_runtime_view():
    import os
    import subprocess
    from pathlib import Path
    dependencies=Path(os.environ.get('MODE_NODE_RUNTIME', 'optional-node-runtime'))
    thread=ThreadMemory.create('op');thread.add_message('user','local only')
    view=RuntimeViewServer(NS(context=NS(identity=NS(operator_id='op'),active_thread=thread,runtime_state='IDLE')))
    try:
        result=subprocess.run([str(dependencies/'bin/node.exe'),str(Path(__file__).with_name('frontend_live_smoke.cjs'))],
            env=dict(os.environ,NODE_PATH=str(dependencies/'node_modules'),MODE_VIEW_TEST_URL=view.url),
            capture_output=True,text=True,timeout=40)
        assert result.returncode==0,'Local browser binding failed; no private URL logged'
    finally:view.close()
