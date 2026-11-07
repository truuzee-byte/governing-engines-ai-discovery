import pytest
from specs.document_service import DocumentService
from system_layer.contracts import digest


def approval(action,value):return dict(operator_id='op',action=action,decision='APPROVE',hash=digest(value))


def test_derivation_keeps_pinned_sources_without_promoting_candidate(tmp_path):
    docs=DocumentService(tmp_path/'docs.db')
    original=dict(object_id='source',content='Original exact source.',kind='SPECIFICATION',visual_authority='NOT_APPLICABLE',
        source_reference='operator:1',authority='operator',project_id='p',thread_id='t',expected_previous=None,
        validation_references=[],knowledge_class='EXTERNAL')
    source=docs.intake('op',original,approval('DOCUMENT_INTAKE',original))
    candidate=dict(original,object_id='candidate',kind='GENERATED_CANDIDATE',content='Proposed interpretation.',knowledge_class='INTERNAL')
    request=dict(document=candidate,sources=[dict(object_id='source',version=1,expected_hash=source['record_hash'])],
        derivation='GENERATED_CANDIDATE',mechanism_reference='operator-authored-proposal:1')
    with pytest.raises(PermissionError):docs.derive('op',request,{})
    value=docs.derive('op',request,approval('DOCUMENT_DERIVATION',request))
    assert value['metadata']['derivation_sources'][0]['knowledge_class']=='EXTERNAL'
    assert value['metadata']['claims_validated'] is False
    assert docs.retrieve('op','source',1,source['record_hash'])['content']==original['content']
    with pytest.raises(PermissionError):docs.specification_source('op','candidate',1,value['record_hash'])
    request['document']['kind']='CANON'
    with pytest.raises(PermissionError):docs.derive('op',request,approval('DOCUMENT_DERIVATION',request))
