from copy import deepcopy
from types import SimpleNamespace as NS
import pytest
from learning.contracts import digest,now
from data_governance.context_admission import Admission,verify,EPHEMERAL,GOVERNED
from data_governance.response_claims import extract

@pytest.mark.parametrize('kind',sorted(EPHEMERAL|GOVERNED))
def test_every_context_class_has_explicit_policy(kind):
    a=Admission('op','thread');a.consider(kind,'id','payload',source='fixture')
    p=a.finish();verify(p,'thread')
    assert p.decisions[0]['decision']==('ADMITTED' if kind in EPHEMERAL else 'EXCLUDED')
    assert ('payload' in p)==(kind in EPHEMERAL)

def test_prompt_mutation_and_direct_augmentation_blocked():
    a=Admission('op','thread');a.consider('OPERATOR_INPUT','input','Hello',source='operator')
    p=a.finish()
    with pytest.raises(PermissionError):verify(p+'unreviewed learning')
    p.decisions[0]['governance_state']='APPROVED'
    with pytest.raises(PermissionError):verify(p)
    from core.mode_controller import process_interaction
    from models.runtime_models import OperatorInput
    with pytest.raises(PermissionError):process_interaction(OperatorInput('Hello','thread',now(),'interactive_mode_bot'),reasoning_input='unreviewed')

def test_unknown_and_cross_owner_context_fail_closed():
    a=Admission('op','thread')
    assert not a.consider('LEGACY','legacy','secret',source='legacy')
    assert not a.consider('THREAD','foreign','other secret',source='thread',owner='other')
    assert str(a.finish())==''
    assert [d['decision'] for d in a.decisions]==['REVIEW_REQUIRED','BLOCKED']

def test_unknown_metadata_cannot_be_relabelled_ephemeral():
    a=Admission('op','thread')
    assert not a.consider('SESSION','id','content',source='source',basis={'governance_state':'UNKNOWN'})

def test_reasoning_stages_admit_unvalidated_proposals(monkeypatch):
    import importlib.util,sys
    from pathlib import Path
    name='governed_reasoning_test'
    spec=importlib.util.spec_from_file_location(name,Path(__file__).resolve().parents[1]/'agents/reasoning_agent.py')
    module=importlib.util.module_from_spec(spec);monkeypatch.setitem(sys.modules,name,module);spec.loader.exec_module(module)
    agent=module.ReasoningAgent.__new__(module.ReasoningAgent);agent.provider='stub';agent.model='stub'
    prompts=[]
    def call(prompt,**kwargs):
        verify(prompt,'thread');prompts.append(prompt)
        return module.ModelCallResult('Hello',NS())
    monkeypatch.setattr(agent,'_call_model',call)
    a=Admission('op','thread');a.consider('OPERATOR_INPUT','input','Hello',source='OperatorInput')
    args=dict(active_pack_name='Mode',active_mode_name='Chat',mode_definition={'purpose':'Respond','schema':[],'constraints':[]},user_input=a.finish())
    result=agent.generate(**args)
    assert len(prompts)==3 and len(result.context_admission)==3
    proposal=[d for p in prompts for d in p.decisions if d['artifact_type']=='MODEL_PROPOSAL']
    assert len(proposal)==2 and all(d['authority']=='NONE' and d['validation_state']=='UNVALIDATED' for d in proposal)
    with pytest.raises(PermissionError):agent.generate(**args,recent_context='unadmitted memory')

def test_discussion_request_can_draft_but_not_bypass_response_gate():
    from data_governance.response_gate import evaluate
    r=NS(context=NS(identity=NS(operator_id='op')))
    assert evaluate(r,'Explain the prior bounded result.')['allowed']
    assert not evaluate(r,'Explain the prior bounded result.',generated_text='The service is ready for customers.')['allowed']

