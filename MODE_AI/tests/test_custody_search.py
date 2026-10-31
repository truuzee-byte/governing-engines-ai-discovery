import sqlite3
import pytest
from memory.vault import Vault
from specs.document_service import DocumentService
from system_layer.contracts import digest


def test_search_preserves_scope_history_and_exact_references(tmp_path):
    vault=Vault(tmp_path/'store.db');docs=DocumentService(vault.store.path)
    def keep(owner,project,identity,text,previous=None):
        req=dict(object_id=identity,content=text,kind='CANON',project_id=project,thread_id='t',source_reference='operator:input',authority='operator',expected_previous=previous)
        return vault.preserve(owner,req,dict(operator_id=owner,action='VAULT_PRESERVE',decision='APPROVE',hash=digest(req)))
    first=keep('op','p','object','Straße and sea')
    second=keep('op','p','object','Updated shoreline',first['record_hash'])
    keep('other','p','foreign','Straße and sea');keep('op','elsewhere','foreign-project','Straße and sea')
    assert vault.search('op','STRASSE','p')['matches']==[]
    found=vault.search('op','STRASSE','p',include_history=True)
    assert len(found['matches'])==1 and found['matches'][0]['record_position']=='HISTORICAL_VERSION'
    ref=found['matches'][0]['reference'];assert vault.retrieve('op',**ref)==first
    assert found['matches'][0]['authority_status']=='NOT_RECONCILED'
    assert docs.search('op','shoreline','p')['matches']==[]
    assert vault.search('op','shoreline','p')['matches'][0]['reference']['expected_hash']==second['record_hash']
    assert not found['automatically_selected'] and not found['execution_authority']
    keep('op','p','another','shoreline')
    limited=vault.search('op','shoreline','p',limit=1)
    assert limited['results_limited'] and limited['matching_records_in_window']==2
    with sqlite3.connect(vault.store.path) as db:
        db.execute("UPDATE objects SET checksum='corrupt' WHERE namespace='VAULT' AND owner='op' AND identity='object' AND version=1")
    with pytest.raises(ValueError,match='CUSTODY_INTEGRITY_FAILURE'):vault.search('op','shoreline','p')


def test_search_reports_unsearched_window(tmp_path):
    vault=Vault(tmp_path/'store.db')
    # Use the underlying already-authorized storage fixture to isolate the window boundary.
    for index in range(257):
        vault.store.append('VAULT','op',f'item-{index:03d}','text',{'project_id':'p'},expected_previous=None,authorization={})
    found=vault.search('op','absent','p')
    assert found['search_completeness']=='PARTIAL_OBJECT_WINDOW' and found['examined_records']==256
    assert not found['matches']


def test_custody_rejects_duplicate_persisted_fields_before_hash_interpretation(tmp_path):
    import json
    vault=Vault(tmp_path/'store.db')
    record=vault.store.append('VAULT','op','item','exact content',{'project_id':'p'},expected_previous=None,authorization={})
    with sqlite3.connect(vault.store.path) as db:
        raw=db.execute('SELECT payload FROM objects').fetchone()[0]
        # The old decoder would discard the first owner and still match the checksum.
        db.execute('UPDATE objects SET payload=?',('{"owner":"other",'+raw[1:],))
    with pytest.raises(ValueError,match='DUPLICATE_FIELD'):
        vault.retrieve('op','item',1,record['record_hash'])


def test_knowledge_discovery_retains_source_classes(tmp_path):
    from knowledge.retrieval import KnowledgeRetrieval
    knowledge=KnowledgeRetrieval(tmp_path/'docs.db')
    for category in ('SYSTEM','INTERNAL','EXTERNAL'):
        req=dict(object_id=category,content='Shared term',kind='DRAFT',visual_authority='NOT_APPLICABLE',knowledge_class=category,
            source_reference='operator:source',authority='operator',project_id='p',thread_id='t',expected_previous=None,validation_references=[])
        knowledge.documents.intake('op',req,dict(operator_id='op',action='DOCUMENT_INTAKE',decision='APPROVE',hash=digest(req)))
    found=knowledge.search('op','Shared','p')
    refs=[m['reference'] for m in found['matches']]
    result=knowledge.retrieve('op',refs)
    assert {e['knowledge_class'] for e in result['entries']}=={'SYSTEM','INTERNAL','EXTERNAL'}
    assert all(e['state']=='UNPROVEN' for e in result['entries'])


@pytest.mark.parametrize('mutation',[
    {'content_hash':'wrong'}, {'schema_version':'CustodyObject/unknown'},
    {'version':True}, {'metadata':[]}, {'unexpected':'unrepresented'},
])
def test_self_consistent_outer_checksum_cannot_hide_malformed_custody(tmp_path,mutation):
    import json
    vault=Vault(tmp_path/'store.db')
    vault.store.append('VAULT','op','item','exact content',{'project_id':'p'},expected_previous=None,authorization={})
    with sqlite3.connect(vault.store.path) as db:
        value=json.loads(db.execute('SELECT payload FROM objects').fetchone()[0])
        value.update(mutation)
        checksum=digest(value)
        db.execute('UPDATE objects SET payload=?,checksum=?',(json.dumps(value),checksum))
    with pytest.raises(ValueError,match='CUSTODY_INTEGRITY_FAILURE'):
        vault.retrieve('op','item',1,checksum)


def test_malformed_custody_metadata_rejected_before_append(tmp_path):
    vault=Vault(tmp_path/'store.db')
    for metadata,authorization in (([],{}),({},None)):
        with pytest.raises(ValueError,match='custody metadata'):
            vault.store.append('VAULT','op','item','exact',metadata,expected_previous=None,authorization=authorization)
    assert vault.store.history('VAULT','op','item')==[]
