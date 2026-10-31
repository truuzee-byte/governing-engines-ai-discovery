import json
import pytest
from mode_operator.operator_store import OperatorStore
from mode_operator.operator_identity import OperatorIdentity


def test_profile_stale_save_cannot_overwrite_thread_selection_or_answers(tmp_path):
    store=OperatorStore(str(tmp_path));identity=OperatorIdentity.create('op');profile=store.create_profile(identity)
    stale=store.load_profile(identity)
    profile.update_operator_managed_info(preferred_name='Current answer');store.save_profile(identity,profile)
    stale.active_thread_id='different-thread'
    with pytest.raises(ValueError,match='PROFILE_WRITE_CONFLICT'):store.save_profile(identity,stale)
    assert store.load_profile(identity).operator_managed.preferred_name=='Current answer'
    assert store.load_profile(identity).active_thread_id is None


def test_profile_inspection_is_read_only_and_corruption_is_not_hidden(tmp_path):
    store=OperatorStore(str(tmp_path));one=OperatorIdentity.create('one');two=OperatorIdentity.create('two')
    store.create_profile(one);store.create_profile(two)
    assert store.get_current_operator_id()=='two'
    store.load_profile(one);assert store.get_current_operator_id()=='two'
    assert {value.operator_id for value in store.list_profiles()}=={'one','two'}
    assert store.get_current_operator_id()=='two'
    path=tmp_path/'one.json';data=json.loads(path.read_text());del data['operator_managed'];path.write_text(json.dumps(data))
    before=path.read_bytes()
    with pytest.raises(ValueError,match='INTEGRITY'):store.load_profile(one)
    with pytest.raises(ValueError,match='listing incomplete'):store.list_profiles()
    assert path.read_bytes()==before


@pytest.mark.parametrize('identity',['CON','nul.json','COM1','LPT9.txt','bad?name','bad\nname'])
def test_profile_paths_reject_non_file_windows_identities(tmp_path,identity):
    with pytest.raises(ValueError):OperatorStore(str(tmp_path))._profile_path(identity)
    assert list(tmp_path.iterdir())==[]


def test_missing_selected_profile_and_duplicate_fields_do_not_regenerate_identity(tmp_path):
    store=OperatorStore(str(tmp_path));identity=OperatorIdentity.create('op');store.create_profile(identity)
    path=tmp_path/'op.json';before=path.read_text()
    path.write_text(before[:-2]+',"operator_id":"op"\n}')
    with pytest.raises(ValueError,match='DUPLICATE'):store.load_profile(identity)
    path.unlink()
    with pytest.raises(FileNotFoundError):store.get_or_create_profile()
    assert not path.exists()
