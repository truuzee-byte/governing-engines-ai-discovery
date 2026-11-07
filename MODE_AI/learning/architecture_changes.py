"""Governed change events and dependency closure, independent of file mtimes."""
from copy import deepcopy
from learning.contracts import digest,now,validate_scope

ENTITY_TYPES={'subsystem','component','capability','interface','runtime_path','specification','governance_policy',
              'evidence_source','rp_claim','context_surface','memory_behavior','execution_behavior'}

def entity(value):
    if not isinstance(value,dict) or set(value)!={'type','id'} or value['type'] not in ENTITY_TYPES or not isinstance(value['id'],str) or not value['id'].strip():
        raise ValueError('Unknown dependency entity')
    return value['type']+':'+value['id']

def derive(record):
    """Source-backed references only. Derived coverage is explicitly incomplete."""
    outcome=record.get('lineage',{}).get('outcome',{})
    deps=[{'type':'capability','id':record['scope']['capability']},
          {'type':'context_surface','id':'learning_advisory'},
          {'type':'memory_behavior','id':'LearningMemoryGateway'}]
    for value in record.get('evidence',[]):deps.append({'type':'evidence_source','id':value})
    claim=record.get('lesson',{}).get('rp_claim') or {}
    if claim.get('claim_id'):deps.append({'type':'rp_claim','id':claim['claim_id']})
    spec=outcome.get('specification') or {}
    if spec.get('spec_id'):deps.append({'type':'specification','id':spec['spec_id']})
    for component in spec.get('structure',{}).get('approved_components',[]):
        if isinstance(component,str):deps.append({'type':'component','id':component})
    policy=record.get('lineage',{}).get('governance_decision',{}).get('policy_basis')
    if policy:deps.append({'type':'governance_policy','id':policy})
    if record.get('lineage',{}).get('canonical_v2',{}).get('understanding_complete'):
        deps.append({'type':'interface','id':'GovernedUnderstanding/1.2'})
    if outcome.get('build'):
        deps.extend([{'type':'subsystem','id':'Builder'},{'type':'runtime_path','id':'ModeRuntime.handle_build_request'},
                     {'type':'execution_behavior','id':'BuilderValidation'}])
    return {'dependencies':deps,'edges':[],'complete':False,'basis':'Preserved source lineage; undeclared dependencies remain unknown'}

def declare(manager,owner,identity,expected_hash,dependencies,edges,complete,source_refs):
    if type(complete) is not bool or not source_refs or not all(isinstance(s,str) and s for s in source_refs):raise ValueError('Explicit dependency authority required')
    keys={entity(d) for d in dependencies}
    for edge in edges:
        if set(edge)!={'dependent','dependency'}:raise ValueError('Malformed dependency edge')
        entity(edge['dependent']);entity(edge['dependency'])
    with manager.store.transaction(owner) as (state,_,append):
        record=deepcopy(state[identity])
        if digest(record)!=expected_hash:raise ValueError('Stale dependency review')
        combined={entity(d):deepcopy(d) for d in derive(record)['dependencies']+dependencies}
        graph={'dependencies':list(combined.values()),'edges':deepcopy(edges),'complete':complete,'source_refs':source_refs}
        decision={'decision_id':'dependencies:'+digest([identity,expected_hash,graph]),'operator_id':owner,'subject_id':identity,
                  'decision':'APPROVED','action':'DECLARE_DEPENDENCIES','source_hash':expected_hash,'graph_hash':digest(graph),'timestamp':now()}
        record['lineage']['dependency_graph']={**graph,'governance':decision};record['updated_at']=now()
        append(decision['decision_id'],'dependency_governance',decision);append(identity,'record',record)
    return record

