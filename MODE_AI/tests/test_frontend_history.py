from types import SimpleNamespace as NS
from frontend.runtime_view import history, snapshot
from memory.thread_store import ThreadStore
from onboarding.onboarding_state import OnboardingState
from runtime_observation.observation_collector import RuntimeObservationCollector
from runtime_observation.observation_store import RuntimeObservationStore

def test_history_preserves_historical_status_and_missingness(tmp_path):
    store=ThreadStore(str(tmp_path/'threads'));thread=store.create_thread('op','A project')
    collector=RuntimeObservationCollector(store=RuntimeObservationStore(tmp_path/'observations'))
    record=collector.collect(operator_id='op',thread_id=thread.thread_id,
        metadata={'runtime_component':'integration.build_runtime','observed_outcome':{'request_id':'build','state':'BUILD_PASS_RP_CONFIRMED'},'produced_receipts':['receipt']})
    runtime=NS(context=NS(identity=NS(operator_id='op'),active_thread=thread,runtime_state='IDLE',
        onboarding_state=OnboardingState('op',False,True)),thread_store=store,
        runtime_observation_collector=collector)
    value=history(runtime,expected_owner='op')
    assert value['threads']['items'][0]['title']=='A project'
    assert value['past_builds']['items'][0]['current_validity']=='NOT_REVALIDATED'
    assert snapshot(runtime)['onboarding']['state']=='COMPLETE'
    def fail(owner):raise ValueError('Unreadable record')
    runtime.runtime_observation_collector.store.load_records_for_operator=fail
    assert history(runtime,expected_owner='op')['past_builds']['state']=='UNAVAILABLE'


def test_attempts_are_distinct_and_every_stage_reference_is_retained(tmp_path):
    store=ThreadStore(str(tmp_path/'threads'));thread=store.create_thread('op')
    collector=RuntimeObservationCollector(store=RuntimeObservationStore(tmp_path/'observations'))
    for attempt,state in [('one','BUILD_FAIL'),('two','BUILD_PASS_RP_PENDING'),('two','BUILD_PASS_RP_CONFIRMED')]:
        collector.collect(operator_id='op',thread_id=thread.thread_id,metadata={
            'runtime_component':'integration.build_runtime','observed_outcome':{'request_id':'same-request','attempt_id':attempt,'state':state}})
    runtime=NS(context=NS(identity=NS(operator_id='op'),active_thread=thread),thread_store=store,runtime_observation_collector=collector)
    builds=history(runtime,expected_owner='op')['past_builds']['items']
    assert len(builds)==2
    second=next(b for b in builds if b['attempt_id']=='two')
    assert second['observed_state']=='BUILD_PASS_RP_CONFIRMED' and second['current_validity']=='NOT_REVALIDATED'
    assert len(second['observations'])==2