@pytest.mark.parametrize('source',['interactive_mode_bot','supervisor_bridge'])
def test_both_runtime_publishers_block_unverified_output(source):
    from data_governance.response_gate import governed_interaction
    from models.runtime_models import OperatorInput,InteractionProcessingResult
    a=Admission('op','thread');a.consider('OPERATOR_INPUT','input','Hello',source='operator')
    r=NS(context=NS(identity=NS(operator_id='op'),active_thread=NS(thread_id='thread')))
    def processor(*a,**kw):return InteractionProcessingResult(True,None,'trace:1',{},False,False,'You can deploy the payment service now.',
        reasoning_id='reasoning:1',context_admission=[{'stage':'DRAFT','decisions':[]}])
    result=governed_interaction(r,OperatorInput('Hello','thread',now(),source),a.finish(),processor)
    assert not result.success and result.clarification_required
    assert 'PENDING_VALIDATION' in result.response_text
    assert result.reasoning_id=='reasoning:1' and result.trace_reference=='trace:1'
    assert result.context_admission==[{'stage':'DRAFT','decisions':[]}]

def test_full_artifact_scope_is_preserved_and_mismatch_rejected():
    a=Admission('op','thread')
    basis={'verified':True,'governance_state':'APPROVED','validation_state':'NOT_REQUIRED','classification':'UNDERSTANDING_DATA',
           'authority':'OPERATOR','lineage':['spec:1'],'scope':{'project':'p','capability':'c'}}
    assert a.consider('SPECIFICATION','spec:1','proposal',source='handoff',basis=basis)
    assert a.decisions[-1]['scope']=={'operator_id':'op','thread_id':'thread','project':'p','capability':'c'}
    basis['scope']['thread_id']='other'
    assert not a.consider('SPECIFICATION','spec:2','other',source='handoff',basis=basis)

def test_failed_generation_keeps_admission_evidence(tmp_path):
    import json
    from tests.test_execution_spine import runtime,envelope
    r=runtime(tmp_path)
    r.build_runtime.provider.agent=NS(generate=lambda **kw:NS(final_response='invalid generated JSON',context_admission=[{'stage':'DRAFT'}]))
    result=r.handle_build_request('/build '+json.dumps(envelope(tmp_path/'artifact')))
    assert result['state']=='GENERATION_FAILED'
    evidence=result['generated_contents'][-1]
    assert evidence['generation_status']=='FAILED' and evidence['context_admission']
    assert evidence['reasoning_context_admission']==[{'stage':'DRAFT'}]

def test_exact_signed_response_and_proposition_binding(tmp_path):
    from tests.test_data_governance_closure import _nonbuild_transition_fixture
    from data_governance.response_gate import evaluate
    text='The measured addition is five.'
    r=_nonbuild_transition_fixture(tmp_path,text)
    r.context.assembled_context=NS(runtime=NS(context_ready=True))
    r.context.material_response_claim={'operator_input_hash':digest('Verify this result'),'claim_id':r.context.reality_primacy_result['request']['claim_id']}
    assert evaluate(r,'Verify this result',generated_text=text)['allowed']
    assert not evaluate(r,'Verify this result',generated_text='The measured addition is six.')['allowed']

def test_thread_cannot_launder_governed_artifact():
    from context_assembly.context_assembler import ContextAssembler
    from context_orchestration.context_source import ContextSource
    thread=NS(operator_id='op',thread_id='t',title='conversation',messages=[
        NS(role='assistant',content='revoked lesson',metadata={'learning_id':'revoked'}),
        NS(role='user',content='Hello',metadata={})])
    plan=NS(included_sources=lambda:[ContextSource.THREAD_MEMORY],missing_sources=lambda:[],context_ready=lambda:True,source_selections=[])
    context=ContextAssembler().assemble(NS(operator_id='op'),thread,None,'LISTENING',plan)
    prompt=context.to_prompt_context()
    assert 'revoked lesson' not in prompt and 'Hello' in prompt
    assert any(d['decision']=='EXCLUDED' and d['artifact_type']=='RETRIEVED' for d in prompt.decisions)
    context.thread.recent_messages[0].content='late injection'
    with pytest.raises(PermissionError):context.to_prompt_context()

