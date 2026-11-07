import json
import pytest
from specs.document_service import DocumentService
from specs.spec_engine import require_builder_specification
from system_layer.contracts import digest


def approved(action,request):
    return dict(operator_id='op',action=action,decision='APPROVE',hash=digest(request))


def source(docs,payload):
    req=dict(object_id='spec-source',content=json.dumps(payload),kind='SPECIFICATION',
        visual_authority='NOT_APPLICABLE',source_reference='operator:source',authority='operator',
        project_id='project',thread_id='thread',expected_previous=None,validation_references=[],knowledge_class='INTERNAL')
    doc=docs.intake('op',req,approved('DOCUMENT_INTAKE',req))
    selection=dict(scope_id='project-specification',state='CURRENT_AUTHORITY',
        references=[dict(object_id='spec-source',version=1,expected_hash=doc['record_hash'])],
        rationale='Explicit structured source selection',expected_previous=None)
    decision=docs.reconcile_authority('op',selection,approved('DOCUMENT_AUTHORITY',selection))
    return doc,decision,selection


def payload():
    return dict(request_id='r',system_name='Example',system_purpose='Prepare an example',tool_type='python',
        construction_scope=['main.py'],approved_components=['main'],governance_constraints=['Do not execute'],
        execution_authority='authority_granted',receipt_requirements=['record'],runtime_target='local',
        source_trace_reference='trace:original',artifact_structure={'directories':[],'files':['main.py']},
        validation={'commands':['python -m pytest']},evidence={'required':['artifact_hash']},
        authority_state='authority_granted',validation_state='valid',readiness_state='ready_for_build',
        save_ready_state=True,clarification_required=False)


def test_canonical_draft_keeps_source_lineage_without_inheriting_approval(tmp_path):
    docs=DocumentService(tmp_path/'docs.db');original=payload();doc,decision,selection=source(docs,original)
    args=('op','project-specification',1,decision['record_hash'],'project')
    prepared=docs.prepare_specification(*args);spec=prepared['specification']
    assert spec['validation']==original['validation'] and spec['evidence']==original['evidence']
    assert spec['lineage']['document_source']['expected_hash']==doc['record_hash']
    assert spec['lineage']['source_refs']==['trace:original']
    assert spec['authority_state']=='draft_only' and spec['clarification_required'] is True
    assert len(prepared['transformations'])==6
    with pytest.raises(ValueError):require_builder_specification(spec)
    with pytest.raises(PermissionError):docs.prepare_specification(*args[:-1],'other-project')
    selection.update(state='NOT_SPECIFIED',references=[],expected_previous=decision['record_hash'])
    docs.reconcile_authority('op',selection,approved('DOCUMENT_AUTHORITY',selection))
    with pytest.raises(PermissionError,match='SUPERSEDED'):docs.prepare_specification(*args)


def test_unrepresentable_source_is_not_silently_dropped(tmp_path):
    docs=DocumentService(tmp_path/'docs.db');value=payload();value['unmapped_requirement']='Must survive'
    _,decision,_=source(docs,value)
    with pytest.raises(ValueError,match='field loss'):
        docs.prepare_specification('op','project-specification',1,decision['record_hash'],'project')


def test_draft_factory_cannot_admit_ready_or_authorized_states():
    from specs.spec_engine import create_specification_object
    value=payload();value['execution_authority']='draft_only'
    with pytest.raises(ValueError,match='Draft preparation'):
        create_specification_object(value,draft_only=True)
    with pytest.raises(ValueError,match='execution_authority'):
        create_specification_object(value)


def test_lossless_preserved_binary_enters_canonical_draft_without_copying(tmp_path):
    import base64,hashlib
    docs=DocumentService(tmp_path/'docs.db');original=payload();raw=json.dumps(original,ensure_ascii=False).encode('utf-8')
    wrapped=dict(schema_version='DocumentBinary/1',format='UTF8_TEXT',encoding='BASE64',data=base64.b64encode(raw).decode(),sha256=hashlib.sha256(raw).hexdigest())
    source_record,decision,_=source(docs,wrapped)
    result=docs.prepare_specification('op','project-specification',1,decision['record_hash'],'project')
    spec=result['specification']
    assert spec['artifact_structure']==original['artifact_structure'] and spec['validation']==original['validation']
    assert spec['evidence']==original['evidence']
    assert spec['lineage']['document_extraction']['binary_sha256']==wrapped['sha256']
    assert spec['lineage']['document_source']['expected_hash']==source_record['record_hash']
    assert result['extraction']['transformation']=='LOSSLESS_UTF8_DECODE'
    with pytest.raises(ValueError):require_builder_specification(spec)
