import pytest
from frontend.runtime_view import snapshot


@pytest.mark.parametrize('choice,persistent,failed',[('yes',True,False),('no',False,False),('session-only',False,False),('yes',False,True)])
def test_actual_memory_consent_result_reaches_operator_view(tmp_path,monkeypatch,choice,persistent,failed):
    from interactive_mode_ai import ModeRuntime
    import interactive_mode_ai as app
    from mode_operator.operator_identity import OperatorIdentity
    from mode_operator.operator_store import OperatorStore
    from memory.thread_store import ThreadStore
    monkeypatch.chdir(tmp_path)
    store=OperatorStore(str(tmp_path/'operators'));identity=OperatorIdentity.create('op');profile=store.create_profile(identity)
    profile.update_operator_managed_info(preferred_name='Operator',timezone='UTC',language='English')
    thread=ThreadStore(str(tmp_path/'threads')).create_thread('op');profile.active_thread_id=thread.thread_id;store.save_profile(identity,profile)
    runtime=ModeRuntime('op',str(tmp_path/'operators'),str(tmp_path/'threads'))
    fact='Save this to persistent memory: I prefer tea.';answers=iter([fact,choice,'exit']);pending=[];events=[]
    observe=runtime._observe_runtime_event
    def capture(name,payload,**kwargs):
        if name=='memory_result':
            import threading
            from types import SimpleNamespace as NS
            from integration.mode_runtime_hooks import process_supervisor_messages
            called=[];out=[]
            adapter=NS(process_pending_messages=lambda *a:called.append(True))
            worker=threading.Thread(target=lambda:out.append(process_supervisor_messages(runtime,'fixture',adapter)))
            worker.start();worker.join(2)
            assert not worker.is_alive() and not called and out==[[]]
        record=observe(name,payload,**kwargs)
        if name in {'memory_proposal','memory_result'}:events.append((name,payload,record))
        return record
    monkeypatch.setattr(runtime,'_observe_runtime_event',capture)
    def input_value(*args):
        value=next(answers)
        if value==choice:
            proposal=snapshot(runtime)['pending_action'];pending.append(proposal['action_id'])
            assert proposal['memory_text']==fact
        return value
    monkeypatch.setattr('builtins.input',input_value)
    monkeypatch.setattr(app,'process_interaction',lambda *a,**k:pytest.fail('Memory consent must not invoke a model'))
    try:
        runtime.boot()
        if failed:
            from persistent_memory.persistent_memory_manager import PersistentMemoryOperationResult
            monkeypatch.setattr(runtime.persistent_memory_manager,'confirm_candidate',
                lambda candidate,operator_confirmation:PersistentMemoryOperationResult(
                    success=False,requires_confirmation=False,message='Storage unavailable',candidate=candidate))
        runtime.run()
        shown=snapshot(runtime)['operation']['result']
        assert runtime.pending_action is None and shown['candidate']['proposed_content']==fact
        assert bool(shown['record'])==persistent
        assert shown['candidate']['source_message_id']==pending[0]
        import hashlib
        assert [event[0] for event in events]==['memory_proposal','memory_result']
        for _,payload,record in events:
            assert payload['operation_id']==pending[0]
            assert payload['content_sha256']==hashlib.sha256(fact.encode()).hexdigest()
            assert fact not in str(payload)
            assert record is not None
            assert record.correlation_id==pending[0]
            assert record.source_traces==[]
            assert record.metadata['trace_reference_kind']=='INLINE_RUNTIME_EVENT'
            assert record.trace_reference==record.metadata['inline_event_reference']
        assert events[-1][1]['receipt_id']==(shown['receipt']['receipt_id'] if shown['receipt'] else None)
        assert events[-1][2].produced_receipts==([shown['receipt']['receipt_id']] if shown['receipt'] else [])
        assert events[-1][1]['persistent_saved']==persistent
        receipt=shown['receipt']
        if receipt:
            evidence=events[-1][2].metadata['observed_outcome']['receipt_evidence']
            assert evidence['receipt_id']==receipt['receipt_id']
            assert evidence['storage_scope']==receipt['storage_scope']
            assert evidence['consent_status']==receipt['consent_status']
            assert evidence['memory_version']==receipt['memory_version']
            assert fact not in str(evidence) and 'new_content' not in evidence
            loaded=runtime.runtime_observation_collector.store.load_record('op',events[-1][2].observation_id)
            assert loaded.metadata['observed_outcome']['receipt_evidence']==evidence
        observed=events[-1][2]
        if persistent:
            assert observed.authority_source=='data_governance.memory_governance'
            assert observed.authority_decision_source==shown['record']['governance_decision']['decision_id']
            assert observed.authority_decision_source!=observed.observation_id
        else:
            assert observed.authority_source=='pending_action_router'
        assert events[0][2].authorization_receipts==[]
        if failed:
            assert 'NORMAL_EXECUTION' not in [kind.value for kind in events[-1][2].observation_types]
            assert 'RUNTIME_ERROR' in [kind.value for kind in events[-1][2].observation_types]
        if choice=='session-only':
            assert shown['session_only_payload']['content']==fact
            assert runtime.session_answers[('op',thread.thread_id)]['GENERAL']==fact
        if persistent:assert runtime.persistent_memory_manager.store.load_record('op',shown['record']['memory_id']).content==fact
    finally:runtime.shutdown()
