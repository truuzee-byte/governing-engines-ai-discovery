import json
from pathlib import Path
from builder.tests.test_kernel_preparation import FixtureKernel
from builder.tests.test_builder_entry import _valid_handoff_payload
from builder.core.build_entry import run_builder_core


def test_changed_materialization_cannot_execute_or_pass(tmp_path):
    class CorruptTransfer(FixtureKernel):
        def write_files(self,files,required):
            paths=super().write_files(files,required)
            Path(paths[0]).write_text('Changed transfer content',encoding='utf-8')
            return paths
        def run_commands(self,*args):raise AssertionError('Unapproved materialized source executed')
    output=run_builder_core(_valid_handoff_payload(root=tmp_path),str(tmp_path),
        kernel_client=CorruptTransfer('RESOURCE_RELEASE_CONFIRMED',['fixture']),require_kernel=True)
    assert output.validation_status!='PASS'
    check=next(r for r in output.validation_results if r.get('validation_type')=='artifact_materialization')
    assert check['state']=='FAILED' and check['observed_sha256']
    receipt=json.loads(Path(output.receipt_path).read_text())
    assert receipt['final_status']==output.validation_status
    assert all('not executed' in r['error'] for r in output.command_results)
