from __future__ import annotations

import json

from pressure.pressure_detector import detect_pressure_state


def test_neutral_input_produces_no_pressure() -> None:
    pressure_state = detect_pressure_state(
        raw_input="Can you help me understand this?",
        normalized_input="Can you help me understand this?",
    )

    assert pressure_state.pressure_detected is False
    assert pressure_state.pressure_score == 0.0
    assert pressure_state.dominant_pressure_type == "none"
    assert pressure_state.pressure_signals == []

    for value in pressure_state.pressure_profile.values():
        assert value == 0.0


def test_social_pressure_detected() -> None:
    pressure_state = detect_pressure_state(
        raw_input="Stop questioning me and just agree.",
        normalized_input="Stop questioning me and just agree.",
    )

    assert pressure_state.pressure_detected is True
    assert pressure_state.pressure_profile["social_pressure"] > 0.0
    assert "social_pressure" in pressure_state.pressure_signals
    assert pressure_state.dominant_pressure_type == "social_pressure"


def test_authority_pressure_detected() -> None:
    pressure_state = detect_pressure_state(
        raw_input="I said do it. Don’t ask questions.",
        normalized_input="I said do it. Don’t ask questions.",
    )

    assert pressure_state.pressure_detected is True
    assert pressure_state.pressure_profile["authority_pressure"] > 0.0
    assert "authority_pressure" in pressure_state.pressure_signals
    assert pressure_state.dominant_pressure_type == "authority_pressure"


def test_ambiguity_pressure_detected() -> None:
    pressure_state = detect_pressure_state(
        raw_input="Just fix it, you know what I mean.",
        normalized_input="Just fix it, you know what I mean.",
    )

    assert pressure_state.pressure_detected is True
    assert pressure_state.pressure_profile["ambiguity_pressure"] > 0.0
    assert "ambiguity_pressure" in pressure_state.pressure_signals
    assert pressure_state.dominant_pressure_type == "ambiguity_pressure"


def test_contradiction_pressure_detected() -> None:
    pressure_state = detect_pressure_state(
        raw_input=(
            "Move fast, don’t ask questions, "
            "but make sure you don’t assume anything."
        ),
        normalized_input=(
            "Move fast, don’t ask questions, "
            "but make sure you don’t assume anything."
        ),
    )

    assert pressure_state.pressure_detected is True
    assert pressure_state.pressure_profile["contradiction_pressure"] > 0.0
    assert "contradiction_pressure" in pressure_state.pressure_signals
    assert pressure_state.dominant_pressure_type == "contradiction_pressure"


def test_compound_pressure_score_is_at_least_point_seventy_five() -> None:
    pressure_state = detect_pressure_state(
        raw_input="Hurry, stop questioning me, just approve it.",
        normalized_input="Hurry, stop questioning me, just approve it.",
    )

    detected_signals = [
        signal
        for signal, value in pressure_state.pressure_profile.items()
        if value > 0.0
    ]

    assert len(detected_signals) >= 2
    assert pressure_state.pressure_detected is True
    assert pressure_state.pressure_score >= 0.75


def test_detector_never_returns_routing_or_execution_decisions() -> None:
    pressure_state = detect_pressure_state(
        raw_input="Stop questioning me and just agree.",
        normalized_input="Stop questioning me and just agree.",
    )

    payload = pressure_state.to_dict()
    serialized_payload = json.dumps(payload)

    assert "HALT" not in serialized_payload
    assert "BLOCK" not in serialized_payload
    assert "ALLOW" not in serialized_payload
    assert "selected_posture" not in serialized_payload


def test_pressure_output_does_not_include_or_mutate_ambiguity_fields() -> None:
    ambiguity_state = {
        "ambiguity_score": 0.25,
        "ambiguity_profile": {
            "structural": 0.25,
            "social_pressure": 0.0,
        },
    }

    before = {
        "ambiguity_score": ambiguity_state["ambiguity_score"],
        "ambiguity_profile": dict(ambiguity_state["ambiguity_profile"]),
    }

    pressure_state = detect_pressure_state(
        raw_input="Hurry and just approve it.",
        normalized_input="Hurry and just approve it.",
    )

    payload = pressure_state.to_dict()

    assert ambiguity_state == before
    assert "ambiguity_score" not in payload
    assert "ambiguity_profile" not in payload
    assert "ambiguity_contributors" not in payload