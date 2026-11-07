"""Provider isolation for deterministic controller-property unit tests only.

This response double never selects a learning path or supplies behavioral proof.
Manifest/scoring/trace production mechanisms and all original assertions run.
"""
import pytest
from agents.reasoning_agent import ReasoningResult


@pytest.fixture(autouse=True)
def local_controller(monkeypatch,tmp_path):
    class LocalResponseAgent:
        def generate(self,active_pack_name,active_mode_name,mode_definition,user_input,
                     recent_context='',input_kind='statement',response_posture='analytical',interaction_id='UNAVAILABLE'):
            from data_governance.context_admission import AdmittedPrompt,verify
            if isinstance(user_input,AdmittedPrompt):verify(user_input)
            return ReasoningResult('local-unit:'+interaction_id,'LOCAL_TEST_FIXTURE','NO_MODEL','','',
                                   'Synthetic local response for controller property tests.',0.0)
    monkeypatch.setattr('core.mode_controller.ReasoningAgent',LocalResponseAgent)
    monkeypatch.setattr('runtime_logging.trace_logger.TRACE_OUTPUT_PATH',tmp_path/'traces.jsonl')
    monkeypatch.setattr('runtime_logging.response_logger.RESPONSE_OUTPUT_PATH',tmp_path/'responses.jsonl')
    monkeypatch.setattr('context.context_resolver.RUNTIME_STATE_ROOT',tmp_path/'sessions')
