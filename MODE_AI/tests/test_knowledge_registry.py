import json
import pytest
from knowledge.registry import KnowledgeRegistry
from specs.document_service import DocumentService
from understanding import UnderstandingEngine, UnderstandingRequest, AuthorityContext, AuthorityLevel
from understanding.understanding_store import UnderstandingStore
from understanding.understanding_record import Evidence, normalize_meaning
from system_layer.contracts import digest


def approve(request):
    return dict(operator_id='op',action='KNOWLEDGE_REGISTER',decision='APPROVE',hash=digest(request))


def setup(tmp_path,pool='INTERNAL'):
    store=UnderstandingStore(tmp_path/'understanding.sqlite3')
    docs=DocumentService(tmp_path/'content_custody.sqlite3')
    text='The operator defines a reusable source term.'
    source=dict(object_id='document',content=text,kind='DRAFT',visual_authority='NOT_APPLICABLE',
        knowledge_class=pool,source_reference='operator:definition',authority='operator',project_id='p',thread_id='t',
        expected_previous=None,validation_references=[])
    saved=docs.intake('op',source,dict(operator_id='op',action='DOCUMENT_INTAKE',decision='APPROVE',hash=digest(source)))
    result=UnderstandingEngine(store).process(UnderstandingRequest('op','t',text,project_id='p',
        interpreted_input={'subject_id':'term','meaning':text,'semantic_domain':'OPERATOR','source_references':[saved['record_hash']]},
        authority_context=AuthorityContext('op',AuthorityLevel.AUTHORIZED_OPERATOR,'OPERATOR',authenticated=True),
        evidence=(Evidence(saved['record_hash'],'OPERATOR_STATEMENT',True,'OPERATOR',normalize_meaning(text)),)))
    meaning=result.to_dict()['final_understanding']
    assert meaning is not None,result.to_dict()
    request=dict(knowledge_id='term',pool=pool,knowledge_type='DEFINITION',semantic_domain='OPERATOR',
        project_id='p',thread_id='t',sources=[dict(object_id='document',version=1,expected_hash=saved['record_hash'])],
        understanding_reference=dict(understanding_id=meaning['understanding_id'],version=meaning['version'],expected_hash=digest(meaning)),
        author='operator',organization='Governing Engines',authority_scope='project:p',visibility='OWNER_SCOPED',
        lifecycle='CANDIDATE',temporal_scope={'from':None,'until':None},fresh_until=None,applicability=['p'],
        exclusions=[],unresolved=[],related_knowledge=[],conflicts=[],expected_previous=None)
    return KnowledgeRegistry(docs.store.path,store),request


@pytest.mark.parametrize('pool',['SYSTEM','INTERNAL','EXTERNAL'])
def test_actual_understanding_to_versioned_knowledge_preserves_boundaries(tmp_path,pool):
    registry,request=setup(tmp_path,pool)
    record=registry.register('op',request,approve(request))
    got=registry.retrieve('op','term',1,record['record_hash'])
    assert got['knowledge']['request']['pool']==pool
    assert got['knowledge']['rp_state']=='PENDING_VALIDATION'
    assert not got['claims_validated']
    assert got['knowledge']['source_lineage'][0]['source_pool']==pool
    assert registry.search('op','term','p')['matches']
    with pytest.raises(FileNotFoundError):registry.retrieve('other','term',1,record['record_hash'])
    request.update(expected_previous=record['record_hash'],lifecycle='DEPRECATED')
    second=registry.register('op',request,approve(request))
    assert second['version']==2
    assert registry.retrieve('op','term',1,record['record_hash'])['knowledge']['request']['lifecycle']=='CANDIDATE'


def test_missing_lineage_and_pool_change_fail_closed(tmp_path):
    registry,request=setup(tmp_path)
    with pytest.raises(PermissionError):registry.register('op',request,{})
    first=registry.register('op',request,approve(request))
    request.update(expected_previous=first['record_hash'],pool='SYSTEM')
    with pytest.raises(PermissionError):registry.register('op',request,approve(request))
    request['pool']='INTERNAL';request['understanding_reference']['expected_hash']='bad'
    with pytest.raises(ValueError):registry.register('op',request,approve(request))


