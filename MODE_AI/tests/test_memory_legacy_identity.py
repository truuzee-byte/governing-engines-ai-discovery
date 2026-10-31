import json
import pytest
from persistent_memory.persistent_memory_manager import PersistentMemoryManager
from persistent_memory.persistent_memory_store import PersistentMemoryStore


@pytest.mark.parametrize('mismatch',['operator_id','memory_id','duplicate'])
def test_legacy_read_cannot_rebind_persisted_identity(tmp_path,mismatch):
    manager=PersistentMemoryManager(PersistentMemoryStore(tmp_path/'original'))
    candidate=manager.propose_create_memory('op','Original fact','thread','message','Original fact').candidate
    record=manager.confirm_candidate(candidate,'yes').record
    value=record.to_dict()
    if mismatch!='duplicate':value[mismatch]='other'
    raw=json.dumps(value)
    if mismatch=='duplicate':raw='{"operator_id":"other",'+raw[1:]
    folder=tmp_path/'legacy';(folder/'op').mkdir(parents=True)
    path=folder/'op'/f'{record.memory_id}.json';path.write_text(raw)
    store=PersistentMemoryStore(folder)
    with pytest.raises(ValueError):store.load_record('op',record.memory_id)
    with pytest.raises(ValueError):store.load_records_for_operator('op')
    assert path.read_text()==raw


@pytest.mark.parametrize('identity',['C:other','CON','NUL.txt','operator.','operator ','other:stream'])
def test_memory_file_identity_cannot_alias_windows_paths(tmp_path,identity):
    store=PersistentMemoryStore(tmp_path/'memory')
    with pytest.raises(ValueError):store.load_records_for_operator(identity)
    with pytest.raises(ValueError):store.load_record('op',identity)


@pytest.mark.parametrize('field,value',[('storage_scope',None),('consent_status',None),('operator_can_delete','false'),('confidence','1.0'),('version',True)])
def test_persisted_memory_cannot_invent_consent_scope_or_coerce_permissions(tmp_path,field,value):
    from persistent_memory.persistent_memory_record import PersistentMemoryRecord
    manager=PersistentMemoryManager(PersistentMemoryStore(tmp_path/'memory'))
    record=manager.confirm_candidate(manager.propose_create_memory('op','Exact fact','thread','message','Exact fact').candidate,'yes').record
    data=record.to_dict()
    if value is None:data.pop(field)
    else:data[field]=value
    with pytest.raises(ValueError):PersistentMemoryRecord.from_dict(data)


def test_numeric_representation_round_trip_does_not_invalidate_governance_hash(tmp_path):
    manager=PersistentMemoryManager(PersistentMemoryStore(tmp_path/'memory'))
    candidate=manager.propose_create_memory('op','Exact fact','thread','message','Exact fact').candidate
    candidate.confidence=1
    record=manager.confirm_candidate(candidate,'yes').record
    loaded=manager.store.load_record('op',record.memory_id)
    from learning.contracts import digest
    assert digest(loaded.to_dict())==digest(record.to_dict()) and type(loaded.confidence) is int
    assert [r.memory_id for r in manager.retrieve_memories('op')]==[record.memory_id]
