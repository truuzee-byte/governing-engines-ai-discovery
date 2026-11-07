from __future__ import annotations

import pytest

from builder.core.build_models import BuildManifest
from builder.library.library_resolver import ResolvedLibraryArtifact, resolve_manifest_artifacts


def test_required_files_resolve_as_file_artifacts() -> None:
    artifacts = resolve_manifest_artifacts(_manifest())

    assert artifacts[0].artifact_type == "file"


def test_required_directories_resolve_as_directory_artifacts() -> None:
    artifacts = resolve_manifest_artifacts(_manifest())

    assert artifacts[1].artifact_type == "directory"


def test_ordering_preserved() -> None:
    artifacts = resolve_manifest_artifacts(_manifest())

    assert [artifact.artifact_path for artifact in artifacts] == [
        "reports/result.txt",
        "reports",
    ]


def test_invalid_artifact_path_rejected() -> None:
    manifest = _manifest(required_files=[""])

    with pytest.raises(ValueError, match="invalid artifact path"):
        resolve_manifest_artifacts(manifest)


def test_invalid_build_manifest_rejected() -> None:
    with pytest.raises(ValueError, match="invalid build_manifest"):
        resolve_manifest_artifacts("not-a-manifest")


def _manifest(required_files: list | None = None) -> BuildManifest:
    return BuildManifest(
        build_id="build_001",
        spec_id="spec_001",
        artifact_root="artifacts",
        required_files=required_files if required_files is not None else ["reports/result.txt"],
        required_directories=["reports"],
        required_outputs=[],
        actual_files=[],
        actual_directories=[],
    )