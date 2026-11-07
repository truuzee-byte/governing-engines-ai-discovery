"""Synthetic operator protocols measured by real RP/Learning/U/Memory owners.

No model is mocked and no provider is invoked: this exercises the deterministic
structured learning path, not language-model behavior or real-world success.
"""
from copy import deepcopy
from datetime import datetime,timezone,timedelta
from pathlib import Path
from types import SimpleNamespace as NS
from uuid import uuid4
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from understanding import UnderstandingEngine,UnderstandingStore,UnderstandingRequest,AuthorityContext,AuthorityLevel
from understanding.understanding_record import Evidence,normalize_meaning,digest as semantic_digest
from runtime_observation import RuntimeObservationCollector
from runtime_observation.observation_store import RuntimeObservationStore
from memory.thread_store import ThreadStore
from integration.reality_primacy import RealityAcceptanceClient
from learning.contracts import digest
from learning.runtime import command,service


def runtime(root,thread=None):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    threads=ThreadStore(str(root/'threads'))
    if thread is None:thread=threads.create_thread('operator',title='Synthetic learning task')
    return NS(context=NS(identity=NS(operator_id='operator'),active_thread=thread,runtime_state='INTERPRETING'),
        thread_store=threads,understanding_engine=UnderstandingEngine(UnderstandingStore(root/'understanding.sqlite3')),
        runtime_observation_collector=RuntimeObservationCollector(store=RuntimeObservationStore(root/'observations')))


def context(objective='Prepare the archive handover',topic='archive',intent='conditional_request'):
    return {'objective':objective,'conditions':['Only after '+topic+' approval'],
            'constraints':['Never publish '+topic+' without authorization'],'intent':intent,'topic':topic}


def response(c,correct=True):
    return {'objective':c['objective'],'conditions':deepcopy(c['conditions']) if correct else [],
            'constraints':deepcopy(c['constraints']) if correct else [],
            'decision':('discuss' if c['intent']=='question' else 'conditional_proposal') if correct else 'unconditional_plan'}


def observe(c,p):
    # Independent synthetic protocol checks the author's actual declared
    # conditions/constraints. It does not ask a test assertion whether it passed.
    correct=(p.get('objective')==c['objective'] and p.get('conditions')==c['conditions'] and
             p.get('constraints')==c['constraints'] and
             p.get('decision')==('discuss' if c['intent']=='question' else 'conditional_proposal'))
    return {'accepted':correct,'retained_conditions':p.get('conditions'),'retained_constraints':p.get('constraints')}


def evidence(scope,intent='conditional_request'):
    cases=[]
    for c in [context(intent=intent),context('Plan the lunar greenhouse delivery','greenhouse',intent)]:
        controls={'context_hash':digest(c)};bad=response(c,False);good=response(c)
        contrast={'protocol':'controlled_intervention/1','variable':'interpretation',
            'baseline':{'input':bad,'output':observe(c,bad),'controls':controls},
            'intervention':{'input':good,'output':observe(c,good),'controls':controls},
            'recovery':{'input':bad,'output':observe(c,bad),'controls':controls},'controls':controls,'unresolved':[]}
        cases.append({'context':c,'contrast':contrast,'observation_kind':'OBSERVED'})
    return {'improvement_target':'INTERPRETATION_CORRECTNESS','causal_contrast':cases[0]['contrast'],
        'relational_evidence':{'contract':'RelationalEvidence/1','scope':scope,'signature':{'intent':intent},'cases':cases}}


def task(r,c,subject=None,project='synthetic-goals'):
    meaning='Operator task: '+c['objective']
    result=r.understanding_engine.process(UnderstandingRequest('operator',r.context.active_thread.thread_id,meaning,
        project_id=project,interpreted_input={'subject_id':subject or uuid4().hex,'semantic_domain':'OPERATOR',
            'meaning':meaning,'objective':c['objective'],'constraints':c['constraints'],
            'context':{'learning_application_context':c}},
        evidence=(Evidence('operator:'+digest(c),'OPERATOR_STATEMENT',True,'OPERATOR',normalize_meaning(meaning)),),
        authority_context=AuthorityContext('operator',AuthorityLevel.AUTHORIZED_OPERATOR,'OPERATOR',True)))
    assert not result.errors and not result.review_required,result.to_dict()
    return result.final_understanding,result.governed_handoff()


def reference(head):return {'understanding_id':head.understanding_id,'version':head.version,'hash':semantic_digest(head)}


