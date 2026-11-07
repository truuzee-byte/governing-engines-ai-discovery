import os
import subprocess
from pathlib import Path
from types import SimpleNamespace as NS
import pytest
from frontend.server import RuntimeViewServer
from memory.thread_memory import ThreadMemory
from integration.content_custody import command
from system_layer.contracts import digest


@pytest.mark.parametrize('collection',['vault','knowledge'])
@pytest.mark.parametrize('open_source',[False,True,'history'])
def test_selected_reference_reaches_context_without_reclassification(tmp_path,collection,open_source):
    from memory.vault import Vault
    from specs.document_service import DocumentService
    from knowledge.retrieval import KnowledgeRetrieval
    path=tmp_path/'content_custody.sqlite3';thread=ThreadMemory.create('op')
    request=dict(object_id='source',content='Operator selected exact source.',kind='DRAFT',source_reference='operator:source',
        authority='operator',project_id='project',thread_id=thread.thread_id,expected_previous=None)
    if collection=='vault':
        request['kind']='CANON';service=Vault(path);action='VAULT_PRESERVE';write=service.preserve
    else:
        request.update(visual_authority='NOT_APPLICABLE',validation_references=[],knowledge_class='EXTERNAL')
        service=DocumentService(path);action='DOCUMENT_INTAKE';write=service.intake
    original=write('op',request,dict(operator_id='op',action=action,decision='APPROVE',hash=digest(request)))
    if open_source=='history':
        newer=dict(request,content='A different revision',expected_previous=original['record_hash'])
        write('op',newer,dict(operator_id='op',action=action,decision='APPROVE',hash=digest(newer)))
    search=(service if collection=='vault' else KnowledgeRetrieval(path)).search('op','selected','project')
    operation=dict(contract='ModeOperationView/1',command='/'+collection,state='RETURNED',error_type=None,
        operator_id='op',thread_id=thread.thread_id,result=search,execution_authority=False);operation['view_hash']=digest(operation)
    runtime=NS(context=NS(identity=NS(operator_id='op'),active_thread=thread,runtime_state='IDLE',operation_view=operation),
        understanding_engine=NS(store=NS(path=tmp_path/'meaning.db')))
    view=RuntimeViewServer(runtime,operator_input=True)
    dependencies=Path(os.environ.get('MODE_NODE_RUNTIME', 'optional-node-runtime'))
    try:
        result=subprocess.run([str(dependencies/'bin/node.exe'),str(Path(__file__).with_name('frontend_source_selection_smoke.cjs'))],
            env=dict(os.environ,NODE_PATH=str(dependencies/'node_modules'),MODE_VIEW_TEST_URL=view.url,
                MODE_OPEN_SOURCE='1' if open_source is True else '0',MODE_SEARCH_HISTORY='1' if open_source=='history' else '0',
                MODE_SOURCE_COLLECTION=collection),capture_output=True,text=True,timeout=40)
        assert result.returncode==0,'Local source selection failed; private URL omitted'
        selected=command(runtime,view.next_input())
        if open_source=='history':
            assert selected['include_history'] is True
            assert len(selected['matches'])==1 and selected['matches'][0]['record_position']=='HISTORICAL_VERSION'
            assert selected['matches'][0]['reference']['expected_hash']==original['record_hash']
            return
        if collection=='vault':from memory.vault_context import prompt_context
        else:from knowledge.runtime_context import prompt_context
        if open_source:
            assert selected['record_hash']==search['matches'][0]['reference']['expected_hash']
            assert selected['content']==request['content']
            assert prompt_context(runtime) is None
            return
        assert selected['state']=='SELECTED_FOR_NEXT_RESPONSE'
        material=prompt_context(runtime)
        assert request['content'] in str(material)
        if collection=='knowledge':assert 'EXTERNAL' in str(material)
        assert prompt_context(runtime) is None
    finally:view.close()
