"""Operator-only memory lifecycle commands through the existing manager."""
from uuid import uuid4
from .strict_json import load_payload
from system_layer.contracts import digest


def execute(runtime,text):
    action,_,body=text[len('/memory '):].partition(' ')
    owner=runtime.context.identity.operator_id
    event={'operation_id':'memory-command:'+uuid4().hex,'action':action,'request_hash':digest(text),'state':'STARTED'}
    manager=runtime.persistent_memory_manager
    try:
        if action=='show':
            if not body.strip():raise ValueError('Exact memory identity required')
            result=manager.store.history(owner,body)
            event.update(state='RETURNED',memory_id=body,result_hash=digest(result))
        else:
            if action not in {'archive','restore','remove'}:raise ValueError('Unknown memory lifecycle command')
            data=load_payload(body)
            if type(data) is not dict or set(data)!={'id','confirmation'}:raise ValueError('Exact memory identity and actual Operator confirmation required')
            record=manager.lifecycle(owner,data['id'],action.upper(),data['confirmation'])
            result=record.to_dict()
            event.update(state='COMMITTED',memory_id=record.memory_id,memory_version=record.version,
                memory_status=record.status.value,authorization_state='APPROVED',scope=record.storage_scope.value,
                authority_source='data_governance.memory_governance',
                authority_reference=record.governance_decision['decision_id'],
                record_references=[record.governance_decision['decision_id']],result_hash=digest(result))
    except Exception as exc:
        event.update(state='REJECTED' if isinstance(exc,PermissionError) else 'FAILED',error_type=type(exc).__name__)
        if isinstance(exc,PermissionError):event['authorization_state']='REJECTED'
        runtime._observe_runtime_event('memory_lifecycle',event,runtime_error=type(exc).__name__)
        raise
    runtime._observe_runtime_event('memory_lifecycle',event)
    return result
