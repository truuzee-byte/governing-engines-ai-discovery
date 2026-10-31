from __future__ import annotations

import hashlib
from pathlib import Path

from builder.components.manifest_validator import validate_manifest_integrity
from builder.core.build_models import BuildManifest, BuildPlan


def validate_build_plan(build_plan: BuildPlan) -> bool:
    if not isinstance(build_plan, BuildPlan):
        return False
    required_strings = [
        build_plan.build_id,
        build_plan.spec_id,
        build_plan.snapshot_hash,
        build_plan.target_name,
        build_plan.tool_type,
    ]
    if any(not isinstance(v, str) or not v.strip() for v in required_strings):
        return False
    if not isinstance(build_plan.approved_components, list):
        return False
    if len(set(build_plan.required_files)) != len(build_plan.required_files):
        return False
    if len(set(build_plan.required_directories)) != len(build_plan.required_directories):
        return False
    if any(path not in build_plan.required_files for path in build_plan.approved_files):
        return False
    if any(not isinstance(command, list) or not command for command in build_plan.approved_commands):
        return False
    if any(not isinstance(command, list) or not command for command in build_plan.validation_commands):
        return False
    return True


def validate_build_manifest(build_manifest: BuildManifest) -> bool:
    return validate_manifest_integrity(build_manifest)


def evaluate_validation_results(
    build_plan: BuildPlan,
    command_results: list[dict],
    validation_results: list[dict],
) -> str:
    if not isinstance(build_plan, BuildPlan):
        return "FAIL"

    # Failures take precedence over missing evidence, regardless of result order.
    if any(result.get("state") in {"FAILED", "FAIL"} for result in validation_results):
        return "FAIL"
    if any(result.get("returncode") != 0 for result in command_results):
        return "FAIL"
    if any(result.get("state") == "BLOCKED" for result in validation_results):
        return "BLOCKED"
    if any(result.get("state") != "PASSED" for result in validation_results):
        return "UNPROVEN"

    # Syntax checks and successful build commands alone do not prove the
    # declared validation requirements. Requirements without an executable
    # validation command remain unproven.
    if not build_plan.validation_commands or not build_plan.validation_requirements:
        return "UNPROVEN"

    for command in build_plan.validation_commands:
        if not any(result.get("command") == command and result.get("returncode") == 0
                   for result in command_results):
            return "UNPROVEN"
        if not any(result.get("command") == command and result.get("state") == "PASSED"
                   and result.get("returncode") == 0 for result in validation_results):
            return "UNPROVEN"

    for path in build_plan.required_files:
        if Path(path).suffix.lower() == ".py" and not any(
            result.get("validation_type") == "python_compile"
            and result.get("path") == path and result.get("state") == "PASSED"
            for result in validation_results
        ):
            return "UNPROVEN"

    return "PASS"


def validate_python_artifacts(artifact_root: str, required_files: list[str]) -> list[dict]:
    """Compile the final on-disk Python bytes without executing or writing pyc files."""
    root = Path(artifact_root).resolve()
    results = []
    for relative_path in required_files:
        if Path(relative_path).suffix.lower() != ".py":
            continue
        result = {"validation_type": "python_compile", "path": relative_path,
                  "state": "FAILED", "executed": False}
        try:
            target = (root / relative_path).resolve()
            target.relative_to(root)
            source = target.read_bytes()
            result["sha256"] = hashlib.sha256(source).hexdigest()
            result["executed"] = True
            compile(source, str(target), "exec", dont_inherit=True)
            result["state"] = "PASSED"
        except (OSError, ValueError, SyntaxError) as exc:
            if isinstance(exc, OSError):
                result["state"] = "UNPROVEN"
            result["error_type"] = type(exc).__name__
            result["error"] = str(exc)
        results.append(result)
    return results
