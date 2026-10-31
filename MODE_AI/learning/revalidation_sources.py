"""Observed change triggers request review; they never manufacture replacement evidence."""
from dataclasses import asdict,is_dataclass
from learning.contracts import digest,now

def trigger(manager,operator,kind,reference,scope=None):
    allowed={'NEW_EVIDENCE','CONTRADICTORY_EVIDENCE','ARCHITECTURE_CHANGE','OPERATOR_PREFERENCE_CHANGE',
        'GOVERNANCE_POLICY_CHANGE','RP_INVALIDATION','REPEATED_EXECUTION_FAILURE'}
    if kind not in allowed or not reference:raise ValueError('Governed trigger source required')
    identity='trigger:'+digest([operator,kind,reference,scope])
    with manager.store.transaction(operator) as (state,history,append):
        if any(h['entity']==identity for h in history):return []
        affected=[v for v in state.values() if v.get('status')=='APPROVED' and (scope is None or v['scope']==scope) and
            (kind!='OPERATOR_PREFERENCE_CHANGE' or 'OPERATOR' in v.get('lineage',{}).get('canonical_v2',{}).get('classification',{}).get('dimensions',[]))]
        append(identity,'revalidation_trigger',{'trigger':kind,'source':reference,'scope':scope,'timestamp':now(),
            'affected':[v['learning_id'] for v in affected],
            'proposed_outcome':'REQUEST_ADDITIONAL_EVIDENCE' if kind=='NEW_EVIDENCE' else 'SUSPEND',
            'evidence_comparison':'New source requires review; no truth or replacement inferred'})
    if kind=='NEW_EVIDENCE':return []
    return [manager.revalidate(operator,r['learning_id'],digest(r),kind,'SUSPEND',initiator='POLICY') for r in affected]

def poll(runtime,manager):
    owner=runtime.context.identity.operator_id
    profile=getattr(runtime.context,'profile',None);preferences=getattr(profile,'operator_managed',None)
    preferences=asdict(preferences) if is_dataclass(preferences) else vars(preferences) if preferences is not None else {}
    memory=getattr(runtime,'persistent_memory_manager',None)
    memory_versions=[] if memory is None else [(r.memory_id,r.version) for r in memory.store.load_records_for_operator(owner,include_inactive=True)]
    # Filesystem differences are not governed architecture or policy events.
    # Those enter through architecture_changes.process with exact authorization.
    snapshot={'OPERATOR_PREFERENCE_CHANGE':digest([preferences,memory_versions])}
    with manager.store.transaction(owner) as (_,history,append):
        previous=next((h['value'] for h in reversed(history) if h['kind']=='environment'),None)
        if previous==snapshot:return []
        append('environment:'+digest(snapshot),'environment',snapshot)
    changed=[]
    if previous:
        for kind,value in snapshot.items():
            if previous.get(kind)!=value:changed.extend(trigger(manager,owner,kind,value))
    return changed
