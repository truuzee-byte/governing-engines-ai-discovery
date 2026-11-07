import base64
import hashlib
import io
import json
import pytest
from PIL import Image
from runtime_observation.frame_inspection import inspect_frames
from runtime_observation.observation_collector import RuntimeObservationCollector
from runtime_observation.observation_store import RuntimeObservationStore
from understanding.creative_production import CreativePreparation
from system_layer.contracts import digest


def image(color,size=(3,3)):
    stream=io.BytesIO()
    with Image.new('RGB',size,color) as value:value.save(stream,format='PNG')
    raw=stream.getvalue()
    return json.dumps(dict(schema_version='ImageSource/1',encoding='BASE64',data=base64.b64encode(raw).decode(),sha256=hashlib.sha256(raw).hexdigest()))


def test_pixel_evidence_preserves_zero_change_and_missing_comparison():
    black=image('black');red=image('red')
    result=inspect_frames([black,black,red,image('red',(2,2))])
    assert result['frames'][0]['rgb_mean']==[0,0,0]
    assert result['differences'][0]['rgb_mean_absolute_difference']==[0,0,0]
    assert result['differences'][1]['rgb_mean_absolute_difference']==[255,0,0]
    assert result['differences'][2]['rgb_mean_absolute_difference'] is None
    assert result['state']=='PARTIAL'
    assert result['unavailable_measurements']==[{'from_index':2,'to_index':3,'reason':'UNAVAILABLE_DIMENSION_MISMATCH'}]
    assert not result['motion_validated'] and not result['render_execution_observed']
    assert result['frames'][0]['alpha_extrema']==[255,255]


def test_unreadable_frame_does_not_erase_adjacent_measurements_or_create_zero_motion():
    result=inspect_frames([image('black'),'not a frame source',image('red')])
    assert result['state']=='PARTIAL'
    assert result['frames'][0]['rgb_mean']==[0,0,0]
    assert result['frames'][1]['state']=='UNINSPECTABLE' and result['frames'][1]['rgb_mean'] is None
    assert result['frames'][2]['rgb_mean']==[255,0,0]
    assert all(d['state']=='UNAVAILABLE_FRAME' and d['rgb_mean_absolute_difference'] is None for d in result['differences'])
    assert not result['motion_validated']


def test_verified_bytes_remain_identified_when_pixel_decoding_fails():
    raw=b'Not an image';checksum=hashlib.sha256(raw).hexdigest()
    content=json.dumps(dict(schema_version='ImageSource/1',encoding='BASE64',data=base64.b64encode(raw).decode(),sha256=checksum))
    result=inspect_frames([content])
    frame=result['frames'][0]
    assert result['state']=='PARTIAL' and frame['state']=='UNINSPECTABLE'
    assert frame['sha256']==checksum and frame['source_hash_state']=='VERIFIED'
    assert frame['rgb_mean'] is None and frame['width'] is None


@pytest.mark.parametrize('mismatch',[False,True])
def test_frame_observation_is_source_bound_and_cannot_prove_rendering(tmp_path,mismatch):
    creative=CreativePreparation(tmp_path/'docs.db');refs=[]
    for index,color in enumerate(('black','red')):
        req=dict(object_id=f'frame{index}',content=image(color,(2,2) if mismatch and index else (3,3)),kind='RENDERED_EVIDENCE',visual_authority='RENDERED_EVIDENCE',
            knowledge_class='INTERNAL',source_reference='operator:frame',authority='operator',project_id='p',thread_id='t',
            expected_previous=None,validation_references=[])
        record=creative.documents.intake('op',req,dict(operator_id='op',action='DOCUMENT_INTAKE',decision='APPROVE',hash=digest(req)))
        refs.append(dict(object_id=req['object_id'],version=1,expected_hash=record['record_hash']))
    prep=creative.prepare('op',dict(project_id='p',medium='ANIMATION',capabilities=['ANIMATION'],assets=refs,
        reuse_inventory_references=[],output_requirements=['Visible authored action']))
    collector=RuntimeObservationCollector(store=RuntimeObservationStore(tmp_path/'observations'))
    result=creative.inspect_frames('op',refs,prep,collector=collector,thread_id='t')
    assert result['inspection']['state']==('PARTIAL' if mismatch else 'MEASURED')
    observed=collector.store.load_record('op',result['observation_id'])
    if mismatch:assert 'NORMAL_EXECUTION' not in [kind.value for kind in observed.observation_types]
    located=creative.locate_observations('op',prep,[dict(observation_id=result['observation_id'],expected_hash=result['observation_hash'])],observation_store=collector.store)
    assert not located['located'] and len(located['supplemental'])==1
    assert 'RENDERED_OUTPUT_OBSERVED' in located['missing'] and 'MOTION_OBSERVED' in located['missing']
    with pytest.raises(PermissionError):creative.inspect_frames('op',[dict(refs[0],expected_hash='changed')],prep,collector=collector,thread_id='t')
