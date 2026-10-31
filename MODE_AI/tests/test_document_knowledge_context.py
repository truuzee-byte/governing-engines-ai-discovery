import base64
import hashlib
import json
from types import SimpleNamespace as NS
from specs.document_service import DocumentService
from knowledge.runtime_context import select,prompt_context
from system_layer.contracts import digest


def test_binary_source_decodes_into_context_with_exact_byte_and_record_lineage(tmp_path):
    docs=DocumentService(tmp_path/'content_custody.sqlite3');text='Specific original source café.';raw=text.encode()
    encoded=json.dumps(dict(schema_version='DocumentBinary/1',format='UTF8_TEXT',encoding='BASE64',
        data=base64.b64encode(raw).decode(),sha256=hashlib.sha256(raw).hexdigest()))
    req=dict(object_id='document',content=encoded,kind='DRAFT',visual_authority='NOT_APPLICABLE',knowledge_class='EXTERNAL',
        source_reference='operator:file',authority='operator',project_id='p',thread_id='t',expected_previous=None,validation_references=[])
    record=docs.intake('op',req,dict(operator_id='op',action='DOCUMENT_INTAKE',decision='APPROVE',hash=digest(req)))
    runtime=NS(context=NS(identity=NS(operator_id='op'),active_thread=NS(thread_id='t')),
        understanding_engine=NS(store=NS(path=tmp_path/'meaning.db')))
    select(runtime,[dict(object_id='document',version=1,expected_hash=record['record_hash'],knowledge_class='EXTERNAL')])
    result=str(prompt_context(runtime))
    assert text in result and base64.b64encode(raw).decode() not in result
    assert record['record_hash'] in result and hashlib.sha256(raw).hexdigest() in result
    assert 'EXTERNAL' in result and 'python:utf-8-strict' in result
    assert docs.retrieve('op','document',1,record['record_hash'])['content']==encoded
    exported=docs.export('op','document',1,record['record_hash'],'TEXT')
    assert exported['content']==text
    assert exported['source_transformation']=='EXTRACTED_TEXT'
    assert exported['extraction']['binary_sha256']==hashlib.sha256(raw).hexdigest()
    assert 'segments' not in exported['extraction']
    archived=json.loads(docs.export('op','document',1,record['record_hash'],'JSON')['content'])
    assert archived['content']==encoded
    found=docs.search('op','original source café','p')
    assert found['search_completeness']=='COMPLETE_FOR_SELECTED_NAMESPACE'
    assert found['matches'][0]['reference']['expected_hash']==record['record_hash']
    assert found['matches'][0]['matched_fields']==['extracted_content']
    assert found['matches'][0]['content_extraction']['binary_sha256']==hashlib.sha256(raw).hexdigest()


def test_unreadable_document_search_preserves_missingness(tmp_path):
    docs=DocumentService(tmp_path/'docs.db')
    req=dict(object_id='broken',content=json.dumps(dict(schema_version='DocumentBinary/1',format='UTF8_TEXT',encoding='BASE64',
        data='broken',sha256='0'*64)),kind='DRAFT',visual_authority='NOT_APPLICABLE',knowledge_class='EXTERNAL',
        source_reference='operator:file',authority='operator',project_id='p',thread_id='t',expected_previous=None,validation_references=[])
    record=docs.intake('op',req,dict(operator_id='op',action='DOCUMENT_INTAKE',decision='APPROVE',hash=digest(req)))
    result=docs.search('op','unavailable phrase','p')
    assert result['matches']==[] and result['search_completeness']=='PARTIAL_CONTENT_UNAVAILABLE'
    assert result['unavailable_content'][0]['reference']['expected_hash']==record['record_hash']
