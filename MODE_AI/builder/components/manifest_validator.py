from __future__ import annotations

from pathlib import Path

from builder.core.build_models import BuildManifest


def validate_manifest_integrity(build_manifest: BuildManifest) -> bool:
    if not isinstance(build_manifest, BuildManifest):
        return False

    required_files = set(build_manifest.required_files)
    required_directories = set(build_manifest.required_directories)
    actual_files = set(build_manifest.actual_files)
    actual_directories = set(build_manifest.actual_directories)

    # Every required artifact must exist in the actual manifest.
    if not required_files.issubset(actual_files):
        return False
    if not required_directories.issubset(actual_directories):
        return False

    # No unapproved artifact may appear in the manifest.
    if not actual_files.issubset(required_files):
        return False
    if not actual_directories.issubset(required_directories):
        return False

    root = Path(build_manifest.artifact_root).resolve()
    for relative_path in actual_files:
        target = (root / relative_path).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            return False
        if not target.is_file():
            return False

    for relative_path in actual_directories:
        target = (root / relative_path).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            return False
        if not target.is_dir():
            return False

    return True
