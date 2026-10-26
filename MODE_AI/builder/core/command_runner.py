from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Dict, List


DEFAULT_TIMEOUT_SECONDS = 120


def run_approved_commands(
    commands: list,
    approved_commands: list,
    cwd: str,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> list[dict]:
    """Run exact approved argv under host authority, not in an OS sandbox.

    Approval and cwd do not confine file writes, child processes, network access,
    or other side effects. Preserve that boundary with each execution result;
    returncode establishes process completion only, not consequence validation.
    """
    if not isinstance(commands, list):
        raise ValueError("commands must be a list")
    if not isinstance(approved_commands, list):
        raise ValueError("approved_commands must be a list")
    if not isinstance(cwd, str) or not cwd.strip():
        raise ValueError("cwd must not be empty")
    if not isinstance(timeout_seconds, int) or timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")

    cwd_path = Path(cwd).resolve()
    if not cwd_path.is_dir():
        raise ValueError("cwd does not exist")

    approved_signatures = {_command_signature(command) for command in approved_commands}
    results: List[Dict[str, object]] = []

    for command in commands:
        signature = _command_signature(command)
        if signature not in approved_signatures:
            raise ValueError("unapproved command")

        completed = subprocess.run(
            list(signature),
            cwd=str(cwd_path),
            shell=False,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
            env=_restricted_environment(),
        )
        results.append(
            {
                "command": list(signature),
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "execution_boundary": {
                    "argv_approved": True,
                    "working_directory": str(cwd_path),
                    "filesystem_confinement": "NOT_ENFORCED",
                    "process_authority": "HOST_USER",
                    "non_filesystem_side_effect_confinement": "NOT_ENFORCED",
                    "side_effect_rollback": "NOT_PROVIDED",
                    "consequence_validation": "NOT_ESTABLISHED_BY_RETURN_CODE",
                },
            }
        )

    return results


def _command_signature(command: object) -> tuple[str, ...]:
    if not isinstance(command, list) or not command:
        raise ValueError("invalid command")
    normalized = []
    for command_part in command:
        if not isinstance(command_part, str) or not command_part.strip():
            raise ValueError("invalid command")
        normalized.append(command_part)
    return tuple(normalized)


def _restricted_environment() -> dict[str, str]:
    # Bootstrap mode intentionally passes only common process/runtime variables.
    allow = {"PATH", "PYTHONPATH", "VIRTUAL_ENV", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME", "USERPROFILE"}
    return {key: value for key, value in os.environ.items() if key in allow}
