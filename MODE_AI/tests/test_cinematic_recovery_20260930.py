"""Bounded source-grounded perception continuation; synthetic, no providers."""
import json
import pytest

from tests.test_story_interpretation import interpret, runtime_fixture, command
from understanding.story_cinematic_handoff import admit


SCENE = (
    "Scene 1: Room. Iris enters the room. "
    "Then Niko reacts to an unseen sound. Then Iris notices Niko's reaction. "
    "The audience does not know the sound source."
)


def test_explicit_notice_preserves_reaction_order_and_epistemic_boundary():
    result = interpret(SCENE)
    notice = next(c for c in result.claims if c.predicate == 'notices')
    assert notice.category == 'PERCEPTION'
    assert notice.value == "Niko's reaction"
    assert notice.epistemic_state == 'ESTABLISHED'
    assert [e['verb'] for e in result.events] == ['enters', 'reacts', 'notices']
    assert len([r for r in result.relationships if r['type'] == 'AFTER']) == 2
    assert not any(r['type'] == 'CAUSES' for r in result.relationships)
    models, _, _ = admit(result)[0]
    iris = next(e for e in models['entities'] if e.identity['identity'].value == 'Iris')
    knowledge = next(k for k in models['scenes'][0].knowledge_states if k.holder_id == iris.object_id)
    assert "Niko's reaction" in knowledge.perceptual_access
    assert not knowledge.knows
    assert 'the sound source' in models['audiences'][0].does_not_know
    assert not models['audiences'][0].knows
    assert len(models['beats']) == 3


def test_explicit_audience_notice_is_perception_not_knowledge():
    models, _, _ = admit(interpret("Iris enters the room. The audience notices Iris's reaction."))[0]
    audience = models['audiences'][0]
    assert "Iris's reaction" in audience.perceives
    assert not audience.knows


@pytest.mark.parametrize('text', [
    "Perhaps Iris notices Niko's reaction.",
    "If Iris notices Niko's reaction.",
    "Iris might notices Niko's reaction.",
    "Iris notices Niko's reaction unless the door opens.",
])
def test_uncertain_notice_does_not_become_established_perception(text):
    result = interpret(text)
    assert not any(c.predicate == 'notices' and c.epistemic_state == 'ESTABLISHED' for c in result.claims)
    assert result.unresolved


def test_notice_command_preserves_source_lineage_and_unproven_handoff(tmp_path):
    runtime, docs, request, intake = runtime_fixture(tmp_path, SCENE)
    result = command(runtime, 'interpret', request)
    assert result['state'] == 'UNPROVEN'
    assert not result['execution_authority']
    assert [e['verb'] for e in result['interpretation']['events']] == ['enters', 'reacts', 'notices']
    assert docs.retrieve('op', **request['reference'])['content'] == intake['content']
    handoff = command(runtime, 'handoff', dict(
        specification_reference=result['references']['specification'],
        target='BUILDER', supported_obligations=[]))
    assert handoff['state'] == 'UNPROVEN'
    assert not handoff['execution_authority']
    assert handoff['story_lineage']['interpretation'] == result['interpretation']
    assert handoff['specification']['unresolved_questions']
    (tmp_path / 'SCENARIO_RESULT.json').write_text(
        json.dumps({'input': SCENE, 'request': request, 'result': result, 'handoff': handoff,
                    'observations': runtime.events}, indent=2), encoding='utf-8')
