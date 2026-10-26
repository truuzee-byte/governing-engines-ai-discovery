from __future__ import annotations

from builder.core.build_models import BuildManifest
from builder.library.manifest_validator import validate_manifest_integrity


def test_valid_manifest_passes() -> None:
    assert validate_manifest_integrity(_manifest()) is True


def test_undeclared_actual_file_fails() -> None:
    manifest = _manifest(actual_files=["reports/extra.txt"])

    assert validate_manifest_integrity(manifest) is False


def test_undeclared_actual_directory_fails() -> None:
    manifest = _manifest(actual_directories=["extra"])

    assert validate_manifest_integrity(manifest) is False


def test_malformed_lists_fail() -> None:
    manifest = _manifest()
    object.__setattr__(manifest, "actual_files", "not-a-list")

    assert validate_manifest_integrity(manifest) is False


def test_invalid_build_manifest_fails() -> None:
    assert validate_manifest_integrity("not-a-manifest") is False


def _manifest(
    actual_files: list | None = None,
    actual_directories: list | None = None,
) -> BuildManifest:
    return BuildManifest(
        build_id="build_001",
        spec_id="spec_001",
        artifact_root="artifacts",
        required_files=["reports/result.txt"],
        required_directories=["reports"],
        required_outputs=[],
        actual_files=actual_files if actual_files is not None else ["reports/result.txt"],
        actual_directories=actual_directories if actual_directories is not None else ["reports"],
    )