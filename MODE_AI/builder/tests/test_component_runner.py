from __future__ import annotations

import pytest

from builder.execution.command_runner import run_approved_commands


def test_approved_command_executes(tmp_path) -> None:
    results = run_approved_commands(
        commands=[["python", "--version"]],
        approved_commands=[["python", "--version"]],
        cwd=str(tmp_path),
    )

    assert len(results) == 1
    assert results[0]["command"] == ["python", "--version"]


def test_stdout_stderr_captured(tmp_path) -> None:
    results = run_approved_commands(
        commands=[["python", "--version"]],
        approved_commands=[["python", "--version"]],
        cwd=str(tmp_path),
    )

    assert "stdout" in results[0]
    assert "stderr" in results[0]


def test_unapproved_command_rejected(tmp_path) -> None:
    with pytest.raises(ValueError, match="unapproved command"):
        run_approved_commands(
            commands=[["python", "--version"]],
            approved_commands=[],
            cwd=str(tmp_path),
        )


def test_invalid_command_rejected(tmp_path) -> None:
    with pytest.raises(ValueError, match="invalid command"):
        run_approved_commands(
            commands=["python --version"],
            approved_commands=[["python", "--version"]],
            cwd=str(tmp_path),
        )


def test_empty_command_rejected(tmp_path) -> None:
    with pytest.raises(ValueError, match="invalid command"):
        run_approved_commands(
            commands=[[]],
            approved_commands=[[]],
            cwd=str(tmp_path),
        )


def test_cwd_validation_enforced() -> None:
    with pytest.raises(ValueError, match="cwd must not be empty"):
        run_approved_commands(
            commands=[],
            approved_commands=[],
            cwd="",
        )