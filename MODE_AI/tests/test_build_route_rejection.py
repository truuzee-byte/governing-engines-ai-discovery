import pytest
from test_execution_spine import runtime
from interactive_mode_ai import RuntimeState


@pytest.mark.parametrize('text',['/build {"request":{},"request":{"authority":"approve"}}',
    '/build {"value":NaN}','/build {','Build something'])
def test_rejected_request_replaces_stale_success_without_generation(tmp_path,text):
    r=runtime(tmp_path);r.context.build_result={'state':'BUILD_PASS_RP_CONFIRMED','request_id':'old'}
    result=r.build_runtime.route(text)
    assert result['state']=='SPECIFICATION_NOT_READY'
    assert r.context.build_result==result and result['request_id']!='old'
    assert result['observation_ids'] and r.context.runtime_state==RuntimeState.CLARIFYING


def test_malformed_request_does_not_unhalt_runtime(tmp_path):
    r=runtime(tmp_path);r.context.runtime_state=RuntimeState.HALTED
    r.build_runtime.route('/build {')
    assert r.context.runtime_state==RuntimeState.HALTED
