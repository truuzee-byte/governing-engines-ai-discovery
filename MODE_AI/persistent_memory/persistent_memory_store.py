from __future__ import annotations

import json
import sqlite3
from io import StringIO
from data_governance.custody_json import load as load_custody_json
from learning.contracts import digest
from pathlib import Path

from persistent_memory.persistent_memory_record import (
    PersistentMemoryConsentStatus,
    PersistentMemoryDomain,
    PersistentMemoryRecord,
    PersistentMemoryStatus,
    PersistentMemoryStorageScope,
    utc_now_iso,
)


DEFAULT_MEMORY_DIR = Path("runtime_data") / "persistent_memory"


class PersistentMemoryStore:
    def __init__(
        self,
        storage_dir: Path | str = DEFAULT_MEMORY_DIR,
    ) -> None:
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.database=self.storage_dir/'memory_versions.sqlite3'
        with sqlite3.connect(self.database) as db:
            db.execute('CREATE TABLE IF NOT EXISTS versions (operator TEXT, identity TEXT, version INTEGER, payload TEXT, checksum TEXT, PRIMARY KEY(operator,identity,version))')
            db.execute('CREATE TABLE IF NOT EXISTS uses (operator TEXT, payload TEXT)')

    def save_record(
        self,
        record: PersistentMemoryRecord,
    ) -> PersistentMemoryRecord:
        self._validate_operator_scope(record.operator_id)
        self._record_path(record.operator_id,record.memory_id)

        from data_governance.memory_governance import admissible
        PersistentMemoryRecord.from_dict(record.to_dict())
        if not admissible(record):raise PermissionError('Governance approval does not bind this memory version')
        with sqlite3.connect(self.database,timeout=10) as db:
            db.execute('BEGIN IMMEDIATE')
            rows=db.execute('SELECT payload,checksum FROM versions WHERE operator=? AND identity=? ORDER BY version',(record.operator_id,record.memory_id)).fetchall()
            history=self._verify(rows)
            legacy_path=self._record_path(record.operator_id,record.memory_id)
            imported_legacy=False
            if not history and legacy_path.is_file():
                legacy=self._load_legacy(record.operator_id,record.memory_id)
                if legacy.operator_id!=record.operator_id or legacy.memory_id!=record.memory_id:raise ValueError('Legacy memory identity mismatch')
                legacy.version=1;legacy.previous_hash=None
                original=legacy.to_dict();checksum=digest(original)
                db.execute('INSERT INTO versions VALUES(?,?,?,?,?)',(record.operator_id,record.memory_id,1,json.dumps(original,sort_keys=True),checksum))
                rows=[(json.dumps(original),checksum)];history=[original];imported_legacy=True
            if history and record.version!=history[-1]['version'] and not (imported_legacy and record.version==0):raise ValueError('Stale memory update')
            record.version=len(history)+1
            record.previous_hash=rows[-1][1] if rows else None
            payload=record.to_dict()
            db.execute('INSERT INTO versions VALUES(?,?,?,?,?)',(record.operator_id,record.memory_id,record.version,json.dumps(payload,sort_keys=True),digest(payload)))
        return record

    def _verify(self,rows):
        previous=None;history=[]
        for raw,checksum in rows:
            value=load_custody_json(StringIO(raw))
            if digest(value)!=checksum or value.get('previous_hash')!=previous or value.get('version')!=len(history)+1:
                raise ValueError('Memory version lineage integrity failure')
            previous=checksum;history.append(value)
        return history

    def history(self,operator_id,memory_id):
        self._validate_operator_scope(operator_id)
        with sqlite3.connect(self.database) as db:
            rows=db.execute('SELECT payload,checksum FROM versions WHERE operator=? AND identity=? ORDER BY version',(operator_id,memory_id)).fetchall()
        history=self._verify(rows)
        if any(v['operator_id']!=operator_id or v['memory_id']!=memory_id for v in history):raise ValueError('Memory identity mismatch')
        return history

    def record_use(self,operator_id,payload):
        self._validate_operator_scope(operator_id)
        with sqlite3.connect(self.database) as db:db.execute('INSERT INTO uses VALUES(?,?)',(operator_id,json.dumps(payload,sort_keys=True)))

    def uses(self,operator_id):
        with sqlite3.connect(self.database) as db:
            return [json.loads(row[0]) for row in db.execute('SELECT payload FROM uses WHERE operator=?',(operator_id,))]

    def load_record(
        self,
        operator_id: str,
        memory_id: str,
    ) -> PersistentMemoryRecord | None:
        self._validate_operator_scope(operator_id)

        versions=self.history(operator_id,memory_id)
        if versions:return PersistentMemoryRecord.from_dict(versions[-1])

        path = self._record_path(
            operator_id=operator_id,
            memory_id=memory_id,
        )

        if not path.exists():
            return None

        return self._load_legacy(operator_id,memory_id)

    def _load_legacy(self,operator_id,memory_id):
        path=self._record_path(operator_id,memory_id)
        with path.open(encoding='utf-8') as stream:
            record=PersistentMemoryRecord.from_dict(load_custody_json(stream))
        if record.operator_id!=operator_id or record.memory_id!=memory_id:
            raise ValueError('Legacy memory identity mismatch')
        return record

    def load_records_for_operator(
        self,
        operator_id: str,
        include_inactive: bool = False,
    ) -> list[PersistentMemoryRecord]:
        self._validate_operator_scope(operator_id)

        operator_dir = self._operator_dir(operator_id)

        records: list[PersistentMemoryRecord] = []

        with sqlite3.connect(self.database) as db:
            identities=[row[0] for row in db.execute('SELECT DISTINCT identity FROM versions WHERE operator=?',(operator_id,))]
        for identity in identities:
            record=self.load_record(operator_id,identity)
            if include_inactive or record.status==PersistentMemoryStatus.ACTIVE:records.append(record)

        for path in sorted(operator_dir.glob("*.json")):
            if path.stem in identities:continue
            record = self._load_legacy(operator_id,path.stem)

            if include_inactive is False:
                if record.status != PersistentMemoryStatus.ACTIVE:
                    continue

            records.append(record)

        return records

    def update_record(
        self,
        operator_id: str,
        memory_id: str,
        new_content: str,
    ) -> PersistentMemoryRecord:
        self._validate_operator_scope(operator_id)

        record = self.load_record(
            operator_id=operator_id,
            memory_id=memory_id,
        )

        if record is None:
            raise FileNotFoundError(
                f"Persistent Memory record not found: {memory_id}"
            )

        record.content = new_content
        record.updated_at = utc_now_iso()
        record.last_confirmed_at = record.updated_at

        return self.save_record(record)

    def update_record_metadata(
        self,
        operator_id: str,
        memory_id: str,
        *,
        domain: PersistentMemoryDomain | None = None,
        data_category: str | None = None,
        storage_scope: PersistentMemoryStorageScope | None = None,
        consent_status: PersistentMemoryConsentStatus | None = None,
        expiration_policy: str | None = None,
        operator_can_update: bool | None = None,
        operator_can_delete: bool | None = None,
    ) -> PersistentMemoryRecord:
        self._validate_operator_scope(operator_id)

        record = self.load_record(
            operator_id=operator_id,
            memory_id=memory_id,
        )

        if record is None:
            raise FileNotFoundError(
                f"Persistent Memory record not found: {memory_id}"
            )

        if domain is not None:
            record.domain = domain

        if data_category is not None:
            record.data_category = data_category

        if storage_scope is not None:
            record.storage_scope = storage_scope

        if consent_status is not None:
            record.consent_status = consent_status

        if expiration_policy is not None:
            record.expiration_policy = expiration_policy

        if operator_can_update is not None:
            record.operator_can_update = operator_can_update

        if operator_can_delete is not None:
            record.operator_can_delete = operator_can_delete

        record.updated_at = utc_now_iso()

        return self.save_record(record)

    def deprecate_record(
        self,
        operator_id: str,
        memory_id: str,
    ) -> PersistentMemoryRecord:
        self._validate_operator_scope(operator_id)

        record = self.load_record(
            operator_id=operator_id,
            memory_id=memory_id,
        )

        if record is None:
            raise FileNotFoundError(
                f"Persistent Memory record not found: {memory_id}"
            )

        record.status = PersistentMemoryStatus.DEPRECATED
        record.updated_at = utc_now_iso()
        record.last_confirmed_at = record.updated_at

        return self.save_record(record)

    def reject_record(
        self,
        operator_id: str,
        memory_id: str,
    ) -> PersistentMemoryRecord:
        self._validate_operator_scope(operator_id)

        record = self.load_record(
            operator_id=operator_id,
            memory_id=memory_id,
        )

        if record is None:
            raise FileNotFoundError(
                f"Persistent Memory record not found: {memory_id}"
            )

        record.status = PersistentMemoryStatus.REJECTED
        record.updated_at = utc_now_iso()
        record.last_confirmed_at = record.updated_at

        return self.save_record(record)

    def revoke_consent(
        self,
        operator_id: str,
        memory_id: str,
    ) -> PersistentMemoryRecord:
        self._validate_operator_scope(operator_id)

        record = self.load_record(
            operator_id=operator_id,
            memory_id=memory_id,
        )

        if record is None:
            raise FileNotFoundError(
                f"Persistent Memory record not found: {memory_id}"
            )

        record.consent_status = PersistentMemoryConsentStatus.REVOKED
        record.status = PersistentMemoryStatus.DEPRECATED
        record.updated_at = utc_now_iso()
        record.last_confirmed_at = record.updated_at

        return self.save_record(record)

    def delete_record_file(
        self,
        operator_id: str,
        memory_id: str,
    ) -> bool:
        raise PermissionError('Use governed REMOVE; memory history is preserved')

    def search_records(
        self,
        operator_id: str,
        query: str = "",
        include_inactive: bool = False,
        domain: PersistentMemoryDomain | None = None,
        data_category: str | None = None,
        approved_only: bool = True,
    ) -> list[PersistentMemoryRecord]:
        self._validate_operator_scope(operator_id)

        normalized_query = query.strip().lower()

        records = self.load_records_for_operator(
            operator_id=operator_id,
            include_inactive=include_inactive,
        )

        filtered_records: list[PersistentMemoryRecord] = []

        for record in records:
            if approved_only:
                if record.storage_scope != PersistentMemoryStorageScope.PERSISTENT:
                    continue

                if record.consent_status != PersistentMemoryConsentStatus.APPROVED:
                    continue

            if domain is not None and record.domain != domain:
                continue

            if data_category is not None and record.data_category != data_category:
                continue

            if normalized_query != "":
                if not self._record_matches_query(
                    record=record,
                    normalized_query=normalized_query,
                ):
                    continue

            filtered_records.append(record)

        return filtered_records

    def _record_matches_query(
        self,
        record: PersistentMemoryRecord,
        normalized_query: str,
    ) -> bool:
        searchable_values = (
            record.content,
            record.memory_type.value,
            record.domain.value,
            record.data_category,
            record.status.value,
            record.storage_scope.value,
            record.consent_status.value,
        )

        return any(
            normalized_query in value.lower()
            for value in searchable_values
            if isinstance(value, str)
        )

    def _operator_dir(
        self,
        operator_id: str,
    ) -> Path:
        self._validate_operator_scope(operator_id)
        return self.storage_dir / operator_id

    def _record_path(
        self,
        operator_id: str,
        memory_id: str,
    ) -> Path:
        self._validate_operator_scope(operator_id)

        if not isinstance(memory_id,str) or not memory_id.strip() or any(s in memory_id for s in ('/','\\','..',':')):
            raise ValueError("memory_id cannot be empty")
        from memory.thread_store import ThreadStore
        ThreadStore._validate_identity(memory_id)

        return self._operator_dir(operator_id) / f"{memory_id}.json"

    def _validate_operator_scope(
        self,
        operator_id: str,
    ) -> None:
        if not isinstance(operator_id, str):
            raise TypeError("operator_id must be a string")

        if operator_id.strip() == "":
            raise ValueError("operator_id cannot be empty")

        if "/" in operator_id or "\\" in operator_id:
            raise ValueError("operator_id cannot contain path separators")

        if ".." in operator_id:
            raise ValueError("operator_id cannot contain relative path access")
        from memory.thread_store import ThreadStore
        ThreadStore._validate_identity(operator_id)
