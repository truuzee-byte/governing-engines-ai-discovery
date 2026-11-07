import hashlib
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace as NS
import pytest
from frontend.server import RuntimeViewServer
from memory.thread_memory import ThreadMemory
from system_layer.contracts import digest


@pytest.mark.parametrize('bad',[False,True])
@pytest.mark.parametrize('large',[False,True])
def test_exact_download_or_hash_rejection_without_runtime_execution(bad,large):
    thread=ThreadMemory.create('op');content='Exact exported café\n'
    if large:content*=5000
    checksum=hashlib.sha256(content.encode()).hexdigest()
    result=dict(contract='DocumentExport/1',state='SERIALIZED',content=content,
        rendered_output_observed=False,byte_length=len(content.encode()),sha256='0'*64 if bad else checksum,format='TEXT')
    operation=dict(contract='ModeOperationView/1',command='/documents',state='RETURNED',error_type=None,
        operator_id='op',thread_id=thread.thread_id,result=result,execution_authority=False)
    operation['view_hash']=digest(operation)
    runtime=NS(context=NS(identity=NS(operator_id='op'),active_thread=thread,runtime_state='IDLE',operation_view=operation))
    view=RuntimeViewServer(runtime)
    dependencies=Path(os.environ.get('MODE_NODE_RUNTIME', 'optional-node-runtime'))
    try:
        outcome=subprocess.run([str(dependencies/'bin/node.exe'),str(Path(__file__).with_name('frontend_export_smoke.cjs'))],
            env=dict(os.environ,NODE_PATH=str(dependencies/'node_modules'),MODE_VIEW_TEST_URL=view.url,
                MODE_EXPORT_BAD='1' if bad else '0',MODE_EXPORT_LARGE='1' if large else '0',MODE_EXPORT_HASH=checksum),capture_output=True,text=True,timeout=40)
        assert outcome.returncode==0,'Local export fixture failed; private URL omitted'
    finally:view.close()


def test_retained_export_cannot_cross_thread_or_reconstruct_replaced_result():
    from frontend.runtime_view import operation_export
    thread=ThreadMemory.create('op');content='exact'
    result=dict(contract='DocumentExport/1',state='SERIALIZED',content=content,byte_length=5,sha256=hashlib.sha256(content.encode()).hexdigest())
    operation=dict(operator_id='op',thread_id=thread.thread_id,result=result)
    operation['view_hash']=digest(operation)
    runtime=NS(context=NS(identity=NS(operator_id='op'),active_thread=thread,operation_view=operation))
    assert operation_export(runtime,operation['view_hash'],expected_owner='op')[0]==b'exact'
    runtime.context.active_thread=ThreadMemory.create('op')
    with pytest.raises(PermissionError):operation_export(runtime,operation['view_hash'],expected_owner='op')
    runtime.context.active_thread=thread;runtime.context.operation_view=None
    with pytest.raises(PermissionError):operation_export(runtime,operation['view_hash'],expected_owner='op')


def test_selected_document_queues_existing_export_with_exact_source(tmp_path):
    from specs.document_service import DocumentService
    from integration.content_custody import command
    import json
    docs=DocumentService(tmp_path/'content_custody.sqlite3');thread=ThreadMemory.create('op')
    request=dict(object_id='source',content='<exact source>',kind='DRAFT',visual_authority='NOT_APPLICABLE',
        knowledge_class='INTERNAL',source_reference='operator:file',authority='operator',project_id='p',
        thread_id=thread.thread_id,expected_previous=None,validation_references=[])
    record=docs.intake('op',request,dict(operator_id='op',action='DOCUMENT_INTAKE',decision='APPROVE',hash=digest(request)))
    operation=dict(contract='ModeOperationView/1',command='/documents',state='RETURNED',error_type=None,
        operator_id='op',thread_id=thread.thread_id,result=record,execution_authority=False)
    operation['view_hash']=digest(operation)
    runtime=NS(context=NS(identity=NS(operator_id='op'),active_thread=thread,runtime_state='IDLE',operation_view=operation),
        understanding_engine=NS(store=NS(path=tmp_path/'meaning.db')))
    view=RuntimeViewServer(runtime,operator_input=True)
    deps=Path(os.environ.get('MODE_NODE_RUNTIME', 'optional-node-runtime'))
    try:
        outcome=subprocess.run([str(deps/'bin/node.exe'),str(Path(__file__).with_name('frontend_export_request_smoke.cjs'))],
            env=dict(os.environ,NODE_PATH=str(deps/'node_modules'),MODE_VIEW_TEST_URL=view.url),capture_output=True,text=True,timeout=40)
        assert outcome.returncode==0,'Local export request fixture failed'
        queued=view.next_input()
        assert json.loads(queued[len('/documents export '):])==dict(object_id='source',version=1,expected_hash=record['record_hash'],format='HTML')
        result=command(runtime,queued)
        assert '&lt;exact source&gt;' in result['content']
        assert result['source_reference']['expected_hash']==record['record_hash']
        assert not result['rendered_output_observed']
    finally:view.close()
