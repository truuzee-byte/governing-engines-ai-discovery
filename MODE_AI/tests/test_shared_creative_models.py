import json
import pytest
from understanding.creative_models import SharedCreativeModels,FIELDS
from understanding.creative_production import CreativePreparation
from specs.document_service import DocumentService
from system_layer.contracts import digest


def put(docs,identity,content,kind='CANON'):
    req=dict(object_id=identity,content=content,kind=kind,visual_authority='NOT_APPLICABLE',knowledge_class='INTERNAL',
        source_reference='operator:authored',authority='operator',project_id='p',thread_id='t',expected_previous=None,validation_references=[])
    record=docs.intake('op',req,dict(operator_id='op',action='DOCUMENT_INTAKE',decision='APPROVE',hash=digest(req)))
    return dict(object_id=identity,version=1,expected_hash=record['record_hash'])


@pytest.mark.parametrize('kind',list(FIELDS))
@pytest.mark.parametrize('binary',[False,True])
def test_shared_identity_survives_both_media_and_unknowns_do_not_become_readiness(tmp_path,kind,binary):
    docs=DocumentService(tmp_path/'docs.db');canon=put(docs,'world','Authored world identity')
    definition={field:None for field in FIELDS[kind]}
    model=dict(schema_version='SharedCreativeDefinition/1',identity='shared',kind=kind,definition=definition,
        representations={},use_requirements={'GAME':['Runtime responsiveness'],'ANIMATION':['Authored timing']},source_references=[canon])
    content=json.dumps(model)
    if binary:
        import base64,hashlib
        raw=content.encode()
        content=json.dumps(dict(schema_version='DocumentBinary/1',format='UTF8_TEXT',encoding='BASE64',
            data=base64.b64encode(raw).decode(),sha256=hashlib.sha256(raw).hexdigest()))
    ref=put(docs,'shared',content);resolver=SharedCreativeModels(tmp_path/'docs.db')
    a=resolver.resolve('op',ref,'p','GAME');b=resolver.resolve('op',ref,'p','ANIMATION')
    assert a['definition_hash']==b['definition_hash'] and a['identity']==b['identity']
    assert a['definition_hash']==digest(model) and bool(a['source_extraction'])==binary
    assert a['use_requirements']!=b['use_requirements'] and a['state']=='REVIEW_REQUIRED'
    assert a['readiness']=='UNPROVEN' and a['execution_authority'] is False
    if kind=='MUSIC':assert len(a['music_capabilities'])==8
    request=dict(project_id='p',medium='GAME',capabilities=['CREATIVE_INTENT'],assets=[],reuse_inventory_references=[],
        output_requirements=['Observable experience'],model_references=[ref])
    prepared=CreativePreparation(tmp_path/'docs.db').prepare('op',request)
    assert prepared['shared_models'][0]['definition_hash']==a['definition_hash']
    assert 'SHARED_MODEL_REVIEW:shared' in prepared['missing']
