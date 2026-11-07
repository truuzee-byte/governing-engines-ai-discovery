from mode_operator.operator_identity import OperatorIdentity
from mode_operator.operator_profile import OperatorProfile
from mode_operator.operator_store import OperatorStore

from onboarding.onboarding_state import OnboardingState
from memory.thread_store import ThreadStore


class OnboardingEngine:
    """
    Operator Onboarding orchestrator.

    Owns onboarding flow only.
    Does not own identity, profile persistence, thread memory internals, or temporal logic.
    """

    def __init__(
        self,
        operator_store: OperatorStore,
        thread_store: ThreadStore,
    ) -> None:
        self.operator_store = operator_store
        self.thread_store = thread_store

    def initialize_operator(
        self,
        operator_id: str | None = None,
    ) -> tuple[OperatorIdentity, OperatorProfile, OnboardingState]:
        identity = OperatorIdentity.create(operator_id=operator_id)

        profile_exists = self.operator_store.profile_exists(identity.operator_id)

        if profile_exists:
            profile = self.operator_store.load_profile(identity)
        else:
            profile = self.operator_store.create_profile(identity)

        active_thread = self._get_or_create_active_thread(profile)

        profile.set_active_thread(active_thread.thread_id)
        profile.upsert_thread_reference(
            thread_id=active_thread.thread_id,
            title=active_thread.title,
        )

        onboarding_complete = profile.is_onboarding_complete()
        onboarding_required = not onboarding_complete

        state = OnboardingState(
            operator_id=identity.operator_id,
            onboarding_required=onboarding_required,
            onboarding_complete=onboarding_complete,
            initial_thread_id=active_thread.thread_id,
            temporal_initialized=False,
        )

        self.operator_store.save_profile(identity, profile)

        return identity, profile, state

    def apply_onboarding_answers(
        self,
        identity: OperatorIdentity,
        profile: OperatorProfile,
        preferred_name: str,
        timezone: str,
        language: str,
        name: str | None = None,
        expected_profile_hash: str | None = None,
    ) -> tuple[OperatorProfile, OnboardingState]:
        identity.require_profile_match(profile.operator_id)

        profile.update_operator_managed_info(
            name=name,
            preferred_name=preferred_name,
            timezone=timezone,
            language=language,
        )

        active_thread = self._get_or_create_active_thread(profile)

        profile.set_active_thread(active_thread.thread_id)
        profile.upsert_thread_reference(
            thread_id=active_thread.thread_id,
            title=active_thread.title,
        )

        if expected_profile_hash is None:
            self.operator_store.save_profile(identity, profile)
        else:
            self.operator_store.save_profile_if_current(identity,profile,expected_profile_hash)

        state = OnboardingState(
            operator_id=identity.operator_id,
            onboarding_required=not profile.is_onboarding_complete(),
            onboarding_complete=profile.is_onboarding_complete(),
            initial_thread_id=active_thread.thread_id,
            temporal_initialized=False,
        )

        return profile, state

    def _get_or_create_active_thread(self, profile: OperatorProfile):
        if profile.active_thread_id:
            # An explicit continuity reference is not permission to substitute
            # another thread or silently create an empty replacement.
            return self.thread_store.load_thread(
                operator_id=profile.operator_id,
                thread_id=profile.active_thread_id,
            )

        return self.thread_store.get_or_create_active_thread(
            operator_id=profile.operator_id,
        )
