from __future__ import annotations

import json
from pathlib import Path

from builder.core.build_models import BuildReceipt


def create_build_receipt(
    intent_id: str,
    build_id: str,
    snapshot_hash: str,
    stages_checked: list,
    drift_detected: bool,
    final_status: str,
    files_written: list | None = None,
    directories_created: list | None = None,
    commands_executed: list | None = None,
    validation_results: list | None = None,
    evidence_references: list | None = None,
    blocked_conditions: list | None = None,
) -> BuildReceipt:
    return BuildReceipt(
        intent_id=intent_id,
        build_id=build_id,
        snapshot_hash=snapshot_hash,
        stages_checked=list(stages_checked),
        drift_detected=bool(drift_detected),
        final_status=final_status.strip().upper(),
        files_written=list(files_written or []),
        directories_created=list(directories_created or []),
        commands_executed=list(commands_executed or []),
        validation_results=list(validation_results or []),
        evidence_references=list(evidence_references or []),
        blocked_conditions=list(blocked_conditions or []),
    )


def write_build_receipt(receipt: BuildReceipt, receipt_path: str) -> str:
    if not isinstance(receipt, BuildReceipt):
        raise TypeError("receipt must be BuildReceipt")
    if not isinstance(receipt_path, str) or not receipt_path.strip():
        raise ValueError("receipt_path must not be empty")

    output_path = Path(receipt_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    from uuid import uuid4
    temporary = output_path.with_name(output_path.name + '.' + uuid4().hex + '.tmp')
    with temporary.open("x", encoding="utf-8") as handle:
        json.dump(receipt.to_dict(), handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    temporary.replace(output_path)
    return str(output_path)
