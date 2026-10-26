import sqlite3
import pytest
from memory.vault import Vault
from specs.document_service import DocumentService
from system_layer.contracts import digest


def request():
    return dict(object_id='fact',content='My character has a blue coat.',source_reference='operator:turn-3',
                authority='operator',kind='CANON',project_id='project',thread_id='thread',expected_previous=None)


def approve(value, action):
    return dict(operator_id='owner',action=action,decision='APPROVE',hash=digest(value))


def test_vault_exact_content_and_versions(tmp_path):
    vault=Vault(tmp_path/'store.db'); first=request()
    a=vault.preserve('owner',first,approve(first,'VAULT_PRESERVE'))
    second=dict(first,content='My character has a green coat.',expected_previous=a['record_hash'])
    b=vault.preserve('owner',second,approve(second,'VAULT_PRESERVE'))
    assert vault.retrieve('owner','fact',1,a['record_hash'])['content']==first['content']
    assert b['previous_hash']==a['record_hash'] and b['version']==2
    with pytest.raises(ValueError):vault.preserve('owner',first,approve(first,'VAULT_PRESERVE'))
    with pytest.raises(FileNotFoundError):vault.retrieve('other','fact',1,a['record_hash'])
    with pytest.raises(ValueError):vault.retrieve('owner','fact',1,b['record_hash'])


@pytest.mark.parametrize('approval',[None,{}, {'decision':'NO'}])
def test_no_fabricated_consent(tmp_path,approval):
    with pytest.raises(PermissionError):Vault(tmp_path/'store.db').preserve('owner',request(),approval)


def test_tampering_and_missing_content_fail_closed(tmp_path):
    path=tmp_path/'store.db';vault=Vault(path);r=request()
    a=vault.preserve('owner',r,approve(r,'VAULT_PRESERVE'))
    with sqlite3.connect(path) as db:db.execute("UPDATE objects SET checksum='modified'")
    with pytest.raises(ValueError,match='INTEGRITY'):vault.retrieve('owner','fact',1,a['record_hash'])


def test_document_namespace_and_specification_authority(tmp_path):
    path=tmp_path/'store.db';docs=DocumentService(path)
    r=dict(request(),kind='SPECIFICATION',visual_authority='NOT_APPLICABLE',validation_references=[],knowledge_class='INTERNAL')
    a=docs.intake('owner',r,approve(r,'DOCUMENT_INTAKE'))
    source=docs.specification_source('owner','fact',1,a['record_hash'])
    assert source['execution_authority'] is False
    assert source['record']['content']==r['content']
    with pytest.raises(FileNotFoundError):Vault(path).retrieve('owner','fact',1,a['record_hash'])
    draft=dict(r,object_id='draft',kind='GENERATED_CANDIDATE')
    b=docs.intake('owner',draft,approve(draft,'DOCUMENT_INTAKE'))
    with pytest.raises(PermissionError):docs.specification_source('owner','draft',1,b['record_hash'])
