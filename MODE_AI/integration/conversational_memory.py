"""Natural explicit memory commands using the existing governed writer only."""
from uuid import uuid4
from hashlib import sha256
from persistent_memory.operator_requests import create_content,removal_target,removal_matches


def execute(runtime,text):
    content=create_content(text);target=removal_target(text)
    if content is None and target is None:return None
    owner=runtime.context.identity.operator_id
    thread=runtime.context.active_thread.thread_id
    manager=runtime.persistent_memory_manager
    operation_id='memory-request:'+uuid4().hex
    if target is not None:
        candidates=[r for r in manager.retrieve_memories(owner) if removal_matches(text,r.content)]
        if len(candidates)!=1:
            return {'state':'CLARIFICATION_REQUIRED' if candidates else 'NO_MATCHING_PERSISTENT_MEMORY',
                'persistent_saved':False,'message':'No memory changed. Specify an exact memory identity.' if candidates else
                'No matching persistent memory is active. This statement remains in this thread.'}
        record=manager.lifecycle(owner,candidates[0].memory_id,'REMOVE',text)
        result={'state':'REMOVED','persistent_saved':False,'memory_id':record.memory_id,
            'version':record.version,'message':'Matching persistent memory removed; the conversation still retains your statement.'}
    else:
        proposed=manager.propose_create_memory(owner,content,thread,operation_id,text)
        if proposed.candidate is not None and proposed.requires_confirmation:
            proposed=manager.confirm_candidate(proposed.candidate,text)
        record=proposed.record
        result=proposed.to_dict()
        result.update(state='SAVED' if record else 'NOT_SAVED',persistent_saved=record is not None)
    runtime._observe_runtime_event('memory_result',{
        'operation_id':operation_id,'memory_id':record.memory_id if record else None,
        'authorization_state':'APPROVED' if record else 'UNRESOLVED','scope':'PERSISTENT',
        'persistent_saved':result['persistent_saved'],'result':result['state'],
        'content_sha256':sha256((content if content is not None else candidates[0].content).encode('utf-8')).hexdigest(),
        'authority_source':'data_governance.memory_governance' if record else 'persistent_memory_manager',
        'receipt_id':proposed.receipt.receipt_id if content is not None and proposed.receipt else None,
        'authority_reference':record.governance_decision['decision_id'] if record else None,
        'record_references':[record.governance_decision['decision_id']] if record else [],
        'receipt_evidence':proposed.receipt.evidence_projection() if content is not None and proposed.receipt else None},
        runtime_error='MEMORY_OPERATION_FAILED' if content is not None and not proposed.success else None)
    return result
