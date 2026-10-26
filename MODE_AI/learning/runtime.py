"""Local operator interface; no approvals inferred from model output or memory."""
import json
from uuid import uuid4
from .contracts import digest
from .service import LearningService
from .store import LearningStore


def service(runtime):
    if not hasattr(runtime,'learning_service'):
        runtime.learning_service=LearningService(LearningStore(runtime.understanding_engine.store.path.with_name('learning.sqlite3')))
    if not hasattr(runtime,'learning_memory_gateway'):
        from persistent_memory.learning_gateway import LearningMemoryGateway
        runtime.learning_memory_gateway=LearningMemoryGateway(runtime.learning_service.store.path.with_name('learning_memory.sqlite3'),runtime.learning_service.store.get)
        runtime.learning_service.memory_admissibility=runtime.learning_memory_gateway.available
    return runtime.learning_service


def command(runtime,text):
    if not text.startswith('/learning '):return None
    owner=runtime.context.identity.operator_id;manager=service(runtime)
    from learning.revalidation_sources import poll
    for changed in poll(runtime,manager):runtime.learning_memory_gateway.publish(owner,changed['learning_id'])
    for changed in manager.expire_due(owner):
        runtime.learning_memory_gateway.publish(owner,changed['learning_id'])
    action,_,body=text[len('/learning '):].partition(' ')
    if action=='list':
        with manager.store.transaction(owner) as (state,_,__):
            return [{'id':k,'status':v.get('candidate_status',v.get('status')),'scope':v['scope']} for k,v in state.items()]
    if action=='show':
        item=manager.store.get(owner,body)
        if item is None:raise ValueError('Unknown Learning identity')
        return {'record':item,'review_hash':digest(item)}
    data=json.loads(body)
    if action=='experience':
        if set(data)!={'observation_id','package'}:raise ValueError('Exact governed experience fields required')
        if (getattr(runtime,'_halt_latch',None) or getattr(runtime.context.active_thread,'halt',None) or
                getattr(runtime.context.runtime_state,'value',runtime.context.runtime_state)=='HALTED'):
            raise PermissionError('HALT prevents learning adaptation')
        from integration.interaction_learning import evaluate
        observation=runtime.runtime_observation_collector.store.load_record(owner,data['observation_id'])
        if observation is None or observation.thread_id!=runtime.context.active_thread.thread_id:
            raise PermissionError('Persisted same-thread Observation required')
        return evaluate(runtime,observation,data['package'])
    if action=='apply':
        if set(data)!={'understanding_id','version','hash'}:raise ValueError('Current task reference required')
        # Selection is thread-bound and re-resolved at prompt consumption time.
        from .relationships import resolve_context
        resolve_context(runtime,data)
        runtime._learning_application_selection=(runtime.context.active_thread.thread_id,data)
        return {'state':'SELECTED_FOR_NEXT_RESPONSE','task_reference':data,'execution_authority':False}
    if action=='verify_application':
        if set(data)!={'application_id','observation_id'}:raise ValueError('Exact application/Observation identities required')
        return manager.verify_application(runtime,**data)
    if action=='understand':
        if set(data)!={'request','approval'}:raise ValueError('Exact adoption envelope required')
        thread=runtime.context.active_thread.thread_id
        result=runtime.understanding_engine.adopt_learning(manager,owner,thread,data['request'],data['approval'])
        runtime._learned_understanding_scope=(thread,data['request']['scope'],data['request']['conditions'])
        runtime.context.learning_understanding_result=result
        return result
    if action=='architecture_change':
        from learning.architecture_changes import process
        result=process(manager,owner,data)
        for item in result['results']:
            if item['impact']!='UNAFFECTED':runtime.learning_memory_gateway.publish(owner,item['learning_id'])
        return result
    if action=='dependencies':
        from learning.architecture_changes import declare
        result=declare(manager,owner,**data)
        runtime.learning_memory_gateway.publish(owner,result['learning_id'])
        return result
    if action=='resolve':
        from learning.conflicts import resolve
        result=resolve(manager,owner,**data)
        for record in result['records']:runtime.learning_memory_gateway.publish(owner,record['learning_id'])
        return result
    if action=='revalidate':
        if set(data)-{'id','hash','trigger','outcome','new_candidate_id'}:raise ValueError('Unknown revalidation fields')
        result=manager.revalidate(owner,data['id'],data['hash'],data['trigger'],data['outcome'],data.get('new_candidate_id'))
        runtime.learning_memory_gateway.publish(owner,result['learning_id'])
        return result
    if action in {'use','use_for_build'}:
        from .contracts import validate_scope
        validate_scope(data)
        if data['operator_id']!=owner:raise PermissionError('Operator mismatch')
        if action == 'use_for_build':
            runtime._build_learning_scope=(runtime.context.active_thread.thread_id,data)
            return {'scope':data,'application':'Next matching governed build generation only; historical advisory, no execution authority'}
        runtime._learning_scope=(runtime.context.active_thread.thread_id,data)
        return {'scope':data,'application':'Next conversational prompt only; advisory authority only'}
    if action=='relate':
        if set(data)!={'candidate_id','learning_id','reason'}:raise ValueError('Exact relation fields required')
        return manager.relate(owner,**data)
    if action not in {'approve','reject','revoke','restore'} or set(data)-{'id','hash','resolution'}:
        raise ValueError('Unsupported Learning command')
    result=manager.review(owner,data['id'],data['hash'],action.upper(),data.get('resolution'))
    if result.get('learning_id') and result.get('integrity_metadata',{}).get('canonical_policy')=='2.2':
        runtime.learning_memory_gateway.publish(owner,result['learning_id'])
    return result


