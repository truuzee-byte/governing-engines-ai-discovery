import json
from pathlib import Path
import pytest
from builder.tests.test_kernel_preparation import FixtureKernel
from builder.tests.test_builder_entry import _valid_handoff_payload
from builder.core.build_entry import run_builder_core

@pytest.mark.parametrize('defect',['duplicate','different_command','boolean_exit'])
def test_malformed_kernel_result_cannot_pass(tmp_path,defect):
    class Malformed(FixtureKernel):
        def run_commands(self,commands,approved):
            results=super().run_commands(commands,approved)
            if defect=='duplicate':return results+results
            if defect=='different_command':results[0]['command']=['unrequested']
            if defect=='boolean_exit':results[0]['returncode']=False
            return results
    out=run_builder_core(_valid_handoff_payload(root=tmp_path),str(tmp_path),
        kernel_client=Malformed('RESOURCE_RELEASE_CONFIRMED',['fixture:reference']),require_kernel=True)
    assert out.validation_status!='PASS'
    receipt=json.loads(Path(out.receipt_path).read_text())
    assert receipt['final_status']==out.validation_status
    assert 'requested invocation' in out.command_results[0]['error']