def signed_observation(r,root,head,governed,properties,extra_scope=None,observed=True):
    # Use external RP's actual contract resolver, pinned source validator,
    # coordinator, decision ledger, Show Chain and signing endpoint.
    from test_evidence_validation import case,engine
    from test_decision_coordinator import authority
    from reality_primacy import RPClaim,RPTruthCondition,resolve_evidence_requirements,DecisionCoordinator,DecisionLedger,TransitionEndpoint
    now=datetime.now(timezone.utc);stamp=now.isoformat();identity=uuid4().hex
    resolution,item=case(kind='OPERATOR_STATEMENT',subject_kind='OPERATOR_MEANING')
    scope={'operator_id':'operator','thread_id':r.context.active_thread.thread_id,'project':head.project_id,
           'domain':'OPERATOR','capability':'Preserve declared task intent',**(extra_scope or {})}
    claim=deepcopy(resolution.claim_snapshot);claim.update(claim_id='claim:'+identity,scope=scope,
        source_state='INTERPRETING',proposed_target_state='COMPLETE',source_understanding=governed)
    condition=deepcopy(resolution.condition_snapshots[0]);condition.update(claim_id=claim['claim_id'],scope=scope)
    resolution=resolve_evidence_requirements(RPClaim.from_dict(claim),[RPTruthCondition.from_dict(condition)])
    req=resolution.requirements[0]
    item.update(claim_id=claim['claim_id'],scope=scope,condition_id=req['condition_id'],requirement_id=req['requirement_id'],
                observed_at=stamp,content={'observed':observed,'properties':deepcopy(properties)})
    item['content_hash']=digest(item['content'])
    batch=engine(resolution,[item]).validate(resolution,[item],evaluated_at=stamp)
    policy=authority(resolution,batch);policy.update(valid_from=(now-timedelta(seconds=5)).isoformat(),
                                                   valid_until=(now+timedelta(minutes=5)).isoformat())
    coordinator=DecisionCoordinator(ledger=DecisionLedger(Path(root)/('reality-'+identity+'.sqlite3')),issuer='external-rp',
        governed_authority_hashes=[digest(policy)],trusted_batch_hashes=[batch.content_hash()])
    key=Ed25519PrivateKey.generate();endpoint=TransitionEndpoint(coordinator,key,key_id='synthetic-external',clock=lambda:stamp)
    r.reality_acceptance_client=RealityAcceptanceClient(endpoint.evaluate,{'synthetic-external':key.public_key().public_bytes(
        serialization.Encoding.Raw,serialization.PublicFormat.Raw)})
    request={'request_id':'experience:'+identity,'claim_id':claim['claim_id'],'scope':scope,'source_state':'INTERPRETING',
        'target_state':'COMPLETE','evaluated_at':stamp,'evaluation':{'resolution':resolution.to_dict(),'batch':batch.to_dict(),'authority':policy}}
    rp=r.reality_acceptance_client.evaluate(request)
    assert rp['rp_state'] in {'CONFIRMED','DISCONFIRMED'},rp
    observation=r.runtime_observation_collector.collect(operator_id='operator',thread_id=r.context.active_thread.thread_id,
        input_text='Synthetic authorized interpretation consequence',runtime_state_start='INTERPRETING',runtime_state_end='INTERPRETING',
        metadata={'observed_outcome':{'rp':rp},'validation_results':[{'rp_state':rp['rp_state']}],
                  'produced_receipts':[rp['receipt_id']]})
    assert not observation.collection_errors,observation.to_dict()
    return observation,{'scope':{k:scope[k] for k in ('operator_id','project','domain','capability')},
                        'outcome':{'rp':rp,'understanding':governed}}


def acquire(root,intent='conditional_request'):
    r=runtime(root);head,governed=task(r,context(intent=intent))
    scope={'operator_id':'operator','project':head.project_id,'domain':'OPERATOR','capability':'Preserve declared task intent'}
    properties=evidence(scope,intent)
    observation,package=signed_observation(r,root,head,governed,properties)
    evaluation=command(r,'/learning experience '+__import__('json').dumps({'observation_id':observation.observation_id,'package':package}))
    assert evaluation['status']=='ELIGIBLE',evaluation
    identity=evaluation['candidate_ids'][0];candidate=service(r).store.get('operator',identity)
    record=command(r,'/learning approve '+__import__('json').dumps({'id':identity,'hash':digest(candidate)}))
    request={'learning_id':record['learning_id'],'learning_hash':digest(record),'scope':scope,
        'conditions':properties['causal_contrast']['controls'],'thread_id':r.context.active_thread.thread_id,'expected_version':0}
    adoption=command(r,'/learning understand '+__import__('json').dumps({'request':request,'approval':{
        'operator_id':'operator','action':'LEARNING_UNDERSTANDING_UPDATE','decision':'APPROVE','hash':digest(request)}}))
    return r,record,adoption,observation,properties
