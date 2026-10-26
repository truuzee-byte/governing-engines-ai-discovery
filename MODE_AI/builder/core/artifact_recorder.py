from __future__ import annotations

from builder.core.build_models import BuildManifest, BuildPlan


def create_build_manifest(
    build_plan: BuildPlan,
    artifact_root: str,
    actual_files: list,
    actual_directories: list,
    command_results: list | None = None,
    validation_results: list | None = None,
) -> BuildManifest:
    if not isinstance(build_plan, BuildPlan):
        raise TypeError("build_plan must be BuildPlan")
    if not isinstance(artifact_root, str) or not artifact_root.strip():
        raise ValueError("artifact_root must not be empty")
    if not isinstance(actual_files, list) or not isinstance(actual_directories, list):
        raise TypeError("actual artifact lists are required")

    return BuildManifest(
        build_id=build_plan.build_id,
        spec_id=build_plan.spec_id,
        artifact_root=artifact_root,
        required_files=list(build_plan.required_files),
        required_directories=list(build_plan.required_directories),
        required_outputs=list(build_plan.required_outputs),
        actual_files=list(actual_files),
        actual_directories=list(actual_directories),
        command_results=list(command_results or []),
        validation_results=list(validation_results or []),
    )
