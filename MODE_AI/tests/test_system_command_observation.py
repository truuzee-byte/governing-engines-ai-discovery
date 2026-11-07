import json
from types import SimpleNamespace as NS
import pytest
from system_layer.runtime import execute,service
from system_layer.contracts import digest


def test_system_discovery_links_receipt_and_failed_authorization_without_source_contents(tmp_path):
    events=[];runtime=NS(context=NS(identity=NS(operator_id='op')),
        understanding_engine=NS(store=NS(path=tmp_path/'meaning.db')),
        _observe_runtime_event=lambda name,payload,**kw:events.append((name,payload,kw)))
    request=dict(system_id='s',root=str(tmp_path),extensions=['.py'],limit=2,purpose='Private source inspection purpose')
    with pytest.raises(PermissionError):execute(runtime,'/system discover_sources '+json.dumps(dict(request=request,approval={})))
    assert events[-1][1]['state']=='REJECTED' and events[-1][2]['runtime_error']=='PermissionError'
    approval=dict(operator_id='op',action='STRUCTURAL_SOURCE_DISCOVERY',decision='APPROVE',hash=digest(request))
    result=execute(runtime,'/system discover_sources '+json.dumps(dict(request=request,approval=approval)))
    assert events[-1][1]['record_references']==[result['receipt_id']]
    assert events[-1][1]['result_hash']==digest(result)
    assert request['purpose'] not in str(events)
    before=len(service(runtime).store.history('op'))
    execute(runtime,'/system show source-discovery:s')
    assert len(service(runtime).store.history('op'))==before
    assert 'produced_receipts' not in events[-1][1]
