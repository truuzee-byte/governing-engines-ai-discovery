from __future__ import annotations

import json

import pytest

from builder.core.build_models import BuildReceipt
from builder.core.receipt_writer import create_build_receipt, write_build_receipt


def test_build_receipt_creation() -> None:
    receipt = _receipt("PASS")

    assert isinstance(receipt, BuildReceipt)


def test_pass_fail_normalization() -> None:
    receipt = _receipt("pass")

    assert receipt.final_status == "PASS"


def test_invalid_final_status_rejected() -> None:
    with pytest.raises(ValueError):
        _receipt("UNKNOWN")


def test_receipt_json_written_correctly(tmp_path) -> None:
    receipt_path = tmp_path / "receipts" / "build_receipt.json"

    write_build_receipt(_receipt("PASS"), str(receipt_path))

    payload = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert payload["final_status"] == "PASS"


def test_deterministic_json_output(tmp_path) -> None:
    receipt_path = tmp_path / "build_receipt.json"

    write_build_receipt(_receipt("PASS"), str(receipt_path))

    content = receipt_path.read_text(encoding="utf-8")

    assert content.endswith("\n")
    assert '"build_id": "build_001"' in content


def test_parent_directories_auto_created(tmp_path) -> None:
    receipt_path = tmp_path / "nested" / "receipts" / "build_receipt.json"

    write_build_receipt(_receipt("PASS"), str(receipt_path))

    assert receipt_path.exists()


def test_receipt_path_returned(tmp_path) -> None:
    receipt_path = str(tmp_path / "build_receipt.json")

    returned_path = write_build_receipt(_receipt("PASS"), receipt_path)

    assert returned_path == receipt_path


def _receipt(final_status: str) -> BuildReceipt:
    return create_build_receipt(
        intent_id="spec_001",
        build_id="build_001",
        snapshot_hash="hash",
        stages_checked=["build_plan_generated"],
        drift_detected=False,
        final_status=final_status,
    )