import pytest
from memory.thread_store import ThreadStore
from memory.vault import Vault
from system_layer.contracts import digest

def test_preserved_thread_survives_evolving_conversation(tmp_path):
    threads=ThreadStore(str(tmp_path/'threads'));thread=threads.create_thread('op')
    thread.add_message('user','The original character wears blue.');threads.save_thread(thread)
    request=dict(object_id='canon',thread_id=thread.thread_id,expected_thread_hash=digest(thread.to_dict()),
                 project_id='p',expected_previous=None)
    approval=dict(operator_id='op',action='VAULT_PRESERVE_THREAD',decision='APPROVE',hash=digest(request))
    vault=Vault(tmp_path/'vault.db')
    with pytest.raises(PermissionError):vault.preserve_thread('op',request,{},thread_store=threads)
    record=vault.preserve_thread('op',request,approval,thread_store=threads)
    thread.add_message('user','Consider a different outfit.');threads.save_thread(thread)
    saved=vault.thread_snapshot('op','canon',1,record['record_hash'])
    assert [m['content'] for m in saved['thread']['messages']]==['The original character wears blue.']
    assert saved['claims_validated'] is False
    with pytest.raises(ValueError,match='Thread changed'):vault.preserve_thread('op',request,approval,thread_store=threads)
    with pytest.raises(FileNotFoundError):vault.thread_snapshot('other','canon',1,record['record_hash'])
