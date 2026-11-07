from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Dict, List


def run_approved_commands(
    commands: list,
    approved_commands: list,
    cwd: str,
) -> list[dict]:
    if not isinstance(commands, list):
        raise ValueError("commands must be a list")

    if not isinstance(approved_commands, list):
        raise ValueError("approved_commands must be a list")

    if not isinstance(cwd, str):
        raise ValueError("cwd must be a string")

    if cwd.strip() == "":
        raise ValueError("cwd must not be empty")

    cwd_path = Path(cwd).resolve()

    approved_command_signatures = set()

    for approved_command in approved_commands:
        approved_command_signatures.add(
            _command_signature(
                approved_command,
            )
        )

    results: List[Dict[str, object]] = []

    for command in commands:
        command_signature = _command_signature(
            command,
        )

        if command_signature not in approved_command_signatures:
            raise ValueError("unapproved command")

        completed_process = subprocess.run(
            command,
            cwd=str(cwd_path),
            shell=False,
            capture_output=True,
            text=True,
            check=False,
        )

        results.append(
            {
                "command": list(command),
                "returncode": completed_process.returncode,
                "stdout": completed_process.stdout,
                "stderr": completed_process.stderr,
            }
        )

    return results


def _command_signature(
    command: object,
) -> tuple[str, ...]:
    if not isinstance(command, list):
        raise ValueError("invalid command")

    if len(command) == 0:
        raise ValueError("invalid command")

    normalized_command = []

    for command_part in command:
        if not isinstance(command_part, str):
            raise ValueError("invalid command")

        if command_part.strip() == "":
            raise ValueError("invalid command")

        normalized_command.append(command_part)

    return tuple(normalized_command)