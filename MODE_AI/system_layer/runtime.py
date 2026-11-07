"""Explicit operator command surface; model output cannot invoke approval."""
import json
from integration.strict_json import load_payload
from .service import SystemLayer


def execute(runtime,text):
    """Link the normal command attempt to its returned canonical records.

    Existing capability validation observations remain authoritative for their
    outcomes. Reading a receipt here does not issue another receipt or validate it.
    """
    from uuid import uuid4
    from .contracts import digest
    payload={'operation_id':'system-command:'+uuid4().hex,'command':text.split(' ',2)[:2],
        'request_hash':digest(text),'state':'STARTED','execution_authority':False}
    try:result=command(runtime,text)
    except Exception as exc:
        payload.update(state='REJECTED' if isinstance(exc,PermissionError) else 'FAILED',error_type=type(exc).__name__)
        if isinstance(exc,PermissionError):payload['authorization_state']='REJECTED'
        runtime._observe_runtime_event('system_command',payload,runtime_error=type(exc).__name__)
        raise
    payload.update(state='RETURNED',result_hash=digest(result))
    if isinstance(result,dict):
        payload['record_references']=[result['receipt_id']] if isinstance(result.get('receipt_id'),str) else []
        if isinstance(result.get('admission'), dict):
            payload['record_references'].append(result['admission']['receipt_id'])
            if result.get('object'):
                payload['record_references'].append(result['object']['receipt_id'])
            payload['result_state'] = result['admission']['value']['decision']
        else:
            payload['result_state']=result.get('state')
    runtime._observe_runtime_event('system_command',payload)
    return result


def service(runtime):
    if not hasattr(runtime, 'system_layer'):
        runtime.system_layer = SystemLayer(
            runtime.understanding_engine.store.path.with_name('system_layer.sqlite3'), runtime,
            getattr(runtime, 'capability_reality_client', None))
    return runtime.system_layer


def command(runtime, text):
    if not text.startswith('/system '):
        return None
    action, _, body = text[len('/system '):].partition(' ')
    manager = service(runtime)
    if action == 'show':
        return manager.store.get(manager.owner, body)
    if action == 'history':
        return manager.store.history(manager.owner)
    if action == 'context':
        runtime._system_context_selection = None
        record=manager._record(body)
        runtime._system_context_selection = (runtime.context.active_thread.thread_id, body, record['receipt_id'])
        return {'selected_capability': body, 'selected_receipt_id':record['receipt_id'], 'authority': 'DECLARATION_ONLY'}
    if action == 'operation_plan':
        result = getattr(runtime.context, 'understanding_result', None)
        if result is None:
            raise PermissionError('Governed capability understanding required')
        if (result.operator_id!=manager.owner or result.final_understanding is None
                or result.final_understanding.thread_id!=runtime.context.active_thread.thread_id):
            raise PermissionError('Operational preparation requires current Operator/thread meaning')
        inventory = manager.store.get(manager.owner, 'inventory:' + body)
        operational = manager.store.get(manager.owner, 'operational-understanding:' + body)
        if inventory is None or operational is None:
            raise PermissionError('Inventory and operational model must be admitted first')
        sources=manager.store.get(manager.owner,'operational-sources:'+body)
        if sources is not None and (sources['value']['model_hash']!=operational['value']['model']['model_hash'] or sources['value']['inventory_hash']!=inventory['value']['inventory_hash']):
            raise PermissionError('Operation source binding must be renewed for the current model/inventory')
        return result.operational_handoff(operational['value']['model'], inventory['value'],
            current_system_version=inventory['value']['system_version'],source_bindings=sources['value']['bindings'] if sources else None)
    methods = {'admit_material': manager.admit_material,
               'identity': manager.identity, 'declare': manager.declare, 'audit': manager.audit,
               'discover_sources':manager.discover_sources,
               'inventory': manager.inventory,
               'operational_understanding': manager.operational_understanding,
               'operational_sources':manager.operational_sources,
               'control': manager.control, 'prepare': manager.prepare, 'construct': manager.construct,
               'validate': manager.validate, 'accept': manager.accept, 'rollback': manager.rollback,
               'learning_change': manager.learning_change, 'recommend': manager.recommend,
               'admit_library': manager.admit_library}
    if action not in methods:
        raise ValueError('Unknown System Layer action')
    return methods[action](**load_payload(body))


def prompt_context(runtime):
    from data_governance.context_admission import Admission
    store = getattr(getattr(runtime, 'understanding_engine', None), 'store', None)
    if not hasattr(runtime, 'system_layer') and (store is None or not store.path.with_name('system_layer.sqlite3').exists()):
        return None
    manager = service(runtime)
    identity = manager.store.get(manager.owner, 'identity')
    if identity is None:
        return None
    manager._verify_method(identity['value'])
    admission = Admission(manager.owner, runtime.context.active_thread.thread_id)
    def include(record, value):
        admission.consider('GOVERNANCE', record['receipt_id'], json.dumps(value, sort_keys=True),
            source='SystemLayer/1', basis={'verified': True, 'governance_state': 'APPROVED',
                'classification': 'RUNTIME_DATA', 'validation_state': 'NOT_REQUIRED',
                'authority': 'SystemLayer', 'lineage': [record['receipt_id']]})
    include(identity, {'approved_system_identity': identity['value'], 'grants_execution_authority': False})
    selected = getattr(runtime, '_system_context_selection', None)
    runtime._system_context_selection = None
    if selected and selected[0] == runtime.context.active_thread.thread_id:
        if len(selected)!=3:raise PermissionError('Exact selected capability receipt required')
        record = manager._record(selected[1])
        if record['receipt_id']!=selected[2]:raise PermissionError('Selected capability changed; select the current declaration explicitly')
        include(record, {'capability_declaration': record['value']['capability'],
            'historical_record_only': True, 'requires_current_external_reality_for_transition': True})
        from .audit.structural_inventory_auditor import freshness
        from .audit.operational_understanding_validator import evaluate
        inventory = manager.store.get(manager.owner, 'inventory:' + selected[1])
        operational = manager.store.get(manager.owner, 'operational-understanding:' + selected[1])
        if inventory is not None:
            state = freshness(inventory['value'])
            include(inventory, {'structural_inventory': inventory['value'], 'current_assessment': state,
                'source_is_not_operational_proof': True, 'grants_execution_authority': False})
        else:
            include(record, {'structural_inventory_status': 'NOT_RETRIEVED',
                'operational_understanding_status': 'REVIEW_REQUIRED',
                'description_does_not_prove_operability': True})
        if operational is not None:
            assessment = evaluate(operational['value']['model'], inventory['value'] if inventory else None,
                current_system_version=inventory['value']['system_version'] if inventory else None)
            include(operational, {'operational_model': operational['value']['model'],
                'current_assessment': assessment, 'grants_execution_authority': False})
            sources=manager.store.get(manager.owner,'operational-sources:'+selected[1])
            if sources is not None:
                from .audit.operation_source_binding import assess
                body=sources['value']
                if inventory is None or body['model_hash']!=operational['value']['model']['model_hash'] or body['inventory_hash']!=inventory['value']['inventory_hash']:
                    current={'state':'REVIEW_REQUIRED','reason':'OPERATION_SOURCE_BINDING_SUPERSEDED'}
                else:current=assess(operational['value']['model'],inventory['value'],body['bindings'])
                include(sources,{'operation_sources':current,'grants_execution_authority':False})
    return admission.finish()
