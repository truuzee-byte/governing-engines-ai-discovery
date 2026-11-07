import json
from types import SimpleNamespace as NS
import pytest
from integration.content_custody import command
from knowledge.runtime_context import prompt_context
from specs.document_service import DocumentService
from system_layer.contracts import digest


def test_authority_selection_is_rechecked_at_prompt_assembly(tmp_path):
    runtime=NS(context=NS(identity=NS(operator_id='op'),active_thread=NS(thread_id='t')),
               understanding_engine=NS(store=NS(path=tmp_path/'meaning.db')))
    docs=DocumentService(tmp_path/'content_custody.sqlite3')
    def approval(action,req):return dict(operator_id='op',action=action,decision='APPROVE',hash=digest(req))
    req=dict(object_id='spec',content='Exact governing definition',kind='SPECIFICATION',visual_authority='NOT_APPLICABLE',
        knowledge_class='SYSTEM',source_reference='operator:spec',authority='operator',project_id='p',thread_id='t',
        expected_previous=None,validation_references=[])
    record=docs.intake('op',req,approval('DOCUMENT_INTAKE',req))
    decision=dict(scope_id='definition',state='CURRENT_AUTHORITY',references=[dict(object_id='spec',version=1,expected_hash=record['record_hash'])],
        rationale='Operator selection',expected_previous=None)
    selected=docs.reconcile_authority('op',decision,approval('DOCUMENT_AUTHORITY',decision))
    text='/knowledge authority_context '+json.dumps(dict(scope_id='definition',version=1,expected_hash=selected['record_hash']))
    command(runtime,text)
    prompt=prompt_context(runtime)
    assert req['content'] in str(prompt) and 'CURRENT_AUTHORITY' in str(prompt)
    assert '"claims_validated": false' in str(prompt)
    command(runtime,text)
    decision.update(state='MISSING_AUTHORITY',references=[],rationale='Withdraw selection',expected_previous=selected['record_hash'])
    docs.reconcile_authority('op',decision,approval('DOCUMENT_AUTHORITY',decision))
    with pytest.raises(PermissionError,match='SUPERSEDED_AUTHORITY'):prompt_context(runtime)
    assert prompt_context(runtime) is None
    with pytest.raises(PermissionError,match='SUPERSEDED_AUTHORITY'):command(runtime,text)


def test_selected_sources_reach_admitted_context_once_without_claim_promotion(tmp_path):
    runtime=NS(context=NS(identity=NS(operator_id='op'),active_thread=NS(thread_id='t')),
               understanding_engine=NS(store=NS(path=tmp_path/'meaning.db')))
    docs=DocumentService(tmp_path/'content_custody.sqlite3');refs=[]
    for category in ('SYSTEM','INTERNAL','EXTERNAL'):
        req=dict(object_id=category,content='Exact '+category+' source.',kind='DRAFT',visual_authority='NOT_APPLICABLE',
            knowledge_class=category,source_reference='source:'+category,authority='operator',project_id='p',thread_id='t',
            expected_previous=None,validation_references=[])
        record=docs.intake('op',req,dict(operator_id='op',action='DOCUMENT_INTAKE',decision='APPROVE',hash=digest(req)))
        refs.append(dict(object_id=category,version=1,expected_hash=record['record_hash'],knowledge_class=category))
    command(runtime,'/knowledge context '+json.dumps(refs+refs[:1]))
    prompt=prompt_context(runtime)
    for category in ('SYSTEM','INTERNAL','EXTERNAL'):assert str(prompt).count('Exact '+category+' source.')==1
    assert '"claims_validated": false' in str(prompt)
    assert len(prompt.decisions)==3 and all(d['decision']=='ADMITTED' for d in prompt.decisions)
    assert prompt_context(runtime) is None
    command(runtime,'/knowledge context '+json.dumps(refs))
    with pytest.raises(FileNotFoundError):command(runtime,'/knowledge context '+json.dumps([dict(refs[0],object_id='missing')]))
    assert prompt_context(runtime) is None
    command(runtime,'/knowledge context '+json.dumps(refs))
    runtime.context.active_thread.thread_id='other'
    with pytest.raises(PermissionError):prompt_context(runtime)
    assert prompt_context(runtime) is None


def test_selected_source_enters_normal_runtime_prompt(tmp_path,monkeypatch):
    from interactive_mode_ai import ModeRuntime
    from mode_operator.operator_identity import OperatorIdentity
    from mode_operator.operator_store import OperatorStore
    from memory.thread_store import ThreadStore
    monkeypatch.chdir(tmp_path)
    operators=OperatorStore(str(tmp_path/'operators'));identity=OperatorIdentity.create('op')
    profile=operators.create_profile(identity)
    profile.update_operator_managed_info(preferred_name='Operator',timezone='UTC',language='English')
    thread=ThreadStore(str(tmp_path/'threads')).create_thread('op');profile.active_thread_id=thread.thread_id
    operators.save_profile(identity,profile)
    runtime=ModeRuntime('op',str(tmp_path/'operators'),str(tmp_path/'threads'))
    try:
        runtime.boot()
        docs=DocumentService(runtime.understanding_engine.store.path.with_name('content_custody.sqlite3'))
        req=dict(object_id='specific',content='Pinned selected source survives runtime assembly.',kind='DRAFT',
            visual_authority='NOT_APPLICABLE',knowledge_class='INTERNAL',source_reference='operator:source',authority='operator',
            project_id='p',thread_id=thread.thread_id,expected_previous=None,validation_references=[])
        record=docs.intake('op',req,dict(operator_id='op',action='DOCUMENT_INTAKE',decision='APPROVE',hash=digest(req)))
        refs=[dict(object_id='specific',version=1,expected_hash=record['record_hash'],knowledge_class='INTERNAL')]
        command(runtime,'/knowledge context '+json.dumps(refs))
        prompt=runtime._build_engine_input('Explain the selected source.')
        assert req['content'] in str(prompt)
        assert record['record_hash'] in runtime.context.context_admission['injected_ids']
        assert req['content'] not in str(runtime._build_engine_input('Explain again.'))
    finally:runtime.shutdown()
