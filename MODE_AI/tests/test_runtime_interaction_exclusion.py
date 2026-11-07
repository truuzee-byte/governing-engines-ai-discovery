import threading
from types import SimpleNamespace as NS
from integration.mode_runtime_hooks import process_supervisor_messages


def test_supervisor_keeps_messages_unclaimed_during_operator_context_use():
    calls=[];runtime=NS(_interaction_lock=threading.RLock(),pending_action=None)
    adapter=NS(process_pending_messages=lambda *a:calls.append('processed') or ['result'])
    with runtime._interaction_lock:
        results=[]
        thread=threading.Thread(target=lambda:results.append(process_supervisor_messages(runtime,'task',adapter)))
        thread.start();thread.join(2)
        assert not thread.is_alive() and results==[[]] and calls==[]
    runtime._knowledge_context_selection=('operator','thread',['source'],None)
    assert process_supervisor_messages(runtime,'task',adapter)==[] and calls==[]
    runtime._knowledge_context_selection=None
    runtime._knowledge_record_context_selection=('operator','thread','project',['record'])
    assert process_supervisor_messages(runtime,'task',adapter)==[] and calls==[]
    runtime._knowledge_record_context_selection=None
    runtime.pending_action=object()
    assert process_supervisor_messages(runtime,'task',adapter)==[]
    runtime.pending_action=None
    assert process_supervisor_messages(runtime,'task',adapter)==['result']
    assert calls==['processed']
