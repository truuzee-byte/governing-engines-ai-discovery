import json
from types import SimpleNamespace as NS
import pytest
from persistent_memory.persistent_memory_manager import PersistentMemoryManager
from persistent_memory.persistent_memory_store import PersistentMemoryStore
from integration.memory_commands import execute


def test_lifecycle_requires_actual_consent_and_preserves_governance_reference(tmp_path):
    manager=PersistentMemoryManager(PersistentMemoryStore(tmp_path/'memory'))
    candidate=manager.propose_create_memory('op','Exact private fact.','t','m','Exact private fact.').candidate
    record=manager.confirm_candidate(candidate,'yes').record;events=[]
    runtime=NS(context=NS(identity=NS(operator_id='op')),persistent_memory_manager=manager,
        _observe_runtime_event=lambda name,payload,**kw:events.append((payload,kw)))
    with pytest.raises(PermissionError):execute(runtime,'/memory archive '+json.dumps({'id':record.memory_id,'confirmation':'no'}))
    assert manager.store.load_record('op',record.memory_id).status.value=='ACTIVE'
    changed=execute(runtime,'/memory archive '+json.dumps({'id':record.memory_id,'confirmation':'yes'}))
    assert changed['status']=='ARCHIVED'
    assert events[-1][0]['record_references']==[changed['governance_decision']['decision_id']]
    assert events[-1][0]['authority_reference']==changed['governance_decision']['decision_id']
    assert events[-1][0]['authority_source']=='data_governance.memory_governance'
    assert 'Exact private fact.' not in str(events)
    with pytest.raises(ValueError):execute(runtime,'/memory restore {"id":"one","id":"two","confirmation":"yes"}')
    assert len(execute(runtime,'/memory show '+record.memory_id))==2
