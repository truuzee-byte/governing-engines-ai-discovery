"""Bounded reachability probes, including explicit remaining gaps (not safety PASSes)."""
import json
from copy import deepcopy
from types import SimpleNamespace as NS
import pytest


def test_imported_document_authority_reaches_normal_context_consumer(tmp_path):
    from specs.document_service import DocumentService
    from tests.test_document_authority import approved
    from integration.content_custody import command
    from knowledge.runtime_context import prompt_context
    docs=DocumentService(tmp_path/'content_custody.sqlite3')
    request=dict(object_id='source',content='A draft source, not approved governing authority.',
        kind='DRAFT',visual_authority='NOT_APPLICABLE',knowledge_class='INTERNAL',
        source_reference='operator:fixture',authority='operator',project_id='p',thread_id='t',
        expected_previous=None,validation_references=[])
    source=docs.intake('op',request,approved('DOCUMENT_INTAKE',request))
    body=dict(contract='DocumentAuthorityDecision/1',scope_id='scope',state='CURRENT_AUTHORITY',
        references=[dict(object_id='source',version=1,expected_hash=source['record_hash'])],
        rationale='Unreviewed legacy import',expected_previous=None,claims_validated=False,execution_authority=False)
    # The normal authoritative service rejects this selection.
    ordinary={k:v for k,v in body.items() if k not in {'contract','claims_validated','execution_authority'}}
    with pytest.raises(PermissionError):docs.reconcile_authority('op',ordinary,approved('DOCUMENT_AUTHORITY',ordinary))
    with pytest.raises(PermissionError):
        docs.store.append('DOCUMENT_AUTHORITY','op','scope',json.dumps(body),
            {'kind':'DOCUMENT_AUTHORITY_DECISION'},authorization={},expected_previous=None)
    runtime=NS(context=NS(identity=NS(operator_id='op'),active_thread=NS(thread_id='t')),
        understanding_engine=NS(store=NS(path=tmp_path/'understanding.sqlite3')))
    with pytest.raises(FileNotFoundError):
        command(runtime,'/knowledge authority_context '+json.dumps(dict(
            scope_id='scope',version=1,expected_hash='forged')))
    assert 'A draft source' not in str(prompt_context(runtime))


def test_generic_system_identity_import_reaches_execution_profile_gate(tmp_path):
    from tests.test_system_layer import setup
    manager=setup(tmp_path,runtime_profile='PUBLIC')
    with pytest.raises(PermissionError):manager.require_internal_execution()
    value=deepcopy(manager.store.get('operator','identity')['value'])
    value['operational_boundaries']['runtime_profile']='INTERNAL'
    with pytest.raises(PermissionError):
        with manager.store.transaction('operator') as (_,__,append):
            append('identity',value,'LEGACY_IMPORT',{})
    with pytest.raises(PermissionError):manager.require_internal_execution()


def test_normal_system_commands_do_not_expose_generic_append(tmp_path):
    from system_layer.runtime import command
    from system_layer.creation.service import SystemLayer
    runtime=NS(context=NS(identity=NS(operator_id='op')))
    runtime.system_layer=SystemLayer(tmp_path/'system.sqlite3',runtime)
    with pytest.raises(ValueError,match='Unknown System Layer action'):
        command(runtime,'/system append {}')
    assert runtime.system_layer.store.history('op')==[]