def capture(runtime,outcome):
    if outcome.get('build'):
        candidate=service(runtime).capture_build(runtime,outcome)
        for changed in service(runtime).consume_new_evidence(candidate):
            runtime.learning_memory_gateway.publish(runtime.context.identity.operator_id,changed['learning_id'])
        runtime.context.learning_candidate=candidate
        from learning.revalidation_sources import trigger
        manager=service(runtime)
        trigger(manager,runtime.context.identity.operator_id,'NEW_EVIDENCE',candidate['candidate_id'],candidate['scope'])
        if outcome['build']['validation_status']=='FAIL':
            with manager.store.transaction(runtime.context.identity.operator_id) as (state,_,__):
                failures={v.get('source_build_id') for v in state.values() if v.get('scope')==candidate['scope'] and v.get('outcome_state')=='FAIL'}
            if len(failures)>=2:
                for changed in trigger(manager,runtime.context.identity.operator_id,'REPEATED_EXECUTION_FAILURE',sorted(failures),candidate['scope']):
                    runtime.learning_memory_gateway.publish(runtime.context.identity.operator_id,changed['learning_id'])
        return candidate
    return None


def prompt_advisory(runtime, *, selection=None):
    selected=selection if selection is not None else getattr(runtime,'_learning_scope',None)
    if selection is None:runtime._learning_scope=None
    if selected is None or selected[0]!=runtime.context.active_thread.thread_id:return ''
    owner=runtime.context.identity.operator_id
    from learning.revalidation_sources import poll
    for changed in poll(runtime,service(runtime)):runtime.learning_memory_gateway.publish(owner,changed['learning_id'])
    for changed in service(runtime).expire_due(owner):
        runtime.learning_memory_gateway.publish(owner,changed['learning_id'])
    text,event=service(runtime).advisory(owner,selected[1],'learning-use:'+uuid4().hex)
    runtime.context.learning_influence=event
    if event:runtime._observe_runtime_event('learning_advisory',event)
    from data_governance.context_admission import Admission
    admission=Admission(owner,runtime.context.active_thread.thread_id)
    records=[service(runtime).store.get(owner,identity) for identity in event.get('learning_ids',[])]
    allowed=True
    for record in records:
        valid=bool(record and service(runtime)._canonical_active(record) and runtime.learning_memory_gateway.available(owner,record['learning_id']))
        allowed=admission.consider('LEARNING',record['learning_id'],json.dumps(record),source='LearningMemoryGateway',
            basis={'verified':valid,'governance_state':'APPROVED' if valid else 'UNKNOWN',
                   'lineage':[record['lineage']['governance_decision']['decision_id']],
                   'freshness':record['lineage']['revalidate_by'],'classification':'LEARNING_DATA',
                   'validation_state':'VALIDATED',
                   'scope':record['scope'],
                   'authority':'Governance','durability_state':'DURABLE'}) and allowed
    for excluded in event.get('excluded',[]):
        admission.consider('LEARNING',excluded['learning_id'],'',source='LearningMemoryGateway')
    admission.parts=[text] if allowed and records else []
    return admission.finish()
