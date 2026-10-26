"""Thread continuity is scoped conversation, never an authoritative Vault substitute."""
import json
import pytest
from memory.thread_store import ThreadStore


@pytest.mark.parametrize('identity', ['../other','C:/other','a\\b','..','.', '', 'other:stream'])
def test_thread_storage_rejects_cross_scope_paths(tmp_path, identity):
    store=ThreadStore(str(tmp_path))
    with pytest.raises(ValueError): store.load_thread(identity,'thread')
    with pytest.raises(ValueError): store.load_thread('operator',identity)


@pytest.mark.parametrize('field',['operator_id','thread_id'])
def test_loaded_and_listed_thread_must_match_requested_identity(tmp_path, field):
    store=ThreadStore(str(tmp_path))
    thread=store.create_thread('operator')
    path=tmp_path/'operator'/f'{thread.thread_id}.json'
    value=json.loads(path.read_text())
    value[field]='other'
    path.write_text(json.dumps(value))
    with pytest.raises(PermissionError):store.load_thread('operator',thread.thread_id)
    with pytest.raises(PermissionError):store.list_threads('operator')


def test_missing_continuity_is_not_regenerated(tmp_path):
    store=ThreadStore(str(tmp_path))
    with pytest.raises(FileNotFoundError):store.get_or_create_active_thread('operator','missing')
    assert store.list_threads('operator')==[]


def test_existing_thread_survives_roundtrip(tmp_path):
    store=ThreadStore(str(tmp_path))
    thread=store.create_thread('operator')
    thread.add_message('operator','Today I prefer tea.',metadata={'scope':'SESSION_ONLY'})
    store.save_thread(thread)
    assert store.load_thread('operator',thread.thread_id).to_dict()==thread.to_dict()
    assert store.list_threads('other')==[]
