"""Prepare authorized versions; commit only after every analysis stage succeeds."""
from dataclasses import dataclass, replace
from .understanding_record import utc_now, digest, primitive


ACTIONS = frozenset({"CREATE", "NO_CHANGE", "ADD_EVIDENCE", "REFINE", "EXPAND", "REDUCE",
    "MARK_PROVISIONAL", "CONFIRM", "DISPUTE", "CONTRADICT", "SUPERSEDE", "ARCHIVE", "ROLLBACK"})


@dataclass(frozen=True)
class UnderstandingUpdateResult:
    success: bool
    action: str
    previous_record: object = None
    updated_record: object = None
    transition: object = None
    store_receipt: dict | None = None
    rollback_reference: str | None = None
    reason: str = ""


class UnderstandingUpdater:
    def __init__(self, store):
        self.store = store

    def prepare(self, existing, candidate, decision, transition):
        decision.verify(candidate, transition)
        if transition.action not in ACTIONS:
            raise ValueError("unknown update action")
        if existing and existing.version != transition.expected_version:
            raise ValueError("stale evaluated version")
        if transition.action == "NO_CHANGE":
            return existing
        prior = f"{existing.understanding_id}:{existing.version}" if existing else None
        completed = replace(transition, approved_state=candidate.semantic_state,
                            approved_by=decision.custody_holder, policy_result=decision.decision.value,
                            completed_at=utc_now(), rollback_reference=prior)
        return replace(candidate, version=transition.expected_version + 1,
            previous_version_id=prior, rollback_available=existing is not None,
            created_at=existing.created_at if existing else candidate.created_at,
            updated_at=utc_now(), updated_by=decision.custody_holder,
            transition_history=(existing.transition_history if existing else ()) + (primitive(completed),))

    def apply(self, existing, candidate, decision, transition, bundle):
        record = self.prepare(existing, candidate, decision, transition)
        if transition.action == "NO_CHANGE":
            current = self.store.get(existing.operator_id, existing.understanding_id)
            if current.version != existing.version:
                from .understanding_store import StaleUnderstandingError
                raise StaleUnderstandingError("NO_CHANGE evaluated against stale version")
            return UnderstandingUpdateResult(True, "NO_CHANGE", existing, existing, transition,
                                             reason="Meaning and evidence unchanged.")
        receipt = self.store.commit(record, candidate, decision, transition, bundle)
        return UnderstandingUpdateResult(True, transition.action, existing, record, transition,
                                         receipt, record.previous_version_id, decision.decision_explanation)
