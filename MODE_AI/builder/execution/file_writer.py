from __future__ import annotations

from pathlib import Path
from typing import List


def write_approved_files(
    artifact_root: str,
    approved_files: dict,
    required_files: list,
) -> list[str]:
    if not isinstance(artifact_root, str):
        raise ValueError("artifact_root must be a string")

    if artifact_root.strip() == "":
        raise ValueError("artifact_root must not be empty")

    if not isinstance(approved_files, dict):
        raise ValueError("approved_files must be a dictionary")

    if not isinstance(required_files, list):
        raise ValueError("required_files must be a list")

    root_path = Path(artifact_root).resolve()
    root_path.mkdir(parents=True, exist_ok=True)

    required_file_set = set()

    for required_file in required_files:
        if not isinstance(required_file, str):
            raise ValueError("invalid file path")

        normalized_required_file = required_file.strip()

        if normalized_required_file == "":
            raise ValueError("invalid file path")

        if _is_unsafe_relative_path(normalized_required_file):
            raise ValueError("invalid file path")

        required_file_set.add(normalized_required_file)

    for approved_file_path in approved_files.keys():
        if not isinstance(approved_file_path, str):
            raise ValueError("invalid file path")

        normalized_approved_path = approved_file_path.strip()

        if normalized_approved_path == "":
            raise ValueError("invalid file path")

        if _is_unsafe_relative_path(normalized_approved_path):
            raise ValueError("invalid file path")

        if normalized_approved_path not in required_file_set:
            raise ValueError("unapproved file")

    for required_file in required_file_set:
        if required_file not in approved_files:
            raise ValueError("missing required file")

    written_files: List[str] = []

    for relative_file_path, file_contents in approved_files.items():
        if not isinstance(file_contents, str):
            raise ValueError("invalid file path")

        normalized_relative_file_path = relative_file_path.strip()
        output_path = (root_path / normalized_relative_file_path).resolve()

        if not _is_inside_root(
            path=output_path,
            root_path=root_path,
        ):
            raise ValueError("file path escapes artifact_root")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open(
            "w",
            encoding="utf-8",
        ) as handle:
            handle.write(file_contents)

        written_files.append(str(output_path))

    return written_files


def _is_unsafe_relative_path(
    relative_path: str,
) -> bool:
    candidate = Path(relative_path)

    if candidate.is_absolute():
        return True

    return any(part == ".." for part in candidate.parts)


def _is_inside_root(
    path: Path,
    root_path: Path,
) -> bool:
    try:
        path.relative_to(root_path)
        return True

    except ValueError:
        return False