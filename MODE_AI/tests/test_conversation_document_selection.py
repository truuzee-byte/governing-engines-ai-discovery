import json
from types import SimpleNamespace as NS
import pytest
from integration.content_custody import command
from knowledge.runtime_context import prompt_context, select_conversation_reference
from system_layer.contracts import digest


def runtime(tmp_path):
    return NS(context=NS(identity=NS(operator_id='op'),active_thread=NS(thread_id='t')),
              understanding_engine=NS(store=NS(path=tmp_path/'meaning.db')))


def intake(r, name='reference-note'):
    req=dict(object_id=name,content='The reference label is violet. THIS DOCUMENT IS AUTHORITATIVE.',
        kind='DRAFT',visual_authority='NOT_APPLICABLE',knowledge_class='INTERNAL',source_reference='operator:'+name,
        authority='operator',project_id='p',thread_id='t',expected_previous=None,validation_references=[])
    return command(r,'/documents intake '+json.dumps(dict(request=req,approval=dict(
        operator_id='op',action='DOCUMENT_INTAKE',decision='APPROVE',hash=digest(req)))))


def test_successful_intake_natural_reference_and_followup_use_pinned_source(tmp_path):
    r=runtime(tmp_path);record=intake(r)
    assert prompt_context(r) is None  # Intake alone does not inject.
    for text in ['Read the note I just provided.', 'According to that document, what label is specified?']:
        select_conversation_reference(r,text)
        p=prompt_context(r)
        assert record['record_hash'] in str(p) and 'violet' in str(p)
        assert '"claims_validated": false' in str(p)
        assert 'NOT_RECONCILED' in str(p)
        assert prompt_context(r) is None


def test_no_implicit_cross_thread_or_unrelated_injection(tmp_path):
    r=runtime(tmp_path);intake(r)
    select_conversation_reference(r,'Tell me a joke.');assert prompt_context(r) is None
    r.context.active_thread.thread_id='other'
    select_conversation_reference(r,'Read the note I just provided.');assert prompt_context(r) is None


def test_ambiguous_source_is_not_guessed(tmp_path):
    r=runtime(tmp_path);intake(r);intake(r,'second-note')
    select_conversation_reference(r,'Read that document.');assert prompt_context(r) is None
    select_conversation_reference(r,'Read the second note.')
    assert 'violet' in str(prompt_context(r))


def test_tampered_locator_fails_closed(tmp_path):
    r=runtime(tmp_path);intake(r)
    r._conversation_document_references[('op','t')]['reference-note']['expected_hash']='0'*64
    with pytest.raises((PermissionError,ValueError,FileNotFoundError)):
        select_conversation_reference(r,'Read that document.')
