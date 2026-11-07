"""Custody decisions bind exact content, identity, action and evaluated version."""
from dataclasses import dataclass, asdict
import hmac
import secrets
from .semantic_custody_policy import SemanticCustodyPolicy, AuthorityContext
from .semantic_transition import SemanticTransitionDecision as Decision
from .semantic_state import SemanticState as S
from .understanding_record import digest, utc_now

_DECISION_KEY = secrets.token_bytes(32)


@dataclass(frozen=True)
class SemanticCustodyDecision:
    decision: Decision
    permitted: bool
    approved_state: S
    approved_meaning: str
    custody_holder: str
    authority_level: str
    evidence_sufficient: bool
    continuity_accepted: bool
    review_required: bool
    confirmation_required: bool
    decision_explanation: str
    policy_rules_applied: tuple[str, ...]
    candidate_hash: str
    transition_hash: str
    expected_version: int
    action: str
    created_at: str
    signature: str = ""

    def payload(self):
        return {key: value for key, value in asdict(self).items() if key != "signature"}

    def verify(self, candidate, transition):
        self.verify_integrity(candidate, transition)
        if not self.permitted:
            raise ValueError("custody decision does not permit a write")

    def verify_integrity(self, candidate, transition):
        expected = hmac.digest(_DECISION_KEY, digest(self.payload()).encode(), "sha256").hex()
        if (not hmac.compare_digest(expected, self.signature)
                or self.candidate_hash != digest(candidate) or self.transition_hash != digest(transition)
                or self.expected_version != transition.expected_version or self.action != transition.action):
            raise ValueError("custody approval missing, stale or does not bind proposed content")


class SemanticCustodyEngine:
    def __init__(self, policy=None):
        self.policy = policy or SemanticCustodyPolicy()

    def evaluate(self, candidate, existing, transition, continuity, authority):
        if not isinstance(authority, AuthorityContext):
            raise ValueError("explicit authority context required")
        permitted, decision, reason = True, Decision.APPROVE, "Governed candidate accepted within evidence limits."
        rank = self.policy.rank(candidate.semantic_domain, candidate.authority_level)
        same_identity = (authority.domain == candidate.semantic_domain and authority.holder == candidate.custody_holder
                         and authority.level.value == candidate.authority_level)
        if candidate.semantic_domain == "OPERATOR":
            same_identity = same_identity and authority.holder == candidate.operator_id
        evidence = [e for e in candidate.supporting_evidence if e.validated
                    and e.domain == candidate.semantic_domain
                    and e.source_type in self.policy.qualifying_source_types
                    and e.claim == candidate.normalized_meaning]
        sufficient = bool(evidence) and authority.authenticated and same_identity and rank >= 3
        if (transition.understanding_id != candidate.understanding_id or transition.operator_id != candidate.operator_id
                or transition.proposed_state != candidate.semantic_state
                or transition.proposed_meaning != candidate.canonical_meaning
                or transition.expected_version != (existing.version if existing else 0)
                or (transition.action == "CREATE") != (existing is None)):
            raise ValueError("transition does not describe the evaluated candidate/version/action")
        try:
            transition.validate()
        except ValueError as exc:
            permitted, decision, reason = False, Decision.REJECT, str(exc)
        if not same_identity:
            permitted, decision, reason = False, Decision.REQUIRE_AUTHORITY_CONFIRMATION, "Authority does not own this semantic domain/subject."
        elif existing and existing.authority_level != candidate.authority_level and continuity.meaning_changed is False and rank < self.policy.rank(existing.semantic_domain, existing.authority_level):
            permitted, decision, reason = False, Decision.REJECT, "Evidence updates may not lower semantic custody."
        elif existing and rank < self.policy.rank(existing.semantic_domain, existing.authority_level) and continuity.meaning_changed:
            permitted, decision, reason = False, Decision.REJECT, "Lower-authority input cannot replace existing meaning."
        elif existing and existing.protected_meaning and continuity.meaning_changed and not (
                authority.authenticated and authority.may_replace_protected and authority.confirmation_reference):
            permitted, decision, reason = False, Decision.REQUIRE_AUTHORITY_CONFIRMATION, "Protected meaning requires explicit authorized confirmation."
        elif continuity.requires_review and transition.action not in {"DISPUTE", "CONTRADICT", "MARK_PROVISIONAL", "ROLLBACK"}:
            permitted, decision, reason = False, Decision.REQUIRE_HUMAN_REVIEW, "Conflict preserved; no silent replacement or merge."
        elif candidate.semantic_state == S.CONFIRMED and not sufficient:
            permitted, decision, reason = False, Decision.REQUIRE_EVIDENCE, "Confirmation requires claim-specific validated evidence and domain authority."
        elif transition.action in {"ROLLBACK", "SUPERSEDE", "ARCHIVE", "CONTRADICT", "DISPUTE", "MARK_PROVISIONAL"} and not (
                authority.authenticated and rank >= 3 and authority.confirmation_reference):
            permitted, decision, reason = False, Decision.REQUIRE_AUTHORITY_CONFIRMATION, "Lifecycle operation requires explicit domain-owner authorization."
        if permitted and transition.action == "NO_CHANGE":
            decision = Decision.NO_CHANGE
        elif permitted and transition.action == "ROLLBACK":
            decision = Decision.ROLLBACK
        elif permitted and not sufficient:
            reason = "Provisional/pending record only; confidence and repetition are not proof."
        result = SemanticCustodyDecision(decision, permitted, candidate.semantic_state,
            candidate.canonical_meaning, candidate.custody_holder, candidate.authority_level,
            sufficient, continuity.continuity_preserved, not permitted or not sufficient,
            decision in {Decision.REQUIRE_AUTHORITY_CONFIRMATION, Decision.REQUIRE_EVIDENCE} or not sufficient, reason,
            ("DOMAIN_CUSTODY", "EVIDENCE_NOT_CONFIDENCE", "CONTINUITY", "PROTECTED_MEANING", "LEGAL_TRANSITION"),
            digest(candidate), digest(transition), transition.expected_version, transition.action, utc_now())
        from dataclasses import replace
        return replace(result, signature=hmac.digest(_DECISION_KEY, digest(result.payload()).encode(), "sha256").hex())
