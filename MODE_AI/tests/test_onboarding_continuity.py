import pytest
from onboarding.onboarding_engine import OnboardingEngine
from mode_operator.operator_identity import OperatorIdentity
from mode_operator.operator_store import OperatorStore
from memory.thread_store import ThreadStore


def test_missing_explicit_thread_never_becomes_another_conversation(tmp_path):
    operators=OperatorStore(str(tmp_path/'operators'));threads=ThreadStore(str(tmp_path/'threads'))
    identity=OperatorIdentity.create('op');profile=operators.create_profile(identity)
    existing=threads.create_thread('op','Unrelated active conversation')
    profile.active_thread_id='missing-thread';operators.save_profile(identity,profile)
    before=operators._profile_path('op').read_bytes()
    with pytest.raises(FileNotFoundError):OnboardingEngine(operators,threads).initialize_operator('op')
    assert operators._profile_path('op').read_bytes()==before
    assert [t.thread_id for t in threads.list_threads('op')]==[existing.thread_id]


@pytest.mark.parametrize('identity',['../outside','current_operator','other:stream'])
def test_operator_paths_cannot_cross_or_replace_selection(identity,tmp_path):
    with pytest.raises(ValueError):OperatorStore(str(tmp_path)).create_profile(OperatorIdentity.create(identity))
