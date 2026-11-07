"""Normal runtime with deterministic provider output; explicitly not live-model proof."""
import json
from pathlib import Path
from interactive_mode_ai import ModeRuntime
from mode_operator.operator_identity import OperatorIdentity
from mode_operator.operator_store import OperatorStore
from memory.thread_store import ThreadStore
from agents.reasoning_agent import ReasoningResult


def test_conversation_and_presentation_through_normal_boot(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr('runtime_logging.trace_logger.TRACE_OUTPUT_PATH',tmp_path/'traces.jsonl')
    monkeypatch.setattr('runtime_logging.response_logger.RESPONSE_OUTPUT_PATH',tmp_path/'responses.jsonl')
    monkeypatch.setattr('context.context_resolver.RUNTIME_STATE_ROOT',tmp_path/'session_context')
    for name in ('MODE_RP_CONFIG','MODE_CAPABILITY_RP_CONFIG','MODE_SUPERVISOR_DB'):
        monkeypatch.delenv(name,raising=False)
    operators=OperatorStore(str(tmp_path/'operators'));identity=OperatorIdentity.create('operator')
    profile=operators.create_profile(identity)
    profile.update_operator_managed_info(preferred_name='Operator',timezone='UTC',language='English')
    thread=ThreadStore(str(tmp_path/'threads')).create_thread('operator')
    profile.active_thread_id=thread.thread_id;operators.save_profile(identity,profile)
    runtime=ModeRuntime('operator',str(tmp_path/'operators'),str(tmp_path/'threads'))
    def response(*args,**kwargs):
        return ReasoningResult('offline-fixture','fixture','deterministic','','','Hello! How can I help?',0)
    monkeypatch.setattr('core.mode_controller._generate_reasoning_result',response)
    inputs=iter(['Hello.','/view export','exit'])
    monkeypatch.setattr('builtins.input',lambda _:next(inputs))
    try:
        runtime.boot();runtime.run()
        assert runtime.context.response_governance['allowed']
        assert runtime.context.response_governance['materiality']['state']=='NON_MATERIAL'
        saved=json.loads(runtime.understanding_engine.store.path.with_name('presentation.json').read_text())
        assert any(m['content']=='Hello! How can I help?' for m in saved['messages'])
        assert saved['source']=='ACTIVE_RUNTIME_SNAPSHOT'
    finally:runtime.shutdown()
