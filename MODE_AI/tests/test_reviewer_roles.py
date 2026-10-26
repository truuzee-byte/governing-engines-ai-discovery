from __future__ import annotations

import pytest

from models.runtime_models import ReviewerRole


def test_system_operator_role_validates() -> None:
    reviewer = ReviewerRole(
        reviewer_id="reviewer-system-operator-001",
        reviewer_role="system_operator",
        domain_context_level="high",
        system_involvement_level="high",
        independence_level="low",
        bias_vectors=["operator ownership"],
        scoring_authority="human_review",
        review_scope=["runtime_behavior", "governance_alignment"],
        notes="Primary operator review.",
    )

    assert reviewer.reviewer_role == "system_operator"


def test_domain_embedded_reviewer_role_validates_with_bias_vectors() -> None:
    reviewer = ReviewerRole(
        reviewer_id="reviewer-domain-embedded-001",
        reviewer_role="domain_embedded_reviewer",
        domain_context_level="high",
        system_involvement_level="medium",
        independence_level="medium",
        bias_vectors=["architecture familiarity", "system investment"],
        scoring_authority="human_review",
        review_scope=["intent_drift", "structural_mismatch"],
        notes="Can detect architecture drift but may carry design bias.",
    )

    assert reviewer.reviewer_role == "domain_embedded_reviewer"
    assert reviewer.bias_vectors == [
        "architecture familiarity",
        "system investment",
    ]


def test_independent_reviewer_role_validates() -> None:
    reviewer = ReviewerRole(
        reviewer_id="reviewer-independent-001",
        reviewer_role="independent_reviewer",
        domain_context_level="medium",
        system_involvement_level="none",
        independence_level="high",
        bias_vectors=[],
        scoring_authority="human_review",
        review_scope=["output_behavior", "external_consistency"],
        notes="Independent human reviewer.",
    )

    assert reviewer.reviewer_role == "independent_reviewer"


def test_automated_scorer_role_validates_without_human_authority() -> None:
    reviewer = ReviewerRole(
        reviewer_id="reviewer-automated-001",
        reviewer_role="automated_scorer",
        domain_context_level="bounded",
        system_involvement_level="none",
        independence_level="mechanical",
        bias_vectors=[],
        scoring_authority="automated_score",
        review_scope=["schema_compliance", "telemetry_consistency"],
        notes="Automated scoring only.",
    )

    assert reviewer.reviewer_role == "automated_scorer"
    assert reviewer.scoring_authority == "automated_score"


def test_invalid_reviewer_role_fails() -> None:
    with pytest.raises(ValueError):
        ReviewerRole(
            reviewer_id="reviewer-invalid-001",
            reviewer_role="invalid_role",
            domain_context_level="high",
            system_involvement_level="low",
            independence_level="medium",
            bias_vectors=[],
            scoring_authority="human_review",
            review_scope=["runtime_behavior"],
            notes="Invalid role.",
        )


def test_domain_embedded_reviewer_requires_bias_vectors() -> None:
    with pytest.raises(ValueError):
        ReviewerRole(
            reviewer_id="reviewer-domain-embedded-invalid-001",
            reviewer_role="domain_embedded_reviewer",
            domain_context_level="high",
            system_involvement_level="high",
            independence_level="medium",
            bias_vectors=[],
            scoring_authority="human_review",
            review_scope=["intent_drift"],
            notes="Missing bias vectors.",
        )


@pytest.mark.parametrize(
    "human_authority",
    [
        "human_score",
        "human_review",
        "human_final",
        "human_override",
    ],
)
def test_automated_scorer_cannot_claim_human_authority(
    human_authority: str,
) -> None:
    with pytest.raises(ValueError):
        ReviewerRole(
            reviewer_id=f"reviewer-automated-invalid-{human_authority}",
            reviewer_role="automated_scorer",
            domain_context_level="bounded",
            system_involvement_level="none",
            independence_level="mechanical",
            bias_vectors=[],
            scoring_authority=human_authority,
            review_scope=["schema_compliance"],
            notes="Automated scorer cannot claim human authority.",
        )


def test_reviewer_role_to_dict_preserves_fields() -> None:
    reviewer = ReviewerRole(
        reviewer_id="reviewer-dict-001",
        reviewer_role="domain_embedded_reviewer",
        domain_context_level="high",
        system_involvement_level="medium",
        independence_level="medium",
        bias_vectors=["system familiarity"],
        scoring_authority="human_review",
        review_scope=["intent_drift"],
        notes="Dictionary serialization test.",
    )

    payload = reviewer.to_dict()

    assert payload["reviewer_id"] == "reviewer-dict-001"
    assert payload["reviewer_role"] == "domain_embedded_reviewer"
    assert payload["domain_context_level"] == "high"
    assert payload["system_involvement_level"] == "medium"
    assert payload["independence_level"] == "medium"
    assert payload["bias_vectors"] == ["system familiarity"]
    assert payload["scoring_authority"] == "human_review"
    assert payload["review_scope"] == ["intent_drift"]
    assert payload["notes"] == "Dictionary serialization test."