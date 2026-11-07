from __future__ import annotations

from pathlib import Path
from typing import List


def write_approved_files(
    artifact_root: str,
    approved_files: dict,
    required_files: list,
    *, operations: dict[str, str] | None = None,
) -> list[str]:
    if not isinstance(artifact_root, str) or not artifact_root.strip():
        raise ValueError("artifact_root must not be empty")
    if not isinstance(approved_files, dict):
        raise ValueError("approved_files must be a dictionary")
    if not isinstance(required_files, list):
        raise ValueError("required_files must be a list")

    root_path = Path(artifact_root).resolve()
    root_path.mkdir(parents=True, exist_ok=True)

    required_file_set: set[str] = set()
    for required_file in required_files:
        normalized = _validate_relative_path(required_file)
        required_file_set.add(normalized)

    approved_normalized: dict[str, str] = {}
    for raw_path, file_contents in approved_files.items():
        normalized = _validate_relative_path(raw_path)
        if normalized not in required_file_set:
            raise ValueError("unapproved file")
        if not isinstance(file_contents, str):
            raise ValueError("file contents must be a string")
        approved_normalized[normalized] = file_contents

    if set(approved_normalized) != required_file_set:
        raise ValueError("approved_files must exactly match required_files")

    written_files: List[str] = []
    for relative_file_path, file_contents in approved_normalized.items():
        output_path = (root_path / relative_file_path).resolve()
        if not _is_inside_root(output_path, root_path):
            raise ValueError("file path escapes artifact_root")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        operation = (operations or {}).get(relative_file_path)
        if operations is not None and operation not in {"CREATE", "MODIFY"}:
            raise ValueError("missing operation authority")
        if operation == "CREATE":
            # Exclusive creation closes the exists-check/overwrite race.
            with output_path.open("x", encoding="utf-8") as stream:
                stream.write(file_contents)
        elif operation == "MODIFY":
            # r+ cannot silently create a missing file.
            with output_path.open("r+", encoding="utf-8") as stream:
                stream.write(file_contents)
                stream.truncate()
        else:
            output_path.write_text(file_contents, encoding="utf-8")
        written_files.append(str(output_path))

    return written_files


def _validate_relative_path(relative_path: object) -> str:
    if not isinstance(relative_path, str) or not relative_path.strip():
        raise ValueError("invalid file path")
    normalized = relative_path.strip().replace("\\", "/")
    candidate = Path(normalized)
    if candidate.is_absolute() or any(part == ".." for part in candidate.parts):
        raise ValueError("invalid file path")
    return normalized


def _is_inside_root(path: Path, root_path: Path) -> bool:
    try:
        path.relative_to(root_path)
        return True
    except ValueError:
        return False
