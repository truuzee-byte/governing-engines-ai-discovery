import json
import pytest
from specs.document_service import DocumentService
from knowledge.retrieval import KnowledgeRetrieval
from system_layer.contracts import digest
from understanding.creative_production import CreativePreparation
from runtime_observation.observation_store import RuntimeObservationStore
from runtime_observation import RuntimeObservationCollector


def approval(action, request):
    return dict(operator_id='op',action=action,decision='APPROVE',hash=digest(request))


def document(docs, category='SYSTEM', previous=None, content='Exact source.'):
    req=dict(object_id='source',content=content,kind='SPECIFICATION',visual_authority='NOT_APPLICABLE',
        knowledge_class=category,source_reference='operator:source',authority='operator',project_id='p',thread_id='t',
        expected_previous=previous,validation_references=[])
    return docs.intake('op',req,approval('DOCUMENT_INTAKE',req))


def test_document_model_preserves_source_and_unknown_structure(tmp_path):
    docs=DocumentService(tmp_path/'store.db');r=document(docs)
    model=docs.document_model('op','source',1,r['record_hash'])
    assert model['structure']['segments'][0]['text']=='Exact source.'
    assert model['structure']['tables'] is None
    assert model['authority_state']=='NOT_RECONCILED'
    assert model['validation']['state']=='UNPROVEN'
    assert model['version_id']==r['record_hash']
    assert model['model_hash']==digest({k:v for k,v in model.items() if k!='model_hash'})
    exported=docs.export('op','source',1,r['record_hash'],'MODEL_JSON')
    assert json.loads(exported['content'])==model
    segment=model['structure']['segments'][0]
    assert docs.passage('op','source',1,r['record_hash'],segment['segment_id'])['segment']==segment
    assert not exported['rendered_output_observed']
    document(docs,previous=r['record_hash'],content='New exact source.')
    assert not docs.document_model('op','source',1,r['record_hash'])['is_latest_version']
    assert docs.passage('op','source',1,r['record_hash'],segment['segment_id'])['segment']==segment
    with pytest.raises(FileNotFoundError):docs.passage('op','source',2,docs.store.history('DOCUMENT','op','source')[-1]['record_hash'],segment['segment_id'])
    with pytest.raises(ValueError):docs.document_model('op','source',1,'wrong')
    with pytest.raises(FileNotFoundError):docs.document_model('other','source',1,r['record_hash'])


def test_knowledge_authority_preserves_class_and_old_version(tmp_path):
    docs=DocumentService(tmp_path/'store.db');r=document(docs,'EXTERNAL')
    ref=dict(object_id='source',version=1,expected_hash=r['record_hash'])
    req=dict(scope_id='scope',state='CURRENT_AUTHORITY',references=[ref],rationale='Explicit selection',expected_previous=None)
    decision=docs.reconcile_authority('op',req,approval('DOCUMENT_AUTHORITY',req))
    k=KnowledgeRetrieval(tmp_path/'store.db')
    resolved=k.resolve_authority('op','scope',1,decision['record_hash'])
    assert resolved['knowledge_sources'][0]['knowledge_class']=='EXTERNAL'
    assert resolved['knowledge_sources'][0]['claims_validated'] is False
    document(docs,'EXTERNAL',previous=r['record_hash'],content='New candidate text')
    old=k.retrieve('op',[dict(ref,knowledge_class='EXTERNAL')])['entries'][0]
    assert not old['is_latest_version'] and old['state']=='UNPROVEN'
    assert old['provenance']['source_reference']=='operator:source'
    # A new source version is not an implicit authority decision.
    assert k.resolve_authority('op','scope',1,decision['record_hash'])['state']=='CURRENT_AUTHORITY'
    with pytest.raises(PermissionError):k.retrieve('op',[dict(ref,knowledge_class='SYSTEM')])


def test_document_restoration_appends_without_rewriting_history_or_authority(tmp_path):
    docs=DocumentService(tmp_path/'store.db');first=document(docs)
    second=document(docs,previous=first['record_hash'],content='Second version.')
    source=dict(object_id='source',version=1,expected_hash=first['record_hash'])
    req=dict(source=source,expected_previous=second['record_hash'],reason='Restore exact authored source')
    with pytest.raises(PermissionError):docs.restore('op',req,{})
    restored=docs.restore('op',req,approval('DOCUMENT_RESTORE',req))
    assert restored['version']==3 and restored['previous_hash']==second['record_hash']
    assert restored['content']==first['content']
    assert docs.retrieve('op','source',1,first['record_hash'])==first
    assert docs.retrieve('op','source',2,second['record_hash'])==second
    model=docs.document_model('op','source',3,restored['record_hash'])
    assert model['recovery_history'][0]['source']==source
    assert model['authority_state']=='NOT_RECONCILED' and model['validation']['state']=='UNPROVEN'
    with pytest.raises(ValueError,match='STALE'):docs.restore('op',req,approval('DOCUMENT_RESTORE',req))


def test_creative_missing_and_partial_evidence_never_becomes_validated(tmp_path):
    service=CreativePreparation(tmp_path/'store.db')
    prep=service.prepare('op',dict(project_id='p',medium='ANIMATION',capabilities=['ANIMATION'],
        assets=[],reuse_inventory_references=[],output_requirements=['two shots']))
    store=RuntimeObservationStore(tmp_path/'observations')
    result=service.locate_observations('op',prep,[dict(observation_id='missing',expected_hash='h')],observation_store=store)
    assert result['unavailable'] and not result['located']
    record=RuntimeObservationCollector(store=store).collect(operator_id='op',thread_id='t',
        metadata={'creative_preparation_hash':prep['preparation_hash'],'project_id':'p',
            'creative_evidence_kind':'MOTION_OBSERVED'})
    record.evidence_completeness='PARTIAL';store.save_record(record)
    result=service.locate_observations('op',prep,[dict(observation_id=record.observation_id,expected_hash=digest(record.to_dict()))],observation_store=store)
    assert result['located'][0]['completeness']=='PARTIAL'
    assert result['located'][0]['sufficiency']=='NOT_EVALUATED'
    assert result['completion']=='UNPROVEN'


def test_creative_frame_inspection_cannot_issue_unstored_reference(tmp_path,monkeypatch):
    from test_frame_inspection import image
    service=CreativePreparation(tmp_path/'store.db')
    source=document(service.documents,'INTERNAL',content=image('black'))
    collector=RuntimeObservationCollector(store=RuntimeObservationStore(tmp_path/'observations'))
    monkeypatch.setattr(collector.store,'save_record',lambda *a:None)
    with pytest.raises(OSError,match='custody failed'):
        service.inspect_frames('op',[dict(object_id='source',version=1,expected_hash=source['record_hash'])],
            collector=collector,thread_id='t',project_id='p')
