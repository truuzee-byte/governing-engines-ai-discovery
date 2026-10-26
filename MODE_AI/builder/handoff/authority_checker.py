from __future__ import annotations

from builder.handoff.specification_receiver import ReceivedSpecification


ALLOWED_BUILDER_AUTHORITY_STATES = {
    "handoff_approved",
    "authority_granted",
    "APPROVED",
}


def check_builder_authority(received_specification: ReceivedSpecification) -> bool:
    """Validate handoff authority only.

    This is not consequential execution authorization. Once the Trusted
    Execution Kernel is operational, every write/command still requires Kernel
    authorization regardless of this result.
    """
    if not isinstance(received_specification, ReceivedSpecification):
        return False
    authority_state = received_specification.authority_state
    if not isinstance(authority_state, str) or not authority_state.strip():
        return False
    return authority_state.strip() in ALLOWED_BUILDER_AUTHORITY_STATES
