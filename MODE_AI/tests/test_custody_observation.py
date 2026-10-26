import json
from types import SimpleNamespace as NS
import pytest
from integration.content_custody import execute
from system_layer.contracts import digest


def test_command_success_and_failure_keep_actual_outcome_without_private_content(tmp_path):
    events=[]
    runtime=NS(context=NS(identity=NS(operator_id='op')),understanding_engine=NS(store=NS(path=tmp_path/'meaning.db')),
        _observe_runtime_event=lambda name,payload,**kwargs:events.append((name,payload,kwargs)))
    request=dict(object_id='private',content='Private original fact',kind='CANON',project_id='p',thread_id='t',
                 source_reference='operator:1',authority='operator',expected_previous=None)
    approval=dict(operator_id='op',action='VAULT_PRESERVE',decision='APPROVE',hash=digest(request))
    record=execute(runtime,'/vault preserve '+json.dumps(dict(request=request,approval=approval)))
    assert events[-1][1]['record_references']==[record['record_hash']]
    assert events[-1][1]['state']=='COMPLETED' and request['content'] not in str(events)
    with pytest.raises(PermissionError):execute(runtime,'/vault preserve '+json.dumps(dict(request=request,approval={})))
    assert events[-1][1]['state']=='REJECTED' and events[-1][2]['runtime_error']=='PermissionError'


def test_thread_creation_requires_approval_and_records_exact_stored_reference(tmp_path):
    from memory.thread_store import ThreadStore
    events=[];store=ThreadStore(str(tmp_path/'threads'))
    runtime=NS(context=NS(identity=NS(operator_id='op')),thread_store=store,
        _observe_runtime_event=lambda name,payload,**kwargs:events.append(payload))
    request={'title':'Independent conversation'}
    with pytest.raises(PermissionError):execute(runtime,'/thread create '+json.dumps({'request':request,'approval':{}}))
    assert store.list_threads('op')==[]
    approval={'operator_id':'op','action':'THREAD_CREATE','decision':'APPROVE','hash':digest(request)}
    created=execute(runtime,'/thread create '+json.dumps({'request':request,'approval':approval}))
    reference=events[-1]['thread_reference']
    assert reference['expected_hash']==digest(store.load_thread('op',reference['thread_id']).to_dict())
    assert events[-1]['record_references']==[created['thread_hash']]


def test_document_extraction_observation_preserves_mechanism_and_segment_identity(tmp_path):
    import base64,hashlib
    from specs.document_service import DocumentService
    events=[];runtime=NS(context=NS(identity=NS(operator_id='op')),
        understanding_engine=NS(store=NS(path=tmp_path/'meaning.db')),
        _observe_runtime_event=lambda name,payload,**kwargs:events.append(payload))
    text='Private extracted source text';raw=text.encode()
    request=dict(object_id='document',content=json.dumps(dict(schema_version='DocumentBinary/1',format='UTF8_TEXT',
        encoding='BASE64',data=base64.b64encode(raw).decode(),sha256=hashlib.sha256(raw).hexdigest())),
        kind='DRAFT',visual_authority='NOT_APPLICABLE',knowledge_class='EXTERNAL',source_reference='operator:file',
        authority='operator',project_id='p',thread_id='t',expected_previous=None,validation_references=[])
    docs=DocumentService(tmp_path/'content_custody.sqlite3')
    record=docs.intake('op',request,dict(operator_id='op',action='DOCUMENT_INTAKE',decision='APPROVE',hash=digest(request)))
    result=execute(runtime,'/documents extract_text '+json.dumps(dict(object_id='document',version=1,expected_hash=record['record_hash'],project_id='p')))
    evidence=events[-1]['extraction_evidence']
    assert evidence['source_record_hash']==record['record_hash']
    assert evidence['mechanism_reference']=='python:utf-8-strict'
    assert evidence['segments']==[dict(locator='text:1',sha256=hashlib.sha256(raw).hexdigest(),byte_length=len(raw))]
    assert not evidence['rendered_output_observed'] and text not in str(events)
    assert result['segments'][0]['text']==text