def test_conflict_edges_and_expiry_survive_search_without_authority_promotion(tmp_path):
    registry,request=setup(tmp_path)
    first=registry.register('op',request,approve(request))
    reference=dict(knowledge_id='term',version=1,expected_hash=first['record_hash'])
    request.update(knowledge_id='other-term',conflicts=[reference],fresh_until='2000-01-01T00:00:00+00:00')
    second=registry.register('op',request,approve(request))
    edges=registry.relationships('op','other-term',1,second['record_hash'])
    assert edges['edges'][0]['reference']==reference
    assert not edges['conflicts_resolved'] and not edges['claims_validated']
    matches=registry.search('op','other-term','p')['matches']
    assert matches[0]['freshness']=='EXPIRED'
    assert matches[0]['availability']=='REVIEW_REQUIRED'
    assert matches[0]['authority_status']=='NOT_RECONCILED'


@pytest.mark.parametrize('change',[
    {'lifecycle':'CONFIRMED'}, {'pool':'PUBLIC'}, {'visibility':'EVERYONE'},
    {'fresh_until':'2026-09-14'}, {'temporal_scope':{'from':'2026-01-02T00:00:00Z','until':'2026-01-01T00:00:00Z'}},
    {'rp_state':'CONFIRMED'}])
def test_registration_rejects_unknown_authority_and_malformed_time(tmp_path,change):
    registry,request=setup(tmp_path);request.update(change)
    with pytest.raises((ValueError,PermissionError)):
        registry.register('op',request,approve(request))
    assert registry.store.history('KNOWLEDGE','op','term')==[]


def test_missing_understanding_is_explicit_and_cannot_enter_context(tmp_path,monkeypatch):
    registry,request=setup(tmp_path)
    record=registry.register('op',request,approve(request))
    monkeypatch.setattr(registry.understanding_store,'get',lambda *a:None)
    value=registry.retrieve('op','term',1,record['record_hash'])
    assert value['state']=='UNAVAILABLE_SOURCE' and value['unavailable_understanding']
    assert not value['claims_validated']


def test_meaning_index_reconstructs_from_versions_without_cross_pool_inference(tmp_path):
    registry,request=setup(tmp_path)
    first=registry.register('op',request,approve(request))
    meaning=json.loads(first['content'])['canonical_meaning']
    lookup=registry.meaning_lookup('op','  '+meaning.upper()+'  ','OPERATOR','p','INTERNAL')
    assert lookup['references']==[dict(knowledge_id='term',version=1,expected_hash=first['record_hash'])]
    assert lookup['match_method']=='UNDERSTANDING_NORMALIZED_EXACT' and not lookup['automatically_selected']
    assert registry.meaning_lookup('op',meaning,'OPERATOR','p','SYSTEM')['references']==[]
    assert registry.meaning_lookup('op',meaning,'OPERATOR','other','INTERNAL')['references']==[]
    request.update(expected_previous=first['record_hash'],lifecycle='ARCHIVED')
    second=registry.register('op',request,approve(request))
    current=registry.meaning_lookup('op',meaning,'OPERATOR','p','INTERNAL')
    assert current['references'][0]['version']==2
    assert current['records'][0]['knowledge']['request']['lifecycle']=='ARCHIVED'
    assert len(registry.meaning_lookup('op',meaning,'OPERATOR','p','INTERNAL',include_history=True)['references'])==2


def test_registered_meaning_reaches_context_once_with_provenance(tmp_path):
    from types import SimpleNamespace as NS
    from integration.content_custody import command
    from knowledge.runtime_context import prompt_context
    registry,request=setup(tmp_path)
    runtime=NS(context=NS(identity=NS(operator_id='op'),active_thread=NS(thread_id='t')),
        understanding_engine=NS(store=registry.understanding_store))
    record=command(runtime,'/knowledge register '+json.dumps({'request':request,'approval':approve(request)}))
    ref=dict(knowledge_id='term',version=1,expected_hash=record['record_hash'])
    command(runtime,'/knowledge record_context '+json.dumps({'project_id':'p','references':[ref,ref]}))
    prompt=prompt_context(runtime)
    assert len(prompt.decisions)==1
    assert 'The operator defines a reusable source term.' in prompt
    assert 'PENDING_VALIDATION' in prompt and 'INTERNAL' in prompt
    assert prompt_context(runtime) is None
    command(runtime,'/knowledge record_context '+json.dumps({'project_id':'p','references':[ref]}))
    runtime.context.active_thread.thread_id='other'
    with pytest.raises(PermissionError):prompt_context(runtime)
    runtime.context.active_thread.thread_id='t'
    command(runtime,'/knowledge record_context '+json.dumps({'project_id':'p','references':[ref]}))
    with pytest.raises(FileNotFoundError):
        command(runtime,'/knowledge authority_context '+json.dumps({'scope_id':'missing','version':1,'expected_hash':'bad'}))
    assert prompt_context(runtime) is None
