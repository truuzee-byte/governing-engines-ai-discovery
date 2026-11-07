import json
import pytest
from memory.thread_store import ThreadStore


def test_missing_thread_content_is_not_an_empty_conversation(tmp_path):
    store=ThreadStore(str(tmp_path));thread=store.create_thread('op')
    thread.add_message('user','Retain the exact original.');store.save_thread(thread)
    path=tmp_path/'op'/(thread.thread_id+'.json')
    data=json.loads(path.read_text());del data['messages'];path.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='THREAD_INTEGRITY_FAILURE'):store.load_thread('op',thread.thread_id)
    with pytest.raises(ValueError,match='THREAD_INTEGRITY_FAILURE'):store.get_or_create_active_thread('op')


def test_failed_save_preserves_previous_thread(tmp_path,monkeypatch):
    store=ThreadStore(str(tmp_path));thread=store.create_thread('op')
    thread.add_message('user','Preserve this.');store.save_thread(thread)
    original=thread.to_dict();thread.add_message('user','Uncommitted change')
    def fail(*args):raise OSError('Simulated replacement failure')
    monkeypatch.setattr('memory.thread_store.os.replace',fail)
    with pytest.raises(OSError):store.save_thread(thread)
    assert store.load_thread('op',thread.thread_id).to_dict()==original
    assert not list((tmp_path/'op').glob('*.tmp'))
