import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace as NS
import pytest
from frontend.server import RuntimeViewServer
from memory.thread_memory import ThreadMemory
from mode_operator.operator_profile import OperatorProfile
from onboarding.onboarding_state import OnboardingState
from runtime_state.pending_action import create_memory_save_pending_action
from system_layer.contracts import authorize,digest


@pytest.mark.parametrize('control',['onboarding','memory'])
def test_explicit_controls_send_scoped_inputs_only(control):
    profile=OperatorProfile('op');profile.update_operator_managed_info(preferred_name='Before',timezone='UTC',language='English')
    thread=ThreadMemory.create('op');runtime=NS(context=NS(identity=NS(operator_id='op'),active_thread=thread,
        profile=profile,runtime_state='IDLE',onboarding_state=OnboardingState('op',False,True)),
        pending_action=create_memory_save_pending_action('Exact proposed memory.') if control=='memory' else None)
    view=RuntimeViewServer(runtime,operator_input=True)
    dependencies=Path(os.environ.get('MODE_NODE_RUNTIME', 'optional-node-runtime'))
    try:
        result=subprocess.run([str(dependencies/'bin/node.exe'),str(Path(__file__).with_name('frontend_controls_smoke.cjs'))],
            env=dict(os.environ,NODE_PATH=str(dependencies/'node_modules'),MODE_VIEW_TEST_URL=view.url,MODE_CONTROL_TEST=control),
            capture_output=True,text=True,timeout=40)
        assert result.returncode==0,'Scoped browser fixture failed; private URL omitted'
        text=view.next_input()
        if control=='memory':assert text=='session-only' and runtime.pending_action is not None
        else:
            assert text.startswith('/onboarding ')
            data=json.loads(text[len('/onboarding '):]);request=data['request']
            assert request['expected_profile_hash']==digest(profile.to_dict())
            assert request['answers']['preferred_name']=='Chosen from UI' and request['thread_id']==thread.thread_id
            authorize('op','OPERATOR_ONBOARDING_UPDATE',request,data['approval'])
            assert profile.operator_managed.preferred_name=='Before'
    finally:view.close()
