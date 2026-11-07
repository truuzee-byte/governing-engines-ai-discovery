from understanding.creative_production import CreativePreparation


def test_game_claim_requires_packaged_play_and_audio_does_not_collapse_to_file(tmp_path):
    creative=CreativePreparation(tmp_path/'docs.db')
    value=creative.prepare('op',dict(project_id='p',medium='GAME',capabilities=['VOICE_PERFORMANCE'],
        assets=[],reuse_inventory_references=[],output_requirements=['Playable voiced interaction']))
    required=value['required_observations']
    assert {'ACTUAL_PLAY','PACKAGED_BUILD_OBSERVED','PACKAGED_LAUNCH_OBSERVED','PACKAGED_PLAY_OBSERVED',
            'AUDIO_PLAYBACK_OBSERVED','INTERACTIVE_AUDIO_STATE_OBSERVED'}<=set(required)
    result=creative.locate_observations('op',value,[],observation_store=None)
    assert result['missing']==required and result['completion']=='UNPROVEN'


def test_animation_audio_requires_sync_without_inventing_threshold(tmp_path):
    creative=CreativePreparation(tmp_path/'docs.db')
    value=creative.prepare('op',dict(project_id='p',medium='ANIMATION',capabilities=['ANIMATION','MUSIC_COMPOSITION'],
        assets=[],reuse_inventory_references=[],output_requirements=['Animation with authored music']))
    assert 'AUDIO_SYNCHRONIZATION_OBSERVED' in value['required_observations']
    assert value['validation']=='PENDING_VALIDATION' and value['execution_authority'] is False
