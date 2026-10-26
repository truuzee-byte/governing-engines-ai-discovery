from types import SimpleNamespace as NS
import pytest
from frontend.runtime_view import snapshot
from memory.thread_memory import ThreadMemory
from knowledge.retrieval import KnowledgeRetrieval
from specs.document_service import DocumentService
from system_layer.contracts import digest

def test_runtime_projection_only_exposes_conversation():
    thread=ThreadMemory.create('op');thread.add_message('user','hello');thread.add_message('system','private prompt')
    runtime=NS(context=NS(identity=NS(operator_id='op'),active_thread=thread,runtime_state='CLARIFYING',secret='not exposed'))
    value=snapshot(runtime)
    assert value['state']=='CLARIFYING' and len(value['messages'])==1
    assert 'private prompt' not in str(value) and 'secret' not in value
    runtime.context.identity.operator_id='other'
    with pytest.raises(PermissionError):snapshot(runtime)

def test_knowledge_preserves_version_conflict_and_missingness(tmp_path):
    path=tmp_path/'custody.db';docs=DocumentService(path)
    request=dict(object_id='spec',content='first',kind='SPECIFICATION',visual_authority='NOT_APPLICABLE',source_reference='operator:1',
                 authority='operator',project_id='p',thread_id='t',expected_previous=None,validation_references=[],knowledge_class='INTERNAL')
    def put(r):return docs.intake('op',r,dict(operator_id='op',action='DOCUMENT_INTAKE',decision='APPROVE',hash=digest(r)))
    a=put(request);b=put(dict(request,content='second',expected_previous=a['record_hash']))
    refs=[dict(object_id='spec',version=r['version'],expected_hash=r['record_hash'],knowledge_class='INTERNAL') for r in (a,b)]
    refs.append(dict(refs[0],object_id='missing'))
    result=KnowledgeRetrieval(path).retrieve('op',refs+[refs[0]])
    assert len(result['entries'])==3 and result['conflicting_versions']==['spec']
    assert [x['state'] for x in result['entries']]==['UNPROVEN','UNPROVEN','UNAVAILABLE_SOURCE']
    assert result['entries'][0]['record']['content']=='first'
    with pytest.raises(ValueError):KnowledgeRetrieval(path).retrieve('op',[dict(refs[0],expected_hash='wrong')])
    with pytest.raises(PermissionError):KnowledgeRetrieval(path).retrieve('op',[dict(refs[0],knowledge_class='EXTERNAL')])
