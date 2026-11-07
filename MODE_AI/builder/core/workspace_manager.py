from __future__ import annotations

from pathlib import Path
from typing import List


def create_workspace(artifact_root: str, required_directories: list) -> list[str]:
    if not isinstance(artifact_root, str) or not artifact_root.strip():
        raise ValueError("artifact_root must not be empty")
    if not isinstance(required_directories, list):
        raise ValueError("required_directories must be a list")

    root_path = Path(artifact_root).resolve()
    root_path.mkdir(parents=True, exist_ok=True)
    created_directories: List[str] = []

    for directory in required_directories:
        relative_directory = _validate_relative_path(directory)
        directory_path = (root_path / relative_directory).resolve()
        if not _is_inside_root(directory_path, root_path):
            raise ValueError("directory path escapes artifact_root")
        directory_path.mkdir(parents=True, exist_ok=True)
        created_directories.append(str(directory_path))

    return created_directories


def _validate_relative_path(relative_path: object) -> str:
    if not isinstance(relative_path, str) or not relative_path.strip():
        raise ValueError("invalid directory path")
    normalized = relative_path.strip().replace("\\", "/")
    candidate = Path(normalized)
    if candidate.is_absolute() or any(part == ".." for part in candidate.parts):
        raise ValueError("invalid directory path")
    return normalized


def _is_inside_root(path: Path, root_path: Path) -> bool:
    try:
        path.relative_to(root_path)
        return True
    except ValueError:
        return False
