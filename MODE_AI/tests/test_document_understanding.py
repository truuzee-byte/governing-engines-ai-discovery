import json
from types import SimpleNamespace as NS
import pytest
from specs.document_service import DocumentService
from understanding import UnderstandingEngine
from understanding.understanding_store import UnderstandingStore
from integration.content_custody import command
from system_layer.contracts import digest


@pytest.mark.parametrize('binary',[False,True])
def test_document_flows_into_existing_understanding_without_truth_promotion(tmp_path,binary):
    runtime=NS(context=NS(identity=NS(operator_id='op'),active_thread=NS(thread_id='t')),
        understanding_engine=UnderstandingEngine(UnderstandingStore(tmp_path/'meaning.db')))
    docs=DocumentService(tmp_path/'content_custody.sqlite3')
    approve=lambda action,value:dict(operator_id='op',action=action,decision='APPROVE',hash=digest(value))
    req=dict(object_id='authority',content='The proposed tool shall preserve all authored requirements.',kind='SPECIFICATION',
        visual_authority='NOT_APPLICABLE',knowledge_class='SYSTEM',source_reference='operator:spec',authority='operator',
        project_id='p',thread_id='t',expected_previous=None,validation_references=[])
    original=req['content']
    if binary:
        import base64,hashlib
        req['content']=json.dumps(dict(schema_version='DocumentBinary/1',format='UTF8_TEXT',encoding='BASE64',
            data=base64.b64encode(original.encode()).decode(),sha256=hashlib.sha256(original.encode()).hexdigest()))
    process=runtime.understanding_engine.process;seen=[]
    def capture(value):
        seen.append(value.current_input)
        return process(value)
    runtime.understanding_engine.process=capture
    source=docs.intake('op',req,approve('DOCUMENT_INTAKE',req))
    decision=dict(scope_id='project',state='CURRENT_AUTHORITY',references=[dict(object_id='authority',version=1,expected_hash=source['record_hash'])],rationale='Selected specification',expected_previous=None)
    accepted=docs.reconcile_authority('op',decision,approve('DOCUMENT_AUTHORITY',decision))
    request=dict(authority_reference=dict(scope_id='project',version=1,expected_hash=accepted['record_hash']),project_id='p',
        interpretation=dict(subject_id='tool.requirements',semantic_domain='SYSTEM',meaning=original,source_references=[source['record_hash']],requirements=['Preserve all authored requirements']))
    def send(value):return command(runtime,'/documents understand '+json.dumps(dict(request=value,approval=approve('DOCUMENT_UNDERSTANDING',value))))
    result=send(request)
    assert not result['errors'] and 'DOCUMENT' in result['understanding']['modes']
    assert result['understanding']['candidate_understanding']['canonical_meaning']==original
    assert seen==[original]
    assert bool(result['extraction'])==binary
    assert result['understanding']['candidate_understanding']['semantic_state']!='CONFIRMED'
    assert result['understanding']['candidate_understanding']['supporting_evidence'][0]['reference']==source['record_hash']
    with pytest.raises(PermissionError):runtime.context.understanding_result.specification_handoff()
    with pytest.raises(ValueError,match='exact selected'):send(dict(request,interpretation=dict(request['interpretation'],source_references=['invented'])))
    assert runtime.context.understanding_result is None
    decision.update(state='NOT_SPECIFIED',references=[],expected_previous=accepted['record_hash'])
    docs.reconcile_authority('op',decision,approve('DOCUMENT_AUTHORITY',decision))
    with pytest.raises(PermissionError,match='SUPERSEDED'):send(request)
