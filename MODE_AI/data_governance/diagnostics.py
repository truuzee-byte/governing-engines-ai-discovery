"""Read existing state only. No approval, revalidation, creation or recovery on inspect."""
from collections import Counter
from data_governance.learning_governance import prerequisites

def inspect(runtime,identity=None):
    owner=runtime.context.identity.operator_id
    report={'operator_id':owner,'subsystems':{},'records':{},'broken_prerequisites':[],
        'lineage_failures':[],'recovery_required':[],'performance':{'measurement':None,'reason':'No duration measurement supplied'},
        'context':getattr(runtime.context,'learning_influence',None),'response_gate':getattr(runtime.context,'response_governance',None)}
    manager=getattr(runtime,'learning_service',None)
    if manager:
        try:
            history=manager.store.history(owner);state={h['entity']:h['value'] for h in history if h['kind'] in {'record','candidate'}}
            report['subsystems']['learning']=dict(Counter(v.get('status',v.get('candidate_status')) for v in state.values()))
            report['records']=state if identity is None else {identity:state.get(identity)}
            report['governance']=[h['value'] for h in history if h['kind']=='governance']
            report['revalidation']=[h['value'] for h in history if h['kind']=='revalidation_trigger']
            report['evaluations']=[h['value'] for h in history if h['kind']=='evaluation']
            report['architecture_changes']=[h['value'] for h in history if h['kind']=='architecture_change']
            completed={h['entity'] for h in history if h['kind']=='architecture_change'}
            report['pending_architecture_changes']=[h['value'] for h in history if h['kind']=='architecture_change_plan' and h['entity'][:-5] not in completed]
            if report['pending_architecture_changes']:report['recovery_required'].append('Resume incomplete governed architecture change')
            report['context_history']=[h['value'] for h in history if h['kind']=='influence']
            report['artifact_metadata']=[{'id':h['entity'],'metadata':h.get('governed_metadata')} for h in history]
            for key,value in state.items():
                if 'candidate_id' in value:
                    reasons=prerequisites(value)
                    if reasons:report['broken_prerequisites'].append({'id':key,'reasons':reasons})
            if identity and identity in state:
                record=state[identity];report['explainability']=record.get('lineage',{})
                report['version_history']=[h for h in history if h['entity']==identity]
                chain=record.get('lineage',{}).get('canonical_v2',{})
                report['missing_links']=[name for name in ('outcome_analysis','eligibility','classification','confidence','reality_validation') if not chain.get(name)]
                gateway=getattr(runtime,'learning_memory_gateway',None)
                report['learning_memory_versions']=gateway.history(owner,identity) if gateway else []
                if not report['learning_memory_versions']:report['missing_links'].append('Persistent Memory export')
        except Exception as exc:report['lineage_failures'].append(str(exc));report['recovery_required'].append('Learning journal requires inspection')
    else:report['subsystems']['learning']='NOT_INITIALIZED'
    memory=getattr(runtime,'persistent_memory_manager',None)
    report['context_admission']=getattr(runtime.context,'context_admission',None)
    if memory:
        try:
            records=memory.store.load_records_for_operator(owner,include_inactive=True)
            report['subsystems']['memory']=dict(Counter(r.status.value for r in records))
            report['memory']=[{'record':r.to_dict(),'versions':memory.store.history(owner,r.memory_id)} for r in records if identity is None or identity==r.memory_id]
            report['memory_context_history']=memory.store.uses(owner)
            for record in records:
                if not record.governance_decision:report['broken_prerequisites'].append({'id':record.memory_id,'reasons':['Legacy memory has no v2 governance approval']})
        except Exception as exc:report['lineage_failures'].append(str(exc));report['recovery_required'].append('Memory journal requires inspection')
    observation=getattr(runtime.context,'runtime_observation',None)
    if observation:
        report['runtime_observation']=observation.to_dict()
        report['performance']={'execution_time':getattr(observation,'execution_time',None),'source':observation.observation_id}
    report['runtime_state']=getattr(getattr(runtime.context,'runtime_state',None),'value',None)
    return report
