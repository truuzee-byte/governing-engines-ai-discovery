"""Explicit thread resumption without transplanting session or execution authority.

Operator Experience §§7–9: retain conversation groups, select deliberately,
and keep Vault preservation separate. The runtime is the sole mutation caller.
"""
from system_layer.contracts import authorize,digest


def activate(runtime,request,approval):
    from interactive_mode_ai import BootContext,RuntimeState
    owner=runtime.context.identity.operator_id
    if type(request) is not dict or set(request)!={'thread_id','expected_hash','from_thread_id'}:
        raise ValueError('Exact source and destination thread selection required')
    authorize(owner,'THREAD_ACTIVATE',request,approval)
    if runtime.pending_action is not None:raise PermissionError('Resolve pending consent before switching threads')
    if runtime.context.runtime_state not in {RuntimeState.IDLE,RuntimeState.LISTENING,RuntimeState.COMPLETE,RuntimeState.CLARIFYING}:
        raise PermissionError('Runtime cannot switch during execution, failure, or halt')
    if request['from_thread_id']!=runtime.context.active_thread.thread_id:
        raise ValueError('Active thread changed before selection')
    # Finish any existing supervisor interaction before replacing its context.
    running=runtime._supervisor_thread is not None and runtime._supervisor_thread.is_alive()
    runtime._stop_supervisor_listener()
    try:
        old=runtime.context
        if old.runtime_state not in {RuntimeState.IDLE,RuntimeState.LISTENING,RuntimeState.COMPLETE,RuntimeState.CLARIFYING}:
            raise PermissionError('Runtime state changed before selection')
        with runtime.build_runtime._lock:
            baseline=getattr(old.active_thread,'_custody_baseline',None)
            if baseline is None or getattr(old.active_thread,'_custody_conflict',False) or digest(old.active_thread.to_dict())!=baseline:
                raise PermissionError('Current thread has unverified or unpersisted changes; selection cannot discard them')
            thread=runtime.thread_store.load_thread(owner,request['thread_id'])
            if digest(thread.to_dict())!=request['expected_hash']:raise ValueError('Selected thread changed')
            profile=runtime.operator_store.select_active_thread(old.identity,thread.thread_id,old.profile.to_dict())
            runtime.context=BootContext(identity=old.identity,profile=profile,onboarding_state=old.onboarding_state,
                active_thread=thread,temporal_context=old.temporal_context,runtime_state=RuntimeState.IDLE)
            for name in ('_knowledge_context_selection','_vault_context_selection','_system_context_selection'):
                setattr(runtime,name,None)
            runtime._retrieved_memory_ids=[]
            # Thread-bound RP requests and prior result projections are never inherited.
            runtime._reality_requirements={}
            runtime._observed_transitions=[]
        return {'contract':'ThreadActivation/1','from_thread_id':old.active_thread.thread_id,
            'thread_id':thread.thread_id,'thread_hash':request['expected_hash'],'profile_persisted':True,
            'vault_preserved':False,'execution_authority':False}
    finally:
        if running:runtime._start_supervisor_listener()
