from __future__ import annotations

import os
from pathlib import Path

import pytest

from builder.execution.workspace_manager import create_workspace


def test_workspace_directories_created(tmp_path) -> None:
    created = create_workspace(str(tmp_path), ["reports"])

    assert (tmp_path / "reports").exists()
    assert str((tmp_path / "reports").resolve()) in created


def test_artifact_root_auto_created(tmp_path) -> None:
    artifact_root = tmp_path / "artifact_root"

    create_workspace(str(artifact_root), [])

    assert artifact_root.exists()


def test_path_traversal_blocked(tmp_path) -> None:
    with pytest.raises(ValueError, match="invalid directory path"):
        create_workspace(str(tmp_path), ["../escape"])


def test_absolute_paths_blocked(tmp_path) -> None:
    with pytest.raises(ValueError, match="directory path escapes artifact_root"):
        create_workspace(str(tmp_path), [str(Path("/absolute/path"))])


def test_invalid_directory_path_rejected(tmp_path) -> None:
    with pytest.raises(ValueError, match="invalid directory path"):
        create_workspace(str(tmp_path), [""])


def test_escaping_artifact_root_rejected(tmp_path, monkeypatch) -> None:
    from builder.execution import workspace_manager

    monkeypatch.setattr(workspace_manager, "_is_unsafe_relative_path", lambda value: False)

    with pytest.raises(ValueError, match="directory path escapes artifact_root"):
        create_workspace(str(tmp_path), ["../escape"])