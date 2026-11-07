from mode_operator.operator_profile import OperatorProfile
from temporal.temporal_context import TemporalContext, build_temporal_context


class TemporalEngine:
    """
    Temporal Awareness module.

    Anchors Mode Bot to the operator's current temporal reality.
    """

    def build_for_operator(self, profile: OperatorProfile) -> TemporalContext:
        timezone_name = profile.operator_managed.timezone or "UTC"
        return build_temporal_context(timezone_name)