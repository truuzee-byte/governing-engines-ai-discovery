import os
import subprocess
import pytest
from pathlib import Path
from types import SimpleNamespace as NS
from frontend.server import RuntimeViewServer
from memory.thread_store import ThreadStore
from integration.content_custody import command
from system_layer.contracts import digest


@pytest.mark.parametrize('action',['fork','create'])
def test_browser_branches_stored_thread_without_activating_or_promoting_it(tmp_path,action):
    store=ThreadStore(str(tmp_path/'threads'));thread=store.create_thread('op','Conversation')
    thread.add_message('operator','Exact source answer',{'source':'operator'});store.save_thread(thread)
    before=thread.to_dict()
    runtime=NS(context=NS(identity=NS(operator_id='op'),active_thread=thread,runtime_state='IDLE'),thread_store=store)
    view=RuntimeViewServer(runtime,operator_input=True)
    deps=Path(os.environ.get('MODE_NODE_RUNTIME', 'optional-node-runtime'))
    try:
        result=subprocess.run([str(deps/'bin/node.exe'),str(Path(__file__).with_name('frontend_thread_fork_smoke.cjs'))],
            env=dict(os.environ,NODE_PATH=str(deps/'node_modules'),MODE_VIEW_TEST_URL=view.url,MODE_THREAD_ACTION=action),capture_output=True,text=True,timeout=40)
        assert result.returncode==0,'Local thread branch fixture failed'
        assert len(store.list_threads('op'))==1
        result=command(runtime,view.next_input())
        assert not result['active_thread_changed'] and not result['vault_preserved']
        child=store.load_thread('op',result['thread']['thread_id'])
        if action=='fork':
            assert child.messages[0].content=='Exact source answer'
            assert child.continuity['parent_snapshot_hash']==digest(before)
            assert child.title=='Alternate direction'
        else:
            assert child.messages==[] and child.continuity is None and child.title=='Empty direction'
        assert not child.is_active
        assert runtime.context.active_thread is thread and store.load_thread('op',thread.thread_id).to_dict()==before
    finally:view.close()
