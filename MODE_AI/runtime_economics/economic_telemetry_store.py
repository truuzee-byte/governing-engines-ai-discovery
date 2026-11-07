from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Optional

from runtime_economics.provider_request_telemetry import (
    ProviderRequestTelemetry,
)


class EconomicTelemetryStore:
    """
    Append-only persistence for provider request telemetry.

    This store does not:
    - calculate economic conclusions
    - calculate ROI
    - classify waste
    - alter runtime behavior
    - rewrite existing records

    One JSON object is appended per provider request.
    """

    _write_lock = Lock()

    def __init__(self, storage_path: Optional[str] = None) -> None:
        if storage_path is None:
            project_root = Path(__file__).resolve().parents[1]
            storage_path = (
                project_root
                / "runtime_data"
                / "economic_telemetry"
                / "provider_requests.jsonl"
            )

        self.storage_path = Path(storage_path)

    def ensure_storage(self) -> None:
        self.storage_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if not self.storage_path.exists():
            self.storage_path.touch()

    def append(
        self,
        telemetry: ProviderRequestTelemetry,
    ) -> str:
        """
        Persist one provider request telemetry record.

        Returns the telemetry evidence reference.
        """
        self.ensure_storage()

        record = telemetry.to_dict()

        with self._write_lock:
            with self.storage_path.open(
                "a",
                encoding="utf-8",
            ) as file:
                file.write(
                    json.dumps(
                        record,
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                )
                file.write("\n")

        return telemetry.telemetry_id