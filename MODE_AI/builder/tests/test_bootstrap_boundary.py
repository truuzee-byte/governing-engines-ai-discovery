"""Boundary probes use only a temporary tree explicitly owned by this test."""
import sys

from builder.core.command_runner import run_approved_commands


def test_bootstrap_cwd_is_not_reported_as_filesystem_confinement(tmp_path):
    artifact = tmp_path / 'artifact'
    artifact.mkdir()
    command = [sys.executable, '-B', '-c',
               "from pathlib import Path; Path('../outside-cwd.txt').write_text('probe')"]
    result, = run_approved_commands([command], [command], str(artifact))
    assert result['returncode'] == 0
    assert (tmp_path / 'outside-cwd.txt').read_text() == 'probe'
    assert result['execution_boundary'] == {
        'argv_approved': True,
        'working_directory': str(artifact.resolve()),
        'filesystem_confinement': 'NOT_ENFORCED',
        'process_authority': 'HOST_USER',
        'non_filesystem_side_effect_confinement': 'NOT_ENFORCED',
        'side_effect_rollback': 'NOT_PROVIDED',
        'consequence_validation': 'NOT_ESTABLISHED_BY_RETURN_CODE',
    }
