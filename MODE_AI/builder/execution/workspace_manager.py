from __future__ import annotations

from pathlib import Path
from typing import Any, List


def create_workspace(
    artifact_root: str,
    required_directories: list,
) -> list[str]:
    if not isinstance(artifact_root, str):
        raise ValueError("artifact_root must be a string")

    if artifact_root.strip() == "":
        raise ValueError("artifact_root must not be empty")

    if not isinstance(required_directories, list):
        raise ValueError("required_directories must be a list")

    root_path = Path(artifact_root).resolve()
    root_path.mkdir(parents=True, exist_ok=True)

    created_directories: List[str] = []

    for directory in required_directories:
        if not isinstance(directory, str):
            raise ValueError("invalid directory path")

        relative_directory = directory.strip()

        if relative_directory == "":
            raise ValueError("invalid directory path")

        if _is_unsafe_relative_path(relative_directory):
            raise ValueError("invalid directory path")

        directory_path = (root_path / relative_directory).resolve()

        if not _is_inside_root(
            path=directory_path,
            root_path=root_path,
        ):
            raise ValueError("directory path escapes artifact_root")

        directory_path.mkdir(parents=True, exist_ok=True)
        created_directories.append(str(directory_path))

    return created_directories


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