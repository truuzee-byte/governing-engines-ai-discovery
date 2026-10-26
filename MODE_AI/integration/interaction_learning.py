"""All-interaction evaluation using governed outputs; missing evidence yields zero candidates."""
from copy import deepcopy
from learning.contracts import LearningCandidate,digest,now
from learning.runtime import service
from integration.learning_prerequisites import prepare_chain

def evaluate(runtime,observation,package=None):
    manager=service(runtime);owner=runtime.context.identity.operator_id
    event={'observation_id':observation.observation_id,'dimensions_evaluated':['CORRECTNESS','OUTCOME','OPERATOR','SYSTEM'],
        'candidate_ids':[],'status':'PENDING_VALIDATION','reasons':[],'timestamp':now()}
    if package is None:
        event['reasons']=['No complete governed Understanding/RP/causal evidence package']
    else:
        scope=deepcopy(package['scope']);out=deepcopy(package['outcome']);governed=out['understanding']
        if scope['operator_id']!=owner or observation.operator_id!=owner:raise PermissionError('Interaction owner mismatch')
        persisted=runtime.runtime_observation_collector.store.load_record(owner,observation.observation_id)
        if persisted.to_dict()!=observation.to_dict():raise ValueError('Observation substitution')
        if observation.observed_outcome.get('rp')!=out['rp'] and observation.observed_outcome!=out['rp']:
            raise ValueError('Observation is not linked to this RP outcome')
        source=runtime.understanding_engine.store.get(owner,governed['understanding_id'],governed['version'])
        chain=prepare_chain(runtime,out,observation,source,governed,scope)
        if chain['rp_complete']:
            from learning.revalidation_sources import trigger
            kind='CONTRADICTORY_EVIDENCE' if out['rp']['rp_state']=='DISCONFIRMED' else 'NEW_EVIDENCE'
            for changed in trigger(manager,owner,kind,out['rp']['decision_id'],scope):
                runtime.learning_memory_gateway.publish(owner,changed['learning_id'])
        event['reasons']=chain['blocked_reasons']
        if not event['reasons'] and chain['eligibility']['status']=='ELIGIBLE':
            identity='candidate:'+digest([owner,governed['understanding_hash'],out['rp']['decision_id'],scope])
            claim={'statement':'Bounded governed interaction improvement','rp_claim':out['rp']['request']['evaluation']['resolution']['claim_snapshot'],
                'rp_state':out['rp']['rp_state'],'learning_recommendation':chain['classification']['recommendation'],
                'generalization':'NONE','execution_authority':False}
            dimension=chain['classification']['dimensions'][0]
            category={'CORRECTNESS':'INTERPRETATION_CORRECTION','OPERATOR':'OPERATOR_CORRECTION','OUTCOME':'EXECUTION_SUCCESS','SYSTEM':'CAPABILITY_GAP'}[dimension]
            candidate=LearningCandidate(identity,category,claim,scope,[observation.observation_id],[source.understanding_id],None,None,
                out['rp']['decision_id'],list(chain['outcome_analysis']['supporting_evidence']),
                {'canonical_v2':chain,'outcome':out,'observation':observation.to_dict(),'understanding_source':governed,'contradicts':[]},
                'governed_interaction','BOUNDED',[],'VALIDATED','SUPPORTED',now(),'ELIGIBLE').to_dict()
            with manager.store.transaction(owner) as (state,_,append):
                if identity not in state:append(identity,'candidate',candidate,capture_runtime=runtime)
            event.update(status='ELIGIBLE',candidate_ids=[identity])
    with manager.store.transaction(owner) as (_,__,append):append('evaluation:'+digest(event),'evaluation',event)
    runtime.context.learning_evaluation=event
    return event

def consume_transition(runtime,observation,outcome):
    """Called by normal Mode state acceptance after external RP consumption."""
    request=outcome.get('request',{});signed_scope=request.get('scope',{})
    if signed_scope.get('build_id'):return None  # canonical build capture owns this event
    if not all(k in signed_scope for k in ('operator_id','project','domain','capability')):return evaluate(runtime,observation)
    try:governed=request['evaluation']['resolution']['claim_snapshot']['source_understanding']
    except KeyError:return evaluate(runtime,observation)
    return evaluate(runtime,observation,{'scope':{k:signed_scope[k] for k in ('operator_id','project','domain','capability')},
        'outcome':{'rp':outcome,'understanding':governed}})
