import os
import subprocess
from pathlib import Path
from types import SimpleNamespace as NS
from frontend.server import RuntimeViewServer
from memory.thread_store import ThreadStore
from memory.vault import Vault
from integration.content_custody import command


def test_browser_preserves_exact_stored_thread_only_after_explicit_dispatch(tmp_path):
    store=ThreadStore(str(tmp_path/'threads'));thread=store.create_thread('op','Conversation')
    thread.add_message('operator','My exact statement',{'source':'operator'});store.save_thread(thread)
    runtime=NS(context=NS(identity=NS(operator_id='op'),active_thread=thread,runtime_state='IDLE'),thread_store=store,
        understanding_engine=NS(store=NS(path=tmp_path/'meaning.db')))
    view=RuntimeViewServer(runtime,operator_input=True)
    dependencies=Path(os.environ.get('MODE_NODE_RUNTIME', 'optional-node-runtime'))
    try:
        result=subprocess.run([str(dependencies/'bin/node.exe'),str(Path(__file__).with_name('frontend_vault_preserve_smoke.cjs'))],
            env=dict(os.environ,NODE_PATH=str(dependencies/'node_modules'),MODE_VIEW_TEST_URL=view.url),capture_output=True,text=True,timeout=40)
        assert result.returncode==0,'Local preservation fixture failed; private URL omitted'
        assert not (tmp_path/'content_custody.sqlite3').exists()
        record=command(runtime,view.next_input())
        preserved=Vault(tmp_path/'content_custody.sqlite3').thread_snapshot('op',record['object_id'],record['version'],record['record_hash'])
        assert preserved['thread']==thread.to_dict() and not preserved['claims_validated']
        assert store.load_thread('op',thread.thread_id).to_dict()==thread.to_dict()
    finally:view.close()
