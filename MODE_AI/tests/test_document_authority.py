import pytest
from specs.document_service import DocumentService
from knowledge.retrieval import KnowledgeRetrieval
from system_layer.contracts import digest

def approved(action,request):return dict(operator_id='op',action=action,decision='APPROVE',hash=digest(request))

def test_authority_conflict_supersession_and_claim_boundary(tmp_path):
    docs=DocumentService(tmp_path/'store.db');refs=[]
    for key in ('a','b'):
        req=dict(object_id=key,content='Different definition '+key,kind='SPECIFICATION',visual_authority='NOT_APPLICABLE',
                 knowledge_class='INTERNAL',source_reference='operator:'+key,authority='operator',project_id='p',thread_id='t',
                 expected_previous=None,validation_references=[])
        record=docs.intake('op',req,approved('DOCUMENT_INTAKE',req))
        refs.append(dict(object_id=key,version=1,expected_hash=record['record_hash']))
    request=dict(scope_id='project-definition',state='CONFLICT',references=refs,rationale='Two differing definitions',expected_previous=None)
    a=docs.reconcile_authority('op',request,approved('DOCUMENT_AUTHORITY',request))
    knowledge=KnowledgeRetrieval(tmp_path/'store.db')
    result=knowledge.resolve_authority('op','project-definition',1,a['record_hash'])
    assert result['state']=='CONFLICT' and len(result['sources'])==2
    request.update(state='CURRENT_AUTHORITY',references=refs[:1],rationale='Operator selected a',expected_previous=a['record_hash'])
    with pytest.raises(PermissionError):docs.reconcile_authority('op',request,{})
    b=docs.reconcile_authority('op',request,approved('DOCUMENT_AUTHORITY',request))
    assert knowledge.resolve_authority('op','project-definition',1,a['record_hash'])['state']=='SUPERSEDED_AUTHORITY'
    current=knowledge.resolve_authority('op','project-definition',2,b['record_hash'])
    assert current['state']=='CURRENT_AUTHORITY' and current['claims_validated'] is False
    assert current['execution_authority'] is False
    with pytest.raises(FileNotFoundError):knowledge.resolve_authority('other','project-definition',2,b['record_hash'])