CONSEQUENTIAL=[
 'You can deploy the payment service now.','Go ahead and ship it.',"You're clear to deploy.",
 'Push this to production.','This is ready for customers.','Nothing else blocks release.',
 'You have approval to proceed.','The migration is safe to run.','Delete the old records now.',
 'The capability is operational.','The service passed validation.','You can rely on this result.',
 'Transfer the balance to the vendor.','You may release the funds.','The account is compliant.',
 'Authorize the refund.','Approve the purchase.','Sign the agreement.','Finalize the settlement.',
 'The audit has established compliance.','Erase the backup.','Overwrite the customer table.',
 'Rotate the production secret.','Grant the service administrator privileges.','Disable the access check.',
 'Publish the private report.','Send the notification to every customer.','Merge the patch now.',
 'Execute the database migration.','Revoke the old credentials.','The encryption is effective.',
 'The system supports confidential data.','You should purchase the shares.','You must remove the restriction.',
 'We can finalize the contract.','They may access the archive.','The capability remains available.',
 'The device is safe.','The trial passed its acceptance test.','You have permission to continue.',
 'The evidence proves the outcome.','Release the reserved inventory.','Commit the transaction.',
 'Update the production configuration.','Deactivate the retention policy.','The result is accurate.',
 'The application is authorized.','The installation requires no further review.','The records are disposable.',
 'You could distribute the dataset.']
BENIGN=(['What does "'+phrase.rstrip('.')+'" mean?' for phrase in CONSEQUENTIAL[:20]]+
        ['How do you define "'+phrase.rstrip('.')+'"?' for phrase in CONSEQUENTIAL[20:30]]+
        ['Let us discuss "'+phrase.rstrip('.')+'" as an example.' for phrase in CONSEQUENTIAL[30:40]]+
        ['Hello!','Hi.','Good morning.','Good afternoon.','Good evening.','Thanks!','Thank you.',"You're welcome.",'Goodbye.','How can I help?'])

@pytest.mark.parametrize('text',CONSEQUENTIAL)
def test_consequential_response_never_defaults_to_nonmaterial(text):
    result=extract(text,{'operator_id':'op','thread_id':'t'})
    assert result['state']!='NON_MATERIAL'
    from data_governance.response_gate import evaluate
    r=NS(context=NS(identity=NS(operator_id='op'),active_thread=NS(thread_id='t')))
    assert not evaluate(r,'Hello',generated_text=text)['allowed']
    assert all(c['rp_required'] and c['validation_state']=='PENDING_VALIDATION' for c in result['claims'])

@pytest.mark.parametrize('text',BENIGN)
def test_metalinguistic_control_does_not_assert_quoted_proposition(text):
    result=extract(text,{'operator_id':'op','thread_id':'t'})
    assert result['state']=='NON_MATERIAL' and result['claims']==[]

def test_unknown_structure_is_not_safe_and_claim_binding_changes():
    from data_governance.response_gate import evaluate
    r=NS(context=NS(identity=NS(operator_id='op')))
    # Operator law: unknown wording alone is not a consequential decision.
    assert evaluate(r,'Hello',generated_text='🟢🚀')['allowed']
    assert extract('Hello',{})['state']=='NON_MATERIAL'
    assert extract('You may publish the report.',{})['claims']!=extract('You may publish all reports.',{})['claims']
    assert extract('What does "deploy" mean? Delete the records.',{})['state']!='NON_MATERIAL'

def test_materiality_vocabulary_is_distinct():
    examples={'Hello':'NON_MATERIAL','Evidence supports the hypothesis.':'MATERIAL_CLAIM',
        'You should pause.':'MATERIAL_RECOMMENDATION','You may proceed.':'MATERIAL_AUTHORIZATION_IMPLICATION',
        'Delete the copies.':'MATERIAL_EXECUTION_INSTRUCTION','The service is operational.':'MATERIAL_STATE_ASSERTION',
        '🟢🚀':'UNKNOWN_MATERIALITY'}
    for text,state in examples.items():assert extract(text,{})['state']==state

