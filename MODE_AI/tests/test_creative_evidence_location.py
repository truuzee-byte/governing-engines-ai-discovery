import pytest
from understanding.creative_production import CreativePreparation
from runtime_observation.observation_store import RuntimeObservationStore
from runtime_observation.observation_record import RuntimeObservationRecord
from system_layer.contracts import digest

def test_rendered_evidence_and_black_frames_are_not_automatic_success(tmp_path):
    service=CreativePreparation(tmp_path/'docs.db');store=RuntimeObservationStore(tmp_path/'observations')
    prep=service.prepare('op',dict(project_id='p',medium='ANIMATION',capabilities=['ANIMATION'],assets=[],
        reuse_inventory_references=[],output_requirements=['Visible character motion']))
    refs=[]
    for index,kind in enumerate(prep['required_observations']+['FILE_EXISTS']):
        record=RuntimeObservationRecord('obs-'+str(index),operator_id='op',thread_id='t',
            metadata={'creative_preparation_hash':prep['preparation_hash'],'project_id':'p','creative_evidence_kind':kind},
            observed_outcome={'black_frame_fraction':1.0,'motion_measurement':0})
        store.save_record(record)
        refs.append(dict(observation_id=record.observation_id,expected_hash=digest(record.to_dict())))
    result=service.locate_observations('op',prep,refs,observation_store=store)
    assert result['missing']==[] and len(result['located'])==3 and len(result['excluded'])==1
    assert result['located'][0]['observation']['observed_outcome']['black_frame_fraction']==1.0
    assert result['validation']=='PENDING_VALIDATION' and result['completion']=='UNPROVEN'
    with pytest.raises(ValueError):service.locate_observations('op',prep,[dict(refs[0],expected_hash='bad')],observation_store=store)
    partial=service.locate_observations('op',prep,refs[:1],observation_store=store)
    assert len(partial['missing'])==2
