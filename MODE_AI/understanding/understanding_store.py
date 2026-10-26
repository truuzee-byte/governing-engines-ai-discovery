"""Atomic immutable versions and result bundles, isolated by operator/thread/project."""
from contextlib import contextmanager
from pathlib import Path
import json
import sqlite3
from .understanding_record import UnderstandingRecord, digest, primitive, utc_now


class UnderstandingStorageError(RuntimeError):
    pass


class StaleUnderstandingError(UnderstandingStorageError):
    pass


class UnderstandingStore:
    def __init__(self, path="runtime_data/understanding/understanding.sqlite3"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS versions (
                    operator_id TEXT NOT NULL, understanding_id TEXT NOT NULL, version INTEGER NOT NULL,
                    thread_id TEXT NOT NULL, project_id TEXT NOT NULL, subject_id TEXT NOT NULL,
                    domain TEXT NOT NULL, payload TEXT NOT NULL, checksum TEXT NOT NULL,
                    bundle TEXT NOT NULL, PRIMARY KEY(operator_id, understanding_id, version));
                CREATE TABLE IF NOT EXISTS heads (
                    operator_id TEXT NOT NULL, thread_id TEXT NOT NULL, project_id TEXT NOT NULL,
                    subject_id TEXT NOT NULL, domain TEXT NOT NULL, understanding_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    PRIMARY KEY(operator_id, thread_id, project_id, subject_id, domain));
                CREATE TABLE IF NOT EXISTS audit (
                    audit_id INTEGER PRIMARY KEY, operator_id TEXT NOT NULL, understanding_id TEXT NOT NULL,
                    operation TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL);
            """)

    @contextmanager
    def connection(self):
        conn = sqlite3.connect(str(self.path), timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except sqlite3.DatabaseError as exc:
            conn.rollback()
            raise UnderstandingStorageError(f"Understanding database error: {exc}") from exc
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _decode(self, row):
        if row is None:
            return None
        try:
            payload = json.loads(row["payload"])
            bundle = json.loads(row["bundle"])
            if digest({"record": payload, "bundle": bundle}) != row["checksum"]:
                raise ValueError("checksum mismatch")
            record = UnderstandingRecord.from_dict(payload)
            if record.operator_id != row["operator_id"] or record.understanding_id != row["understanding_id"]:
                raise ValueError("identity mismatch")
            return record
        except (ValueError, KeyError, TypeError) as exc:
            raise UnderstandingStorageError(f"corrupt Understanding record: {exc}") from exc

    def get(self, operator_id, understanding_id, version=None):
        with self.connection() as conn:
            if version is None:
                row = conn.execute("SELECT * FROM versions WHERE operator_id=? AND understanding_id=? ORDER BY version DESC LIMIT 1",
                                   (operator_id, understanding_id)).fetchone()
            else:
                row = conn.execute("SELECT * FROM versions WHERE operator_id=? AND understanding_id=? AND version=?",
                                   (operator_id, understanding_id, version)).fetchone()
            return self._decode(row)

    def find_by_subject(self, operator_id, thread_id, project_id, subject_id, domain):
        with self.connection() as conn:
            row = conn.execute("""SELECT v.* FROM versions v JOIN heads h
                ON v.operator_id=h.operator_id AND v.understanding_id=h.understanding_id AND v.version=h.version
                WHERE h.operator_id=? AND h.thread_id=? AND h.project_id=? AND h.subject_id=? AND h.domain=?""",
                (operator_id, thread_id, project_id, subject_id, domain)).fetchone()
            return self._decode(row)

    def history(self, operator_id, understanding_id):
        with self.connection() as conn:
            return [self._decode(row) for row in conn.execute(
                "SELECT * FROM versions WHERE operator_id=? AND understanding_id=? ORDER BY version",
                (operator_id, understanding_id))]

    def query(self, operator_id, **filters):
        allowed = {"thread_id", "project_id", "subject_id", "semantic_domain", "semantic_state",
                   "custody_holder", "validation_status", "active", "min_confidence", "evidence_reference",
                   "updated_after", "updated_before"}
        if set(filters) - allowed:
            raise ValueError("unsupported query filter")
        with self.connection() as conn:
            rows = conn.execute("""SELECT v.* FROM versions v JOIN heads h ON v.operator_id=h.operator_id
                AND v.understanding_id=h.understanding_id AND v.version=h.version WHERE v.operator_id=?""", (operator_id,))
            records = [self._decode(row) for row in rows]
        def match(r):
            for k, v in filters.items():
                if k == "min_confidence" and r.confidence < v: return False
                elif k == "evidence_reference" and not any(e.reference == v for e in r.supporting_evidence): return False
                elif k == "updated_after" and r.updated_at < v: return False
                elif k == "updated_before" and r.updated_at > v: return False
                elif k not in {"min_confidence", "evidence_reference", "updated_after", "updated_before"} and getattr(r, k) != v: return False
            return True
        return [r for r in records if match(r)]

    def commit(self, record, candidate, decision, transition, bundle):
        decision.verify(candidate, transition)
        generated = {"version", "previous_version_id", "rollback_available", "created_at", "updated_at", "updated_by", "transition_history"}
        if ({k: v for k, v in primitive(record).items() if k not in generated} !=
                {k: v for k, v in primitive(candidate).items() if k not in generated}):
            raise ValueError("stored record differs from custody-approved candidate")
        analysis_keys = ("requirements", "relationships", "chains", "chain_map", "decomposition", "principles", "mechanisms", "readiness")
        if candidate.metadata.get("analysis_hash") != digest({k: bundle[k] for k in analysis_keys}):
            raise ValueError("analysis bundle differs from custody-approved structure")
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            key = (record.operator_id, record.thread_id, record.project_id, record.subject_id, record.semantic_domain)
            head = conn.execute("SELECT * FROM heads WHERE operator_id=? AND thread_id=? AND project_id=? AND subject_id=? AND domain=?", key).fetchone()
            current = head["version"] if head else 0
            if current != transition.expected_version or record.version != current + 1:
                raise StaleUnderstandingError("record changed since custody evaluation; reevaluate")
            if head and head["understanding_id"] != record.understanding_id:
                raise StaleUnderstandingError("subject already has an identity")
            payload = primitive(record)
            stored_bundle = primitive(bundle)
            checksum = digest({"record": payload, "bundle": stored_bundle})
            conn.execute("INSERT INTO versions VALUES (?,?,?,?,?,?,?,?,?,?)", (
                record.operator_id, record.understanding_id, record.version, record.thread_id,
                record.project_id, record.subject_id, record.semantic_domain,
                json.dumps(payload, sort_keys=True), checksum, json.dumps(stored_bundle, sort_keys=True)))
            conn.execute("INSERT INTO heads VALUES (?,?,?,?,?,?,?) ON CONFLICT(operator_id,thread_id,project_id,subject_id,domain) DO UPDATE SET version=excluded.version",
                         (*key, record.understanding_id, record.version))
            conn.execute("INSERT INTO audit(operator_id,understanding_id,operation,detail,created_at) VALUES (?,?,?,?,?)",
                         (record.operator_id, record.understanding_id, transition.action,
                          json.dumps(primitive({"decision": decision, "transition": transition})), utc_now()))
        return {"understanding_id": record.understanding_id, "version": record.version,
                "checksum": checksum, "status": "COMMITTED"}

    def record_review(self, candidate, decision, transition, continuity):
        """A denied proposal is auditable; it never replaces the active record."""
        decision.verify_integrity(candidate, transition)
        if decision.permitted:
            raise ValueError("review record expects a denied proposal")
        detail = primitive({"candidate": candidate, "decision": decision,
                            "transition": transition, "continuity": continuity})
        with self.connection() as conn:
            conn.execute("INSERT INTO audit(operator_id,understanding_id,operation,detail,created_at) VALUES (?,?,?,?,?)",
                         (candidate.operator_id, candidate.understanding_id, "REVIEW", json.dumps(detail), utc_now()))

    def audit_history(self, operator_id, understanding_id):
        with self.connection() as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM audit WHERE operator_id=? AND understanding_id=? ORDER BY audit_id",
                                                    (operator_id, understanding_id))]

    def get_bundle(self, operator_id, understanding_id, version=None):
        record = self.get(operator_id, understanding_id, version)
        if record is None: return None
        with self.connection() as conn:
            row = conn.execute("SELECT bundle FROM versions WHERE operator_id=? AND understanding_id=? AND version=?",
                               (operator_id, understanding_id, record.version)).fetchone()
            return json.loads(row[0])

    def delete_permanently(self, operator_id, understanding_id, authority, reason):
        if not (authority.authenticated and authority.may_delete and authority.confirmation_reference
                and authority.holder == operator_id and authority.domain == "OPERATOR" and reason.strip()):
            raise PermissionError("physical deletion requires explicit operator authorization and reason")
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("DELETE FROM heads WHERE operator_id=? AND understanding_id=?", (operator_id, understanding_id))
            conn.execute("DELETE FROM versions WHERE operator_id=? AND understanding_id=?", (operator_id, understanding_id))
            conn.execute("INSERT INTO audit(operator_id,understanding_id,operation,detail,created_at) VALUES (?,?,?,?,?)",
                         (operator_id, understanding_id, "DELETE", json.dumps({"reason": reason, "authority": authority.confirmation_reference}), utc_now()))
