from copy import deepcopy
import pytest
from tests.test_learning import built,approve
from learning.runtime import service,command,prompt_advisory
from learning.contracts import digest
from learning.canonical import classify,confidence
from data_governance.learning_governance import decide
from outcome_analysis import OutcomeAnalysisEngine,OutcomeAnalysisRecord
import json

@pytest.mark.parametrize('field,value',[('rp_complete',False),('understanding_complete',False),('observation_complete',False),('semantic_continuity','UNKNOWN'),('semantic_continuity','UNRESOLVED')])
def test_operator_cannot_override_prerequisites(tmp_path,field,value):
    r,_,c=built(tmp_path)
    c['lineage']['canonical_v2'][field]=value
    assert decide(c,'operator',True).decision=='REJECTED'

@pytest.mark.parametrize('state',['UNKNOWN','UNRESOLVED'])
def test_root_cause_string_is_not_sufficient(tmp_path,state):
    r,_,c=built(tmp_path)
    c['lineage']['canonical_v2']['outcome_analysis'].update(root_cause_state=state,root_cause={'description':'a filled string'})
    assert decide(c,'operator',True).decision=='REJECTED'

@pytest.mark.parametrize('raw',[{}, {'observation':'raw'}, {'understanding':'unvalidated'}, {'approved':True}])
def test_memory_rejects_raw_learning(tmp_path,raw):
    r,_,c=built(tmp_path)
    with pytest.raises(PermissionError):r.learning_memory_gateway.publish('operator',raw)
    assert not r.learning_memory_gateway.available('operator',c['candidate_id'])

def test_governance_rejects_durability(tmp_path):
    r,_,c=built(tmp_path)
    decision=decide(c,'operator',False)
    assert decision.decision=='REJECTED'
    command(r,'/learning reject '+json.dumps({'id':c['candidate_id'],'hash':digest(c)}))
    assert service(r).retrieve('operator',c['scope'])==[]
    assert not r.learning_memory_gateway.available('operator',c['candidate_id'])

def test_complete_chain_and_memory_custody(tmp_path):
    r,_,c=built(tmp_path);record=approve(r,c)
    chain=record['lineage']['canonical_v2']
    assert chain['eligibility']['status']=='ELIGIBLE' and not chain['eligibility']['durability_authority']
    assert chain['semantic_continuity']=='STABLE'
    assert chain['outcome_analysis']['root_cause_state']=='SUPPORTED'
    assert chain['classification']['dimensions']==['OUTCOME']
    assert chain['confidence']['state']=='SUPPORTED'
    assert r.learning_memory_gateway.available('operator',record['learning_id'])
    command(r,'/learning use '+json.dumps(c['scope']))
    assert record['learning_id'] in prompt_advisory(r)
    use=r.context.learning_influence
    assert use['considered']==use['selected']==use['injected']==[record['learning_id']]
    assert use['excluded']==[]
    assert all(chain['outcome_analysis']['prerequisite_refs'].values())

@pytest.mark.parametrize('trigger,outcome',[('NEW_EVIDENCE','SUSPEND'),('CONTRADICTORY_EVIDENCE','DEPRECATE'),('ARCHITECTURE_CHANGE','ARCHIVE'),('OPERATOR_PREFERENCE_CHANGE','REMOVE'),('GOVERNANCE_POLICY_CHANGE','SUSPEND'),('RP_INVALIDATION','SUSPEND'),('REPEATED_EXECUTION_FAILURE','SUSPEND'),('PERIODIC_REVIEW','SUSPEND')])
def test_revalidation_stops_obsolete_influence(tmp_path,trigger,outcome):
    r,_,c=built(tmp_path);record=approve(r,c)
    result=command(r,'/learning revalidate '+json.dumps({'id':record['learning_id'],'hash':digest(record),'trigger':trigger,'outcome':outcome}))
    assert result['lineage']['revalidation_history'][-1]['governance_decision']['decision']=='APPROVED'
    assert service(r).retrieve('operator',c['scope'])==[]
    assert not r.learning_memory_gateway.available('operator',record['learning_id'])

@pytest.mark.parametrize('target,dimension',[('INTERPRETATION_CORRECTNESS','CORRECTNESS'),('RUNTIME_OUTCOME','OUTCOME'),('OPERATOR_CONTINUITY','OPERATOR'),('RUNTIME_ARCHITECTURE','SYSTEM')])
def test_four_dimensions_have_evidence_basis(target,dimension):
    analysis={'status':'COMPLETE','supporting_evidence':['e'],'scope':{'operator_id':'operator'},'analysis_id':'oa',
        'root_cause':{'variable':'controlled','contrast':{'controls':{'constant':1}}}}
    result=classify(analysis,[{'evidence_id':'e','content':{'properties':{'improvement_target':target}}}])
    assert result['dimensions']==[dimension] and result['recommendation']
    assert classify(analysis,[])['dimensions']==[]

def test_confidence_deduplicates_and_decreases():
    first=confidence(['one'],[])
    repeated=confidence(['one','one'],[],first['history'])
    assert repeated['state']=='SUPPORTED'
    corroborated=confidence(['one','two'],[],repeated['history'])
    assert corroborated['state']=='CORROBORATED'
    contradicted=confidence(['one','two'],['counter'],corroborated['history'])
    assert contradicted['state']=='CONTRADICTED' and len(contradicted['history'])==4