def impact(record,event):
    if any(record['scope'][k]!=v for k,v in event['scope'].items()):return 'UNAFFECTED',[]
    graph=record.get('lineage',{}).get('dependency_graph') or derive(record)
    refs={entity(d) for d in graph['dependencies']};edges=graph['edges']+event['dependency_references']
    changed={entity(d) for d in event['changed_entities']}
    while True:
        expanded=changed|{entity(e['dependent']) for e in edges if entity(e['dependency']) in changed}
        if expanded==changed:break
        changed=expanded
    matches=sorted(refs & changed)
    if matches:return 'AFFECTED',matches
    # Complete declarations are content-bound to their operator decision.
    unsigned={k:v for k,v in graph.items() if k!='governance'}
    if graph.get('complete') and graph.get('governance',{}).get('graph_hash')==digest(unsigned):return 'UNAFFECTED',[]
    return 'REVIEW_REQUIRED',[]

def process(manager,owner,event):
    required={'change_id','changed_entities','previous_state','new_state','scope','implementation_refs','evidence','authority','timestamp','dependency_references'}
    if type(event) is not dict or set(event)!=required:raise ValueError('Exact ArchitectureChangeEvent contract required')
    if not event['changed_entities'] or not event['implementation_refs'] or not event['evidence']:raise ValueError('Change provenance required')
    if not event['change_id'] or not event['previous_state'] or not event['new_state']:raise ValueError('Change identity/version required')
    for value in event['changed_entities']:entity(value)
    for edge in event['dependency_references']:
        if set(edge)!={'dependent','dependency'}:raise ValueError('Invalid change dependency')
        entity(edge['dependent']);entity(edge['dependency'])
    if not event['scope'] or event['scope'].get('operator_id')!=owner or set(event['scope'])-{'operator_id','project','domain','capability'}:
        raise PermissionError('Change owner/scope mismatch')
    from datetime import datetime,timezone
    stamp=datetime.fromisoformat(event['timestamp'])
    if stamp.tzinfo is None or stamp>datetime.now(timezone.utc):raise ValueError('Invalid change timestamp')
    body={k:v for k,v in event.items() if k!='authority'}
    auth=event['authority']
    if auth!={'operator_id':owner,'decision':'APPROVE','change_hash':digest(body)}:raise PermissionError('Exact operator authorization required')
    if event['previous_state']==event['new_state']:raise ValueError('No change established')
    event_id='architecture:'+event['change_id']
    with manager.store.transaction(owner) as (state,history,append):
        previous=next((h['value'] for h in history if h['entity']==event_id),None)
        if previous:
            if previous['event']!=event:raise ValueError('Change ID reused with different content')
            return previous
        pending=next((h['value'] for h in history if h['entity']==event_id+':plan'),None)
        if pending:
            if pending['event']!=event:raise ValueError('Pending change identity mismatch')
            records=deepcopy(pending['records'])
        else:
            records=[deepcopy(v) for v in state.values() if v.get('status')=='APPROVED' and 'learning_id' in v]
            append(event_id+':plan','architecture_change_plan',{'event':deepcopy(event),'records':records,'state':'PROCESSING'})
    results=[]
    for record in records:
        result,paths=impact(record,event)
        item={'learning_id':record['learning_id'],'impact':result,'dependency_matches':paths,'prior_hash':digest(record)}
        if result!='UNAFFECTED':
            current=manager.store.get(owner,record['learning_id'])
            prior_events=current['lineage'].get('revalidation_history',[])
            resumed=next((h for h in prior_events if h['initiator']=='GOVERNED_CHANGE:'+event['change_id']),None)
            if resumed:
                changed=current
            else:
                changed=manager.revalidate(owner,record['learning_id'],digest(record),'GOVERNANCE_POLICY_CHANGE' if any(e['type']=='governance_policy' for e in event['changed_entities']) else 'ARCHITECTURE_CHANGE','SUSPEND',initiator='GOVERNED_CHANGE:'+event['change_id'])
            item['governance_decision']=(resumed or changed['lineage']['revalidation_history'][-1])['governance_decision']
            item['result_hash']=digest(changed)
        results.append(item)
    receipt={'receipt_id':'change-receipt:'+digest([event,results]),'event':deepcopy(event),'results':results,
             'automatic_replacement':False,'timestamp':now()}
    with manager.store.transaction(owner) as (_,__,append):append(event_id,'architecture_change',receipt)
    return receipt
