import json
from types import SimpleNamespace as NS
import pytest
from understanding import UnderstandingEngine,UnderstandingStore
from understanding.creative_models import FIELDS
from understanding.creative_understanding import understand
from specs.document_service import DocumentService
from system_layer.contracts import digest


def test_character_intent_uses_existing_semantic_custody_and_preserves_conflict(tmp_path):
    runtime=NS(context=NS(identity=NS(operator_id='op'),active_thread=NS(thread_id='t')),
        understanding_engine=UnderstandingEngine(UnderstandingStore(tmp_path/'meaning.db')))
    docs=DocumentService(tmp_path/'content_custody.sqlite3')
    def save(value,previous=None):
        req=dict(object_id='character',content=json.dumps(value),kind='GENERATED_CANDIDATE',visual_authority='GENERATED_CANDIDATE',
            knowledge_class='INTERNAL',source_reference='operator:definition',authority='operator',project_id='p',thread_id='t',expected_previous=previous,validation_references=[])
        return docs.intake('op',req,dict(operator_id='op',action='DOCUMENT_INTAKE',decision='APPROVE',hash=digest(req)))
    model=dict(schema_version='SharedCreativeDefinition/1',identity='character',kind='CHARACTER',
        definition={key:'Authored character detail' for key in FIELDS['CHARACTER']},representations={},
        use_requirements={'GAME':['Respect authored identity'],'ANIMATION':['Respect authored identity']},source_references=[])
    source=save(model)
    def selected(record):return dict(reference=dict(object_id='character',version=record['version'],expected_hash=record['record_hash']),project_id='p',medium='GAME')
    def approval(request):return dict(operator_id='op',action='CREATIVE_UNDERSTANDING',decision='APPROVE',hash=digest(request))
    request=selected(source)
    with pytest.raises(PermissionError):understand(runtime,request,{})
    result=understand(runtime,request,approval(request))
    assert not result['errors'] and result['understanding']['final_understanding']['semantic_domain']=='OPERATOR'
    assert not result['asset_validated'] and not result['capability_proven'] and not result['canon_document_updated']
    original=result['understanding']['final_understanding']['canonical_meaning']
    model['definition']['identity']='A changed identity'
    changed=save(model,source['record_hash']);request=selected(changed)
    reviewed=understand(runtime,request,approval(request))
    assert reviewed['understanding']['review_required']
    assert reviewed['understanding']['final_understanding']['canonical_meaning']==original
    with pytest.raises(PermissionError):understand(runtime,request,{})
    assert runtime.context.understanding_result is None
