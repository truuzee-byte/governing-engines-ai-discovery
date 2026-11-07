from __future__ import annotations

from builder.core.build_models import BuildManifest


def validate_manifest_integrity(
    build_manifest: BuildManifest,
) -> bool:
    if not isinstance(build_manifest, BuildManifest):
        return False

    if not isinstance(build_manifest.required_files, list):
        return False

    if not isinstance(build_manifest.required_directories, list):
        return False

    if not isinstance(build_manifest.required_outputs, list):
        return False

    if not isinstance(build_manifest.actual_files, list):
        return False

    if not isinstance(build_manifest.actual_directories, list):
        return False

    required_files = set(build_manifest.required_files)
    required_directories = set(build_manifest.required_directories)

    for actual_file in build_manifest.actual_files:
        if actual_file not in required_files:
            return False

    for actual_directory in build_manifest.actual_directories:
        if actual_directory not in required_directories:
            return False

    return True