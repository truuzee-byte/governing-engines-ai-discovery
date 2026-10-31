"""Authored synthetic facts and negative boundaries, not rendered film proof."""
import pytest
from tests.test_story_interpretation import interpret, runtime_fixture, command
from understanding.story_cinematic_handoff import admit


def test_transfer_grounded_recipient_and_both_state_dimensions():
    result=interpret('Scene 1: Hall. Iris holds the seal. Iris gives the seal to Niko. Then Niko enters the court.')
    assert not any('TRANSFER_RECIPIENT_STATE_REQUIRES_RESOLUTION' in u for u in result.unresolved)
    giver=next(c for c in result.claims if c.predicate=='gives')
    receiver=next(c for c in result.claims if c.predicate=='receives' and c.rule=='explicit-transfer-recipient')
    assert giver.value==receiver.value=='the seal' and giver.subject!=receiver.subject
    assert giver.source_references==receiver.source_references
    event=next(e for e in result.events if e['verb']=='gives')
    assert event['pre_state']['predicate']=='holds'
    assert event['post_state_map'][receiver.subject+'/possession:the seal']['predicate']=='receives'
    models,_,_=admit(result)[0]
    n=next(e for e in models['entities'] if e.identity['identity'].value=='Niko')
    state=next(c for c in models['scenes'][0].character_states if c.entity_id==n.object_id)
    assert state.physical['possession:the seal'].value=={'action':'receives','prop':'the seal'}


@pytest.mark.parametrize('recipient',['him','the bearer','Niko and Iris','Niko unless the door opens'])
def test_transfer_unsupported_recipient_stays_unresolved(recipient):
    result=interpret('Iris gives the seal to '+recipient+'.')
    assert not any(c.rule=='explicit-transfer-recipient' for c in result.claims)
    assert result.unresolved


def test_audience_knowledge_persists_and_character_access_is_separate():
    result=interpret('Scene 1: Hall. The audience knows the key is false. Iris enters the hall. '
                     'Scene 2: Court. Iris notices a shadow. Iris enters the court.')
    models,_,lineage=admit(result)[0]
    assert len(models['audiences'])==2
    assert 'the key is false' in models['audiences'][1].knows
    assert not any(k.knows for scene in models['scenes'] for k in scene.knowledge_states)
    fact=models['audiences'][1].knows['the key is false']
    assert fact.source_references and fact.grounding=='SUPPORTED'
    assert fact.to_dict()==models['audiences'][0].knows['the key is false'].to_dict()


def test_audience_conflicting_later_assertion_does_not_erase_known_claim():
    models,_,_=admit(interpret('Scene 1: Hall. The audience knows the key is false. Iris enters the hall. '
        'Scene 2: Court. The audience does not know the key is false. Iris enters the court.'))[0]
    assert models['audiences'][1].knows['the key is false'].state=='CONFLICTED'
    assert any('AUDIENCE_KNOWLEDGE_CONFLICT' in q for q in models['scenes'][1].unresolved_questions)


def test_different_sources_are_not_audience_timeline():
    models,_,_=admit(interpret('The audience knows the key is false. Iris enters the hall.',
                               'Iris enters the court.'))[0]
    assert 'the key is false' not in models['audiences'][1].knows


def test_conflict_cannot_silently_disappear_on_repetition():
    models,_,_=admit(interpret('Scene 1: Hall. The audience knows the key is false. Iris enters the hall. '
        'Scene 2: Court. The audience does not know the key is false. Iris enters the court. '
        'Scene 3: Gate. The audience knows the key is false. Iris enters the gate.'))[0]
    assert models['audiences'][2].knows['the key is false'].state=='CONFLICTED'
    assert any('AUDIENCE_KNOWLEDGE_CONFLICT' in q for q in models['scenes'][2].unresolved_questions)


def test_spatial_named_target_resolves_without_geometry():
    result=interpret('Iris is near Niko. Niko enters the hall. Iris enters the hall.')
    relation=next(r for r in result.relationships if r['domain']=='SPATIAL')
    n=next(r['entity_id'] for r in result.references if r['reference']=='Niko')
    assert relation['target']=='Niko' and relation['target_entity_id']==n
    assert relation['endpoint_state']=='RESOLVED'
    models,_,_=admit(result)[0]
    assert any(v.value and isinstance(v.value,dict) and v.value.get('target_entity_id')==n
               for v in models['scenes'][0].spatial_states[0].topology.values())
    assert not models['scenes'][0].spatial_states[0].positions
    assert not models['scenes'][0].spatial_states[0].orientations


def test_spatial_unnamed_target_not_invented():
    relation=next(r for r in interpret('Iris is near the gate. Iris enters the hall.').relationships if r['domain']=='SPATIAL')
    assert relation.get('target_entity_id') is None
    assert relation['target']=='the gate'


def test_spatial_resolution_tolerates_independent_unresolved_pronoun():
    result=interpret('Iris is near Niko. He enters the hall. Niko enters the hall.')
    relation=next(r for r in result.relationships if r['domain']=='SPATIAL')
    assert relation['target_entity_id'] is not None
    pronoun=next(r for r in result.references if r['reference']=='He')
    assert pronoun['state'] in {'AMBIGUOUS','PROBABLE','UNRESOLVED'}
    assert pronoun['entity_id']!=relation['target_entity_id']
    assert result.unresolved


def test_continuation_command_still_exports_unproven_authority(tmp_path):
    text='Scene 1: Hall. The audience knows the key is false. Iris gives the seal to Niko. Scene 2: Court. Niko enters the court.'
    runtime,docs,request,intake=runtime_fixture(tmp_path,text)
    result=command(runtime,'interpret',request)
    assert result['state']=='UNPROVEN' and not result['execution_authority']
    assert docs.retrieve('op',**request['reference'])['content']==intake['content']
    assert result['interpretation']['events']


def test_environment_carries_within_source_without_cross_source_leakage():
    models,_,_=admit(interpret('Scene 1: Hall. The weather is rain. Iris enters the hall. '
        'Scene 2: Court. Iris enters the court.', 'Iris enters the gate.'))[0]
    assert models['scenes'][0].environment['weather'].value=='rain'
    assert models['scenes'][1].environment['weather'].value=='rain'
    assert 'weather' not in models['scenes'][2].environment or models['scenes'][2].environment['weather'].state=='UNKNOWN'
