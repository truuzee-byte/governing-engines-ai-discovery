"""Semantic vocabulary. Transition permission belongs to semantic_transition."""
from enum import Enum


class SemanticState(str, Enum):
    UNOBSERVED = "UNOBSERVED"
    OBSERVED = "OBSERVED"
    INTERPRETED = "INTERPRETED"
    PENDING_VALIDATION = "PENDING_VALIDATION"
    PROVISIONAL = "PROVISIONAL"
    CONFIRMED = "CONFIRMED"
    DISPUTED = "DISPUTED"
    CONTRADICTED = "CONTRADICTED"
    SUPERSEDED = "SUPERSEDED"
    REJECTED = "REJECTED"
    ARCHIVED = "ARCHIVED"
    ROLLBACK_REQUIRED = "ROLLBACK_REQUIRED"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    AUTHORITY_CONFIRMATION_REQUIRED = "AUTHORITY_CONFIRMATION_REQUIRED"


def is_active_state(state):
    return SemanticState(state) in {SemanticState.PROVISIONAL, SemanticState.CONFIRMED,
                                  SemanticState.DISPUTED, SemanticState.PENDING_VALIDATION}


def is_validated_state(state):
    return SemanticState(state) == SemanticState.CONFIRMED


def is_terminal_state(state):
    return SemanticState(state) in {SemanticState.REJECTED, SemanticState.ARCHIVED, SemanticState.SUPERSEDED}


def requires_review(state):
    return SemanticState(state) in {SemanticState.HUMAN_REVIEW_REQUIRED,
        SemanticState.AUTHORITY_CONFIRMATION_REQUIRED, SemanticState.DISPUTED,
        SemanticState.ROLLBACK_REQUIRED}
