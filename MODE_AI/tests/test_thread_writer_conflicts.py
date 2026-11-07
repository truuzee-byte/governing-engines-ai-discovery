from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from memory.thread_store import ThreadStore
from memory.thread_memory import ThreadMemory


def test_stale_copy_cannot_overwrite_new_messages_or_recreate_deleted_thread(tmp_path):
    store=ThreadStore(str(tmp_path));first=store.create_thread('op')
    stale=store.load_thread('op',first.thread_id)
    first.add_message('operator','Newer preserved fact');store.save_thread(first)
    stale.add_message('operator','Uncommitted stale fact')
    with pytest.raises(ValueError,match='THREAD_WRITE_CONFLICT'):store.save_thread(stale)
    from frontend.runtime_view import snapshot
    from types import SimpleNamespace as NS
    view=snapshot(NS(context=NS(identity=NS(operator_id='op'),active_thread=stale,runtime_state='ERROR')))
    assert view['thread_retention']['state']=='WRITE_CONFLICT'
    assert view['thread_retention']['current_disk_state']=='NOT_RECHECKED'
    assert store.load_thread('op',first.thread_id).messages[-1].content=='Newer preserved fact'
    assert stale.messages[-1].content=='Uncommitted stale fact'
    clone=ThreadMemory.from_dict(first.to_dict())
    with pytest.raises(ValueError,match='THREAD_WRITE_CONFLICT'):store.save_thread(clone)
    store._thread_path('op',first.thread_id).unlink()
    with pytest.raises(ValueError,match='THREAD_WRITE_CONFLICT'):store.save_thread(first)


def test_competing_store_instances_accept_one_writer(tmp_path):
    store=ThreadStore(str(tmp_path));original=store.create_thread('op');barrier=Barrier(2)
    def write(text):
        other=ThreadStore(str(tmp_path));thread=other.load_thread('op',original.thread_id)
        thread.add_message('operator',text);barrier.wait()
        try:other.save_thread(thread);return text
        except ValueError as exc:
            assert 'THREAD_WRITE_CONFLICT' in str(exc)
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(write,['first','second']))
    accepted=[value for value in results if value is not None]
    assert len(accepted)==1
    saved=store.load_thread('op',original.thread_id)
    assert [message.content for message in saved.messages]==accepted
    saved.add_message('assistant','Continued after explicit reload');store.save_thread(saved)
    assert '_custody_baseline' not in saved.to_dict()


def test_duplicate_persisted_thread_fields_are_not_silently_collapsed(tmp_path):
    store=ThreadStore(str(tmp_path));thread=store.create_thread('op')
    path=store._thread_path('op',thread.thread_id);original=path.read_text()
    path.write_text(original[:-2]+',"title":"replacement"\n}')
    with pytest.raises(ValueError,match='DUPLICATE'):store.load_thread('op',thread.thread_id)