@pytest.mark.parametrize('evidence',[[],[{'evidence_id':'e','content':{'properties':{'root_cause':'because failure'}}}]])
def test_outcome_analysis_does_not_invent_cause(evidence):
    result=OutcomeAnalysisEngine().analyze(operator='operator',scope={},observation={'observation_id':'o'},understanding={'understanding_id':'u'},
        validated_reality={'completed':True,'decision_id':'rp'},measurements=evidence)
    assert result.root_cause_state=='UNKNOWN' and result.status=='PENDING'
    assert OutcomeAnalysisRecord(**result.to_dict())==result

@pytest.mark.parametrize('action',['MAINTAIN','UPDATE'])
def test_new_evidence_revalidation_preserves_chain(tmp_path,action):
    import shutil
    r,_,c=built(tmp_path);record=approve(r,c)
    shutil.rmtree(tmp_path/'artifact')
    r,_,new=built(tmp_path)
    result=command(r,'/learning revalidate '+json.dumps({'id':record['learning_id'],'hash':digest(record),
        'trigger':'NEW_EVIDENCE','outcome':action,'new_candidate_id':new['candidate_id']}))
    assert result['lineage']['canonical_v2']['confidence']['state']=='CORROBORATED'
    assert r.learning_memory_gateway.available('operator',record['learning_id'])
    assert len(result['lineage']['revalidation_history'])==1
    # Reviews after renewal must retain the renewed evidence, including restart.
    from learning.store import LearningStore
    from learning.service import LearningService
    reopened=LearningService(LearningStore(service(r).store.path))
    revoked=reopened.review('operator',record['learning_id'],digest(result),'REVOKE')
    restored=reopened.review('operator',record['learning_id'],digest(revoked),'RESTORE')
    assert restored['lineage']['canonical_v2']==result['lineage']['canonical_v2']
    assert reopened.retrieve('operator',restored['scope'])

def test_new_rp_invalidation_suspends_without_inventing_cause(tmp_path):
    import shutil
    r,_,c=built(tmp_path);record=approve(r,c)
    shutil.rmtree(tmp_path/'artifact')
    r,_,counter=built(tmp_path,'disconfirmed')
    assert counter['candidate_status']=='PENDING_VALIDATION'
    current=service(r).store.get('operator',record['learning_id'])
    assert current['status']=='SUSPENDED'
    assert current['lineage']['canonical_v2']['confidence']['state']=='CONTRADICTED'
    assert current['lineage']['revalidation_history'][-1]['initiator']=='POLICY'
    assert not r.learning_memory_gateway.available('operator',record['learning_id'])

def test_legacy_approval_is_quarantined(tmp_path):
    r,_,c=built(tmp_path);record=approve(r,c)
    record['integrity_metadata'].pop('canonical_policy')
    with service(r).store.transaction('operator') as (_,__,append):append(record['learning_id'],'record',record)
    assert service(r).retrieve('operator',c['scope'])==[]
    assert service(r).retrieve('operator',c['scope'],include_inactive=True)
    with pytest.raises(PermissionError):service(r).review('operator',record['learning_id'],digest(record),'RESTORE')

def test_expired_evidence_blocks_approval_and_memory_use(tmp_path):
    r,_,c=built(tmp_path);record=approve(r,c)
    c['lineage']['outcome']['rp']['authority_valid_until']='2000-01-01T00:00:00+00:00'
    assert decide(c,'operator',True).decision=='REJECTED'
    record['lineage']['revalidate_by']='2000-01-01T00:00:00+00:00'
    with service(r).store.transaction('operator') as (_,__,append):append(record['learning_id'],'record',record)
    assert not r.learning_memory_gateway.available('operator',record['learning_id'])
    command(r,'/learning use '+json.dumps(c['scope']))
    assert prompt_advisory(r)==''
    current=service(r).store.get('operator',record['learning_id'])
    assert current['status']=='SUSPENDED'
    assert current['lineage']['revalidation_history'][-1]['trigger']=='PERIODIC_REVIEW'

def test_unvalidated_controlled_data_cannot_supply_root_cause(tmp_path):
    r,_,c=built(tmp_path)
    chain=c['lineage']['canonical_v2'];a=chain['outcome_analysis']
    result=OutcomeAnalysisEngine().analyze(operator='operator',scope=c['scope'],
        observation={'observation_id':a['prerequisite_refs']['observation_id']},
        understanding={'understanding_id':a['prerequisite_refs']['understanding_id']},
        validated_reality=chain['reality_validation'],measurements=[{'evidence_id':'raw','content':{'properties':{'causal_contrast':a['root_cause']['contrast']}}}])
    assert result.status=='PENDING' and result.root_cause_state=='UNKNOWN'

@pytest.mark.parametrize('field,value',[('review_required',True),('final_understanding',None),('errors',['incomplete'])])
def test_incomplete_understanding_export_cannot_supply_completion(tmp_path,field,value):
    from integration.learning_prerequisites import prepare_chain
    r,out,c=built(tmp_path)
    governed=deepcopy(out['understanding']);governed['result'][field]=value
    source=r.understanding_engine.store.get('operator',governed['understanding_id'],governed['version'])
    observation=r.runtime_observation_collector.store.load_record('operator',out['observation_ids'][-1])
    result=prepare_chain(r,out,observation,source,governed,c['scope'])
    assert not result['understanding_complete']
    assert result['eligibility']['status']=='PENDING_VALIDATION'
    assert result['classification']['dimensions']==[]
    assert result['outcome_analysis']['status']=='PENDING'
