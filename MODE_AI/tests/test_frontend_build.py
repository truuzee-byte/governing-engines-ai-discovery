import os
import subprocess
from pathlib import Path
from types import SimpleNamespace as NS
from frontend.server import RuntimeViewServer
from memory.thread_memory import ThreadMemory


def test_build_panel_queues_exact_envelope_without_issuing_authority():
    thread=ThreadMemory.create('op');runtime=NS(context=NS(identity=NS(operator_id='op'),active_thread=thread,runtime_state='IDLE'))
    envelope='{ "request": {}, "understanding": {}, "authorization": {"decision":"NO"} }'
    view=RuntimeViewServer(runtime,operator_input=True)
    dependencies=Path(os.environ.get('MODE_NODE_RUNTIME', 'optional-node-runtime'))
    try:
        result=subprocess.run([str(dependencies/'bin/node.exe'),str(Path(__file__).with_name('frontend_build_smoke.cjs'))],
            env=dict(os.environ,NODE_PATH=str(dependencies/'node_modules'),MODE_VIEW_TEST_URL=view.url,MODE_BUILD_FIXTURE=envelope),
            capture_output=True,text=True,timeout=40)
        assert result.returncode==0,'Local build UI fixture failed; private URL omitted'
        assert view.next_input()=='/build '+envelope
        assert not hasattr(runtime.context,'build_result')
    finally:view.close()
