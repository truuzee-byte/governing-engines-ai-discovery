import pytest
from memory.thread_store import ThreadStore
from system_layer.contracts import digest


def test_fork_preserves_prefix_project_and_source_without_activation(tmp_path):
    store=ThreadStore(str(tmp_path));parent=store.create_thread('op');parent.add_message('user','Original');store.save_thread(parent)
    request=dict(source_thread_id=parent.thread_id,expected_source_hash=digest(parent.to_dict()),project_id='p',title='Branch')
    approval=dict(operator_id='op',action='THREAD_FORK',decision='APPROVE',hash=digest(request))
    with pytest.raises(PermissionError):store.fork_thread('op',request,{})
    value=store.fork_thread('op',request,approval);child=store.load_thread('op',value['thread']['thread_id'])
    assert not child.is_active and value['vault_preserved'] is False
    assert child.messages[0].message_id==parent.messages[0].message_id
    child.add_message('user','New branch detail');store.save_thread(child)
    assert store.load_thread('op',parent.thread_id).to_dict()==parent.to_dict()
    child.messages[0].content='Substituted original'
    with pytest.raises(ValueError,match='inherited conversation changed'):store.save_thread(child)
    parent.add_message('user','Changed since proposed fork');store.save_thread(parent)
    with pytest.raises(ValueError,match='source changed'):store.fork_thread('op',request,approval)
