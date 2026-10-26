from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from builder.core.build_models import BuildManifest


ALLOWED_ARTIFACT_TYPES = {
    "file",
    "directory",
}


@dataclass(frozen=True)
class ResolvedLibraryArtifact:
    artifact_path: str
    artifact_type: str

    def __post_init__(self) -> None:
        _require_non_empty_string(
            self.artifact_path,
            "artifact_path",
        )

        if not isinstance(self.artifact_type, str):
            raise TypeError("artifact_type must be a string")

        if self.artifact_type not in ALLOWED_ARTIFACT_TYPES:
            raise ValueError("invalid artifact type")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_path": self.artifact_path,
            "artifact_type": self.artifact_type,
        }


def resolve_manifest_artifacts(
    build_manifest: BuildManifest,
) -> list[ResolvedLibraryArtifact]:
    if not isinstance(build_manifest, BuildManifest):
        raise ValueError("invalid build_manifest")

    resolved_artifacts: list[ResolvedLibraryArtifact] = []

    for required_file in build_manifest.required_files:
        if not _is_non_empty_string(required_file):
            raise ValueError("invalid artifact path")

        resolved_artifacts.append(
            ResolvedLibraryArtifact(
                artifact_path=required_file,
                artifact_type="file",
            )
        )

    for required_directory in build_manifest.required_directories:
        if not _is_non_empty_string(required_directory):
            raise ValueError("invalid artifact path")

        resolved_artifacts.append(
            ResolvedLibraryArtifact(
                artifact_path=required_directory,
                artifact_type="directory",
            )
        )

    return resolved_artifacts


def _require_non_empty_string(
    value: Any,
    field_name: str,
) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")

    if value.strip() == "":
        raise ValueError(f"{field_name} must not be empty")


def _is_non_empty_string(
    value: Any,
) -> bool:
    return isinstance(value, str) and value.strip() != ""