import base64
import hashlib
import io
import json
import wave
import pytest
from runtime_observation.audio_inspection import inspect_pcm
from runtime_observation.observation_collector import RuntimeObservationCollector
from runtime_observation.observation_store import RuntimeObservationStore
from understanding.creative_production import CreativePreparation
from system_layer.contracts import digest


def wav(samples):
    stream=io.BytesIO()
    with wave.open(stream,'wb') as writer:
        writer.setnchannels(1);writer.setsampwidth(2);writer.setframerate(8000)
        writer.writeframes(b''.join(sample.to_bytes(2,'little',signed=True) for sample in samples))
    return stream.getvalue()


def test_measured_silence_is_distinct_from_missing_or_truncated_audio():
    content=wav([0]*8);value=inspect_pcm(content,hashlib.sha256(content).hexdigest())
    assert value['state']=='MEASURED' and value['metrics']['nonzero_fraction']==[0]
    assert value['playback_observed'] is False and value['quality_validated'] is False
    truncated=content[:-2];partial=inspect_pcm(truncated,hashlib.sha256(truncated).hexdigest())
    assert partial['state']=='PARTIAL' and partial['metrics']['sample_frames']==7
    assert partial['metrics']['declared_sample_frames']==8 and partial['metrics']['missing_sample_frames']==1
    assert partial['metrics']['nonzero_fraction']==[0] and partial['metrics']['measurement_scope']=='OBSERVED_COMPLETE_PCM_FRAMES'
    empty=wav([]);assert inspect_pcm(empty,hashlib.sha256(empty).hexdigest())['metrics']['nonzero_fraction']==[None]
    with pytest.raises(ValueError):inspect_pcm(content,'changed')


def test_partial_audio_keeps_readable_measurements_without_inventing_missing_samples():
    content=wav([100,-200,300])[:-3]
    result=inspect_pcm(content,hashlib.sha256(content).hexdigest())
    assert result['state']=='PARTIAL' and result['metrics']['sample_frames']==1
    assert result['metrics']['peak_absolute_integer']==[100]
    assert result['metrics']['uninterpreted_partial_frame_bytes']==1
    assert result['metrics']['missing_sample_frames']==2
    empty=wav([])
    assert inspect_pcm(empty,hashlib.sha256(empty).hexdigest())['metrics']['peak_absolute_integer']==[None]


def test_source_audio_inspection_records_observation_not_playback(tmp_path):
    service=CreativePreparation(tmp_path/'docs.db');content=wav([-100,0,100])
    payload=dict(schema_version='AudioSource/1',encoding='BASE64_WAV',data=base64.b64encode(content).decode(),sha256=hashlib.sha256(content).hexdigest())
    req=dict(object_id='audio',content=json.dumps(payload),kind='PRODUCTION_ASSET',visual_authority='NOT_APPLICABLE',
        knowledge_class='INTERNAL',source_reference='operator:audio',authority='operator',project_id='p',thread_id='t',expected_previous=None,validation_references=[])
    record=service.documents.intake('op',req,dict(operator_id='op',action='DOCUMENT_INTAKE',decision='APPROVE',hash=digest(req)))
    collector=RuntimeObservationCollector(store=RuntimeObservationStore(tmp_path/'observations'))
    result=service.inspect_audio('op',dict(object_id='audio',version=1,expected_hash=record['record_hash']),'p',collector=collector,thread_id='t')
    observed=collector.store.load_record('op',result['observation_id'])
    assert observed.metadata['creative_evidence_kind']=='AUDIO_STRUCTURE_INSPECTED'
    assert observed.observed_outcome['metrics']['peak_absolute_integer']==[100]
    assert result['completion']=='UNPROVEN' and not observed.observed_outcome['playback_observed']
    reference=dict(object_id='audio',version=1,expected_hash=record['record_hash'])
    preparation=service.prepare('op',dict(project_id='p',medium='ANIMATION',capabilities=['MUSIC_COMPOSITION'],
        assets=[reference],reuse_inventory_references=[],output_requirements=['Music synchronized to picture']))
    bound=service.inspect_audio('op',reference,'p',collector=collector,thread_id='t',preparation=preparation)
    evidence=service.locate_observations('op',preparation,[dict(observation_id=bound['observation_id'],expected_hash=bound['observation_hash'])],observation_store=collector.store)
    assert len(evidence['supplemental'])==1 and not evidence['located']
    assert 'AUDIO_PLAYBACK_OBSERVED' in evidence['missing'] and 'AUDIO_SYNCHRONIZATION_OBSERVED' in evidence['missing']
    assert evidence['supplemental'][0]['observation']['metadata']['source_reference']==reference
    with pytest.raises(PermissionError,match='not selected'):
        other=service.prepare('op',dict(project_id='p',medium='ANIMATION',capabilities=['MUSIC_COMPOSITION'],
            assets=[],reuse_inventory_references=[],output_requirements=['Different source']))
        service.inspect_audio('op',reference,'p',collector=collector,thread_id='t',preparation=other)
