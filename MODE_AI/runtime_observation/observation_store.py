from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4
from dataclasses import fields

from runtime_observation.observation_record import (
    RuntimeObservationRecord,
    RuntimeObservationType,
    utc_now_iso,
)


DEFAULT_OBSERVATION_DIR = (
    Path("runtime_data") / "runtime_observations"
)


class ObservationRetrievalError(RuntimeError):
    """Unreadable evidence is explicit; callers may inspect usable records."""
    def __init__(self, errors, records):
        super().__init__(f"{len(errors)} observation record(s) could not be read")
        self.errors = errors
        self.records = records


class RuntimeObservationStore:
    def __init__(
        self,
        storage_dir: Path | str = DEFAULT_OBSERVATION_DIR,
    ) -> None:
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def save_record(
        self,
        record: RuntimeObservationRecord,
    ) -> RuntimeObservationRecord:
        self._validate_operator_scope(record.operator_id)

        path = self._record_path(
            operator_id=record.operator_id,
            observation_id=record.observation_id,
        )

        path.parent.mkdir(parents=True, exist_ok=True)

        temp_path = path.with_suffix("." + uuid4().hex + ".tmp")

        temp_path.write_text(
            json.dumps(record.to_dict(), indent=2),
            encoding="utf-8",
        )

        temp_path.replace(path)

        return record

    def update_record(
        self,
        record: RuntimeObservationRecord,
    ) -> RuntimeObservationRecord:
        record.updated_at = utc_now_iso()
        return self.save_record(record)

    def record_exists(
        self,
        operator_id: str,
        observation_id: str,
    ) -> bool:
        return self._record_path(
            operator_id=operator_id,
            observation_id=observation_id,
        ).exists()

    def load_record(
        self,
        operator_id: str,
        observation_id: str,
    ) -> RuntimeObservationRecord | None:
        self._validate_operator_scope(operator_id)

        path = self._record_path(
            operator_id=operator_id,
            observation_id=observation_id,
        )

        if not path.exists():
            return None

        data = json.loads(
            path.read_text(encoding="utf-8"),
        )

        if data.get("operator_id") != operator_id:
            raise ValueError("Observation operator scope mismatch")
        return RuntimeObservationRecord.from_dict(data)

    def load_records_for_operator(
        self,
        operator_id: str,
    ) -> list[RuntimeObservationRecord]:
        self._validate_operator_scope(operator_id)

        operator_dir = self._operator_dir(operator_id)

        if not operator_dir.exists():
            return []

        records: list[RuntimeObservationRecord] = []
        errors = []

        for path in sorted(operator_dir.glob("*.json")):
            try:
                data = json.loads(
                    path.read_text(encoding="utf-8"),
                )

                if data.get("operator_id") != operator_id:
                    raise ValueError("Observation operator scope mismatch")
                records.append(
                    RuntimeObservationRecord.from_dict(data)
                )
            except Exception as exc:
                errors.append({"path": str(path), "error": type(exc).__name__, "detail": str(exc)})

        if errors:
            raise ObservationRetrievalError(errors, records)
        return records

    def load_records_by_thread(
        self,
        operator_id: str,
        thread_id: str,
    ) -> list[RuntimeObservationRecord]:
        return [
            record
            for record in self.load_records_for_operator(operator_id)
            if record.thread_id == thread_id
        ]

    def load_records_by_session(
        self,
        operator_id: str,
        runtime_session_id: str,
    ) -> list[RuntimeObservationRecord]:
        return [
            record
            for record in self.load_records_for_operator(operator_id)
            if record.runtime_session_id == runtime_session_id
        ]

    def load_records_by_type(
        self,
        operator_id: str,
        observation_type: RuntimeObservationType,
    ) -> list[RuntimeObservationRecord]:
        return [
            record
            for record in self.load_records_for_operator(operator_id)
            if observation_type in record.observation_types
        ]

    def load_recent_records(
        self,
        operator_id: str,
        limit: int = 25,
    ) -> list[RuntimeObservationRecord]:
        records = sorted(
            self.load_records_for_operator(operator_id),
            key=lambda r: r.created_at,
            reverse=True,
        )

        return records[:limit]

    def count_records(
        self,
        operator_id: str,
    ) -> int:
        return len(
            self.load_records_for_operator(operator_id)
        )

    def search_records(
        self,
        operator_id: str,
        query: str,
    ) -> list[RuntimeObservationRecord]:
        self._validate_operator_scope(operator_id)

        normalized = query.strip().lower()

        if normalized == "":
            return self.load_records_for_operator(operator_id)

        records = self.load_records_for_operator(operator_id)

        return [
            record
            for record in records
            if (
                normalized in record.input_text.lower()
                or normalized in record.response_text.lower()
                or normalized in record.knowledge_domain.lower()
                or normalized in record.runtime_state_start.lower()
                or normalized in record.runtime_state_end.lower()
            )
        ]

    def query_records(self, operator_id: str, **criteria):
        """Exact canonical field filters, including nested evidence identifiers.

        Multiple filters are ANDed. Lists match an item; objects match supplied
        key/value subsets. No semantic similarity or recurrence judgment.
        """
        allowed = {f.name for f in fields(RuntimeObservationRecord)}
        unknown = set(criteria) - allowed
        if unknown:
            raise ValueError(f"Unknown observation filters: {sorted(unknown)}")
        def matches(actual, expected):
            if isinstance(expected, dict) and set(expected) in ({"gt"}, {"gte"}, {"lt"}, {"lte"}):
                if isinstance(actual, bool) or not isinstance(actual, (int, float)):
                    return False
                operation, limit = next(iter(expected.items()))
                if isinstance(limit, bool) or not isinstance(limit, (int, float)):
                    raise ValueError("Numeric occurrence filter requires a number")
                return {"gt": actual > limit, "gte": actual >= limit,
                        "lt": actual < limit, "lte": actual <= limit}[operation]
            if isinstance(actual, list):
                return actual == expected or any(matches(item, expected) for item in actual)
            if isinstance(actual, dict):
                if isinstance(expected, dict):
                    return all(k in actual and matches(actual[k], v) for k, v in expected.items())
                return any(matches(v, expected) for v in actual.values())
            return actual == expected
        return [r for r in self.load_records_for_operator(operator_id)
                if all(matches(r.to_dict().get(k), v) for k, v in criteria.items())]

    def export_operator_records(
        self,
        operator_id: str,
        destination: Path | str,
    ) -> Path:
        records = [
            record.to_dict()
            for record in self.load_records_for_operator(
                operator_id
            )
        ]

        destination = Path(destination)

        destination.write_text(
            json.dumps(records, indent=2),
            encoding="utf-8",
        )

        return destination

    def delete_record_file(
        self,
        operator_id: str,
        observation_id: str,
    ) -> bool:
        self._validate_operator_scope(operator_id)

        path = self._record_path(
            operator_id=operator_id,
            observation_id=observation_id,
        )

        if not path.exists():
            return False

        path.unlink()
        return True

    def _operator_dir(
        self,
        operator_id: str,
    ) -> Path:
        self._validate_operator_scope(operator_id)
        return self.storage_dir / operator_id

    def _record_path(
        self,
        operator_id: str,
        observation_id: str,
    ) -> Path:
        self._validate_operator_scope(operator_id)

        if not isinstance(observation_id, str) or not observation_id.strip() or any(c in observation_id for c in ("/", "\\", "..", ":")) :
            raise ValueError(
                "observation_id cannot be empty"
            )

        return (
            self._operator_dir(operator_id)
            / f"{observation_id}.json"
        )

    def _validate_operator_scope(
        self,
        operator_id: str,
    ) -> None:
        if not isinstance(operator_id, str):
            raise TypeError(
                "operator_id must be a string"
            )

        if operator_id.strip() == "":
            raise ValueError(
                "operator_id cannot be empty"
            )

        if "/" in operator_id or "\\" in operator_id:
            raise ValueError(
                "operator_id cannot contain path separators"
            )

        if ".." in operator_id:
            raise ValueError(
                "operator_id cannot contain relative path access"
            )