def event(kind='subsystem',identity='calculator'):
    e={'change_id':'change-1','changed_entities':[{'type':kind,'id':identity}],
       'previous_state':'v1','new_state':'v2','scope':{'operator_id':'operator','project':'project'},
       'implementation_refs':['operator-review:change-1'],'evidence':['approved-diff:change-1'],
       'timestamp':now(),'dependency_references':[]}
    e['authority']={'operator_id':'operator','decision':'APPROVE','change_hash':digest(e)}
    return e

@pytest.mark.parametrize('kind',sorted(__import__('learning.architecture_changes',fromlist=['ENTITY_TYPES']).ENTITY_TYPES))
def test_all_dependency_entity_types_propagate(kind):
    from learning.architecture_changes import impact
    r={'scope':{'operator_id':'operator','project':'project'},'lineage':{'dependency_graph':{
        'dependencies':[{'type':kind,'id':'calculator'}],'edges':[],'complete':False}}}
    assert impact(r,event(kind))[0]=='AFFECTED'
    assert impact(r,event(kind,'unknown'))[0]=='REVIEW_REQUIRED'
    other=event(kind);other['scope']['project']='unrelated'
    assert impact(r,other)[0]=='UNAFFECTED'

def test_interface_transitive_dependency_and_complete_unrelated():
    from learning.architecture_changes import impact
    graph={'dependencies':[{'type':'component','id':'consumer'}],
           'edges':[{'dependent':{'type':'component','id':'consumer'},'dependency':{'type':'interface','id':'api'}}],
           'complete':True,'source_refs':['review']}
    graph['governance']={'graph_hash':digest(graph)}
    r={'scope':{'operator_id':'operator','project':'project'},'lineage':{'dependency_graph':graph}}
    assert impact(r,event('interface','api'))[0]=='AFFECTED'
    assert impact(r,event('interface','other'))[0]=='UNAFFECTED'
    graph['source_refs'].append('unreviewed-change')
    assert impact(r,event('interface','other'))[0]=='REVIEW_REQUIRED'

def test_governed_change_lifecycle_history_and_receipt(tmp_path,monkeypatch):
    from tests.test_learning import built,approve
    from learning.runtime import service
    from learning.architecture_changes import process,declare
    r,_,c=built(tmp_path);record=approve(r,c);manager=service(r)
    record=declare(manager,'operator',record['learning_id'],digest(record),[{'type':'subsystem','id':'calculator'}],[],True,['operator-review'])
    e=event();e['scope']=record['scope'];e['authority']['change_hash']=digest({k:v for k,v in e.items() if k!='authority'})
    assert manager.store.get('operator',record['learning_id'])['status']=='APPROVED'
    before=len(manager.store.history('operator'))
    original=manager.revalidate
    def interrupted(*a,**k):raise RuntimeError('simulated interruption')
    monkeypatch.setattr(manager,'revalidate',interrupted)
    with pytest.raises(RuntimeError):process(manager,'operator',e)
    assert manager.store.get('operator',record['learning_id'])['status']=='APPROVED'
    assert any(h['kind']=='architecture_change_plan' for h in manager.store.history('operator'))
    monkeypatch.setattr(manager,'revalidate',original)
    receipt=process(manager,'operator',e)
    assert receipt['results'][0]['impact']=='AFFECTED'
    assert manager.store.get('operator',record['learning_id'])['status']=='SUSPENDED'
    assert len(manager.store.history('operator'))>before
    assert process(manager,'operator',e)==receipt
    altered=deepcopy(e);altered['new_state']='v3'
    with pytest.raises(PermissionError):process(manager,'operator',altered)
