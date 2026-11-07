from types import SimpleNamespace as NS
import pytest
from system_layer.runtime import command

def test_operational_preparation_rejects_retained_other_thread_meaning():
    runtime=NS(context=NS(active_thread=NS(thread_id='current'),
        understanding_result=NS(operator_id='op',final_understanding=NS(thread_id='old'))),system_layer=NS(owner='op'))
    with pytest.raises(PermissionError,match='current Operator/thread'):
        command(runtime,'/system operation_plan capability')
