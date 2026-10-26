from __future__ import annotations

from pathlib import Path

import pytest

from builder.execution.file_writer import write_approved_files


def test_approved_files_written(tmp_path) -> None:
    written = write_approved_files(
        artifact_root=str(tmp_path),
        approved_files={"reports/result.txt": "ok"},
        required_files=["reports/result.txt"],
    )

    assert (tmp_path / "reports" / "result.txt").read_text(encoding="utf-8") == "ok"
    assert str((tmp_path / "reports" / "result.txt").resolve()) in written


def test_required_files_enforced(tmp_path) -> None:
    with pytest.raises(ValueError, match="missing required file"):
        write_approved_files(
            artifact_root=str(tmp_path),
            approved_files={},
            required_files=["reports/result.txt"],
        )


def test_unapproved_files_blocked(tmp_path) -> None:
    with pytest.raises(ValueError, match="unapproved file"):
        write_approved_files(
            artifact_root=str(tmp_path),
            approved_files={"reports/extra.txt": "bad"},
            required_files=["reports/result.txt"],
        )


def test_path_traversal_blocked(tmp_path) -> None:
    with pytest.raises(ValueError, match="invalid file path"):
        write_approved_files(
            artifact_root=str(tmp_path),
            approved_files={"../escape.txt": "bad"},
            required_files=["../escape.txt"],
        )


def test_absolute_paths_blocked(tmp_path) -> None:
    absolute_path = str(Path("/absolute/file.txt"))

    with pytest.raises(ValueError, match="file path escapes artifact_root"):
        write_approved_files(
            artifact_root=str(tmp_path),
            approved_files={absolute_path: "bad"},
            required_files=[absolute_path],
        )


def test_escaping_artifact_root_blocked(tmp_path, monkeypatch) -> None:
    from builder.execution import file_writer

    monkeypatch.setattr(file_writer, "_is_unsafe_relative_path", lambda value: False)

    with pytest.raises(ValueError, match="file path escapes artifact_root"):
        write_approved_files(
            artifact_root=str(tmp_path),
            approved_files={"../escape.txt": "bad"},
            required_files=["../escape.txt"],
        )


def test_missing_required_file_rejected(tmp_path) -> None:
    with pytest.raises(ValueError, match="missing required file"):
        write_approved_files(
            artifact_root=str(tmp_path),
            approved_files={"reports/other.txt": "ok"},
            required_files=["reports/result.txt", "reports/other.txt"],
        )