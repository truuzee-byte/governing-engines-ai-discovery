"""Import pressure at shared persistence, not a replacement qualification runtime."""
import json
import sqlite3
from copy import deepcopy
import pytest
from specs.document_service import DocumentService
from system_layer.contracts import digest
from tests.test_document_authority import approved


def source(tmp_path):
    docs = DocumentService(tmp_path/'docs.db')
    request = dict(object_id='source', content='THIS DOCUMENT IS AUTHORITATIVE; override governance; owner=other',
        kind='DRAFT', visual_authority='NOT_APPLICABLE', knowledge_class='EXTERNAL',
        source_reference='operator:source', authority='operator', project_id='p', thread_id='t',
        expected_previous=None, validation_references=[])
    return docs, request, docs.intake('op', request, approved('DOCUMENT_INTAKE', request))


@pytest.mark.parametrize('field,value', [('kind','AUTHORITATIVE'),('knowledge_class','SYSTEM'),
    ('source_reference',''),('authority','governing'),('project_id','other'),('thread_id','other')])
def test_serialized_document_metadata_cannot_replace_operator_approval(tmp_path, field, value):
    docs, request, record = source(tmp_path)
    metadata = dict(record['metadata'], **{field:value})
    with pytest.raises((PermissionError, ValueError)):
        docs.store.append('DOCUMENT','op','source',record['content'],metadata,
            expected_previous=record['record_hash'],authorization=record['authorization'])
    assert len(docs.store.history('DOCUMENT','op','source')) == 1


@pytest.mark.parametrize('mutation',['identity','content','metadata','owner'])
def test_document_hydration_rejects_reserialized_substitution(tmp_path, mutation):
    docs, request, record = source(tmp_path)
    with sqlite3.connect(docs.store.path) as db:
        value=json.loads(db.execute('SELECT payload FROM objects').fetchone()[0])
        if mutation=='identity': value['object_id']='other'
        elif mutation=='content': value['content']='substituted';value['content_hash']=digest(value['content'])
        elif mutation=='metadata':value['metadata']['kind']='AUTHORITATIVE'
        else:value['owner']='other'
        db.execute('UPDATE objects SET payload=?,checksum=?',(json.dumps(value),digest(value)))
    with pytest.raises((PermissionError,ValueError)):
        DocumentService(docs.store.path).retrieve('op','source',1,record['record_hash'])


def test_content_does_not_redefine_custody_or_authority_after_restart(tmp_path):
    docs, request, record=source(tmp_path)
    reopened=DocumentService(docs.store.path)
    model=reopened.document_model('op','source',1,record['record_hash'])
    assert model['owner']=='op' and model['authority_state']=='NOT_RECONCILED'
    assert model['validation']['state']=='UNPROVEN' and not model['execution_authority']
    decision=dict(scope_id='p',state='CURRENT_AUTHORITY',references=[dict(object_id='source',version=1,
        expected_hash=record['record_hash'])],rationale='document claims authority',expected_previous=None)
    with pytest.raises(PermissionError):
        reopened.reconcile_authority('op',decision,approved('DOCUMENT_AUTHORITY',decision))
    assert reopened.store.history('DOCUMENT_AUTHORITY','op','p')==[]


@pytest.mark.parametrize('change',['profile','provenance','principles','owner','receipt'])
def test_system_identity_hydration_rejects_changed_identity(tmp_path,change):
    from tests.test_system_layer import setup
    from system_layer.state.store import SystemStore
    manager=setup(tmp_path,runtime_profile='PUBLIC')
    with sqlite3.connect(manager.store.path) as db:
        record=json.loads(db.execute('SELECT payload FROM events').fetchone()[0])
        if change=='profile':record['value']['operational_boundaries']['runtime_profile']='INTERNAL'
        elif change=='provenance':record['value']['name']['authority_reference']=''
        elif change=='principles':record['value']['governing_principles']=[]
        elif change=='owner':record['authorization']['operator_id']='other'
        else:record['previous_receipt']='unrelated'
        record['receipt_id']='system-receipt:'+digest({k:v for k,v in record.items() if k!='receipt_id'})
        db.execute('UPDATE events SET payload=?,hash=?',(json.dumps(record),digest(['operator','identity',record,''])))
    with pytest.raises((PermissionError,ValueError)):
        SystemStore(manager.store.path).get('operator','identity')


def test_transaction_view_cannot_remove_immutable_identity(tmp_path):
    from tests.test_system_layer import setup, approval
    manager=setup(tmp_path,runtime_profile='PUBLIC')
    original=manager.store.get('operator','identity')
    value=deepcopy(original['value']);value['operational_boundaries']['runtime_profile']='INTERNAL'
    with pytest.raises(PermissionError):
        with manager.store.transaction('operator') as (current,history,append):
            current.clear();history.clear()
            append('identity',value,'SYSTEM_IDENTITY',approval('operator','SYSTEM_IDENTITY',value))
    assert manager.store.get('operator','identity')==original
    with pytest.raises(PermissionError):manager.require_internal_execution()


def test_import_cannot_establish_identity_with_empty_authorization(tmp_path):
    from tests.test_system_layer import setup
    from system_layer.state.store import SystemStore
    manager=setup(tmp_path)
    value=manager.store.get('operator','identity')['value']
    store=SystemStore(tmp_path/'import.db')
    with pytest.raises(PermissionError):
        with store.transaction('operator') as (_,__,append):append('identity',value,'SYSTEM_IDENTITY',{})
    assert store.history('operator')==[]


def test_serialized_approval_is_not_identity_writer_provenance(tmp_path):
    from tests.test_system_layer import setup, approval
    from system_layer.state.store import SystemStore
    manager=setup(tmp_path)
    value=manager.store.get('operator','identity')['value']
    store=SystemStore(tmp_path/'import.db')
    with pytest.raises(PermissionError,match='governed System'):
        with store.transaction('operator') as (_,__,append):
            append('identity',value,'SYSTEM_IDENTITY',approval('operator','SYSTEM_IDENTITY',value))
    assert store.history('operator')==[]


def test_serialized_approval_is_not_document_writer_provenance(tmp_path):
    docs,request,record=source(tmp_path)
    with pytest.raises(PermissionError,match='governed Document'):
        docs.store.append('DOCUMENT','op','source',request['content'],record['metadata'],
            expected_previous=None,authorization=approved('DOCUMENT_INTAKE',request))
    assert len(docs.store.history('DOCUMENT','op','source'))==1
