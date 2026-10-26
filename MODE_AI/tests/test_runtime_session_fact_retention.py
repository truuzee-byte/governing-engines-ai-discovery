from types import SimpleNamespace as NS
import threading
from interactive_mode_ai import ModeRuntime
from persistent_memory.persistent_memory_manager import PersistentMemoryManager
from persistent_memory.persistent_memory_store import PersistentMemoryStore
from runtime_state.pending_action_router import PendingActionRouter


def test_distinct_session_facts_survive_shared_category_without_persistent_records(tmp_path,monkeypatch):
    runtime=ModeRuntime.__new__(ModeRuntime);runtime._interaction_lock=threading.RLock()
    runtime.context=NS(identity=NS(operator_id='op'),profile=NS(operator_id='op',operator_managed=NS(preferred_name='Operator',name='Operator')),
        active_thread=NS(thread_id='thread'))
    runtime.pending_action=None;runtime.pending_action_router=PendingActionRouter()
    runtime.persistent_memory_manager=PersistentMemoryManager(PersistentMemoryStore(tmp_path/'memory'))
    first='Save to persistent memory: first exact fact.'
    second='Save to persistent memory: second unrelated exact fact.'
    replies=iter([first,'session-only',second,'session-only',first,'session-only','exit'])
    monkeypatch.setattr('builtins.input',lambda _:next(replies))
    monkeypatch.setattr(runtime,'_observe_runtime_event',lambda *a,**k:None)
    runtime.run()
    assert set(runtime.session_answers[('op','thread')].values())=={first,second}
    assert len(runtime.session_answers[('op','thread')])==2
    assert runtime.persistent_memory_manager.store.load_records_for_operator('op')==[]
