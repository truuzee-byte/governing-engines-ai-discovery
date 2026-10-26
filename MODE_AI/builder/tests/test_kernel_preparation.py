import pytest
from builder.core.build_entry import run_builder_core
from builder.kernel.kernel_client import OperationBoundKernelClient
from builder.tests.test_builder_entry import _valid_handoff_payload


def test_required_kernel_cannot_default_to_host(tmp_path):
    with pytest.raises(PermissionError,match='fallback prohibited'):
        run_builder_core({},str(tmp_path),require_kernel=True)
    assert list(tmp_path.iterdir())==[]


class RejectingKernel(OperationBoundKernelClient):
    def bind(self, root, operations, snapshot_hash):
        self.bound=(root, operations, snapshot_hash)
        raise PermissionError('external Kernel denied')
    def create_workspace(self, directories): raise AssertionError('denied')
    def write_files(self, files, required): raise AssertionError('denied')
    def run_commands(self, commands, approved): raise AssertionError('denied')


def test_kernel_rejection_never_falls_back(tmp_path,monkeypatch):
    import builder.kernel.kernel_client as module
    monkeypatch.setattr(module,'write_approved_files',lambda *a,**k:pytest.fail('host fallback'))
    kernel=RejectingKernel()
    with pytest.raises(PermissionError,match='external Kernel denied'):
        run_builder_core(_valid_handoff_payload(root=tmp_path),str(tmp_path),kernel_client=kernel,require_kernel=True)
    assert kernel.bound[1] and kernel.bound[2]
    assert not (tmp_path/'reports/result.txt').exists()


class FixtureKernel(OperationBoundKernelClient):
    """Local test double only; no claim of external Kernel qualification."""
    def __init__(self, retirement, references):self.retirement=retirement;self.references=references
    def bind(self,root,operations,snapshot_hash):
        from builder.kernel.kernel_client import BootstrapKernelClient
        self.local=BootstrapKernelClient(root,operations)
    def create_workspace(self,directories):return self.local.create_workspace(directories)
    def write_files(self,files,required):return self.local.write_files(files,required)
    def run_commands(self,commands,approved):
        results=self.local.run_commands(commands,approved)
        return [dict(r,retirement_state=self.retirement,evidence_references=self.references) for r in results]


@pytest.mark.parametrize('retirement,references,expected',[
    ('UNPROVEN',['fixture:evidence'],'UNPROVEN'),
    ('RESOURCE_RELEASE_CONFIRMED','not-a-reference-list','UNPROVEN'),
    ('RESOURCE_RELEASE_CONFIRMED',['fixture:evidence'],'PASS')])
def test_required_retirement_evidence_reaches_receipt(tmp_path,retirement,references,expected):
    import json
    from pathlib import Path
    output=run_builder_core(_valid_handoff_payload(root=tmp_path),str(tmp_path),
        kernel_client=FixtureKernel(retirement,references),require_kernel=True)
    assert output.validation_status==expected
    receipt=json.loads(Path(output.receipt_path).read_text())
    assert receipt['final_status']==expected
    assert any(r.get('validation_type')=='kernel_execution_evidence' for r in receipt['validation_results'])


def test_real_builder_stages_are_observed(tmp_path):
    stages=[]
    run_builder_core(_valid_handoff_payload(root=tmp_path),str(tmp_path),stage_observer=stages.append)
    assert stages==['BUILDING','VALIDATING']


def test_cutover_preparation_does_not_execute_or_activate(tmp_path):
    from builder.core.build_plan_generator import generate_build_plan
    from builder.kernel.cutover_preparation import prepare_cutover
    plan=generate_build_plan(_valid_handoff_payload(root=tmp_path))
    result=prepare_cutover(plan)
    assert result['state']=='CUTOVER_PREPARED_AWAITING_OPERATOR_AUTHORITY'
    assert result['activation']=='BLOCKED' and not result['execution_attempted']
    assert not result['execution_authority']
    assert result['snapshot_hash']==plan.snapshot_hash
    assert result['validation_commands']==plan.validation_commands
    assert list(tmp_path.iterdir())==[]
