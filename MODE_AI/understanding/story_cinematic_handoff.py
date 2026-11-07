"""Lossless grounded story adapter to the existing cinematic state contracts.

No derived intent grants implementation freedom. Inferred purpose and missing
perceptual proof remain readiness obligations in the existing derivation path.
"""
from copy import deepcopy
from .cinematic_models import (Fact, WorldModel, WorldState, EntityModel, NarrativeState,
    TruthState, SceneState, BeatState, AudienceState, CharacterState, KnowledgeState,
    BeliefState, RelationshipState, SpatialState, TemporalState, MECHANISMS)
from .cinematic_derivation import parse_story
from .story_contracts import StoryInterpretation
from system_layer.contracts import digest


def cinematic_story(interpretation):
    interpretation = StoryInterpretation.from_dict(interpretation.to_dict())
    claims={c.claim_id:c for c in interpretation.claims}
    source_facts={}; lineage={}
    def fact(c):
        ref='fact:'+c.claim_id
        source_facts[ref]=deepcopy(c.value); lineage[ref]=c.to_dict()
        state=c.epistemic_state
        return Fact(deepcopy(c.value),state,[ref],list(c.source_references),
            {'ESTABLISHED':'SUPPORTED','INFERRED':'REASONABLE_INFERENCE','UNKNOWN':'UNKNOWN','CONFLICTED':'CONFLICTED'}[state])
    facts={k:fact(c) for k,c in claims.items()}
    def derived_fact(value, refs, rule, state='ESTABLISHED'):
        key='fact:derived:'+digest([value,refs,rule,state]);source_facts[key]=deepcopy(value)
        lineage[key]={'value':deepcopy(value),'source_references':list(refs),'rule':rule,'epistemic_state':state}
        return Fact(deepcopy(value),state,[key],list(refs),
                    {'ESTABLISHED':'SUPPORTED','INFERRED':'REASONABLE_INFERENCE','CONFLICTED':'CONFLICTED','UNKNOWN':'UNKNOWN'}[state])
    # Source spans can anchor object identity without asserting their prose as
    # structured world truth. Every reference maps back through this sidecar.
    for ref,span in interpretation.spans.items():
        key='fact:'+ref;source_facts[key]=span['text'];lineage[key]=deepcopy(span)
    def meta(kind, key, refs):
        return dict(object_id=kind+':'+digest([interpretation.interpretation_id,key]),
            scope=interpretation.sources[0].project,authority='SOURCE_GROUNDED_INTERPRETATION',
            source_references=['fact:'+r for r in refs],lineage=[interpretation.interpretation_id],
            unresolved_questions=list(interpretation.unresolved))
    def state_facts(mapping):
        result={}
        for key,claim in mapping.items():
            current=claims[claim['claim_id']]
            result[key]=derived_fact({'predicate':current.predicate,'value':current.value} if current.epistemic_state!='UNKNOWN' else None,
                current.source_references,'event-state',current.epistemic_state)
        return result
    entities={}
    entity_snapshot=next(s['state']['entities'] for s in interpretation.stages if s['stage']=='ENTITY_REFERENCE_RESOLUTION')
    for eid,e in entity_snapshot.items():
        ref='fact:'+e['refs'][0]
        # Label is a quoted source mention. Exact span custody is retained; no
        # role label is promoted to a proper-name identity.
        labelref='fact:label:'+digest([eid,e['label']]);source_facts[labelref]=e['label']
        lineage[labelref]={'source_references':e['refs'],'rule':'subject-mention','state':e['state']}
        label=Fact(e['label'],'ESTABLISHED',[labelref],e['refs'],'SUPPORTED')
        identity=(derived_fact(e['identity'],e['identity_refs'],'explicit-name-alias') if e.get('identity_refs') else
                  label if e['identity'] else Fact())
        entity=EntityModel(**meta('entity',eid,e['refs']),identity={'source_mention':label,'identity':identity})
        entities[eid]=entity
    models={k:[] for k in ('world_models','world_states','entities','narratives','truth_states','scenes','beats','audiences')}
    models['entities']=list(entities.values()); policies={}
    first=list(interpretation.spans)[0]
    world={c.claim_id:facts[c.claim_id] for c in interpretation.claims if c.category not in {'KNOWLEDGE','BELIEF','AUDIENCE','PURPOSE'} and c.epistemic_state!='UNKNOWN'}
    models['world_models']=[WorldModel(**meta('world',0,[first]))]
    models['world_states']=[WorldState(**meta('world-state',0,[first]),dimensions=deepcopy(world))]
    models['truth_states']=[TruthState(**meta('truth',0,[first]),world_truth=deepcopy(world))]
    material={e['event_id']:e for e in interpretation.events if e['material_transition']}
    prior_state={}; character_claims={}; prior_source=None; audience_history={}; environment_history={}
    for scene_index,raw_scene in enumerate(interpretation.scenes):
        if prior_source!=raw_scene['source_id']:
            prior_state={};character_claims={};audience_history={};environment_history={};prior_source=raw_scene['source_id']
        refs=raw_scene['source_references']; scene_claims=[c for c in interpretation.claims if set(c.source_references)&set(refs)]
        events=[material[e] for e in raw_scene['events'] if e in material]
        if not events: continue  # Preserved as an unresolved unit in interpretation.
        purpose=facts.get(raw_scene.get('purpose_claim'),Fact())
        scene=SceneState(**meta('scene',raw_scene['scene_id'],refs),scene_objective=deepcopy(purpose))
        if raw_scene['boundary_state']!='ESTABLISHED':scene.unresolved_questions.append('SCENE_BOUNDARY_INFERRED')
        selected_subjects={c.subject for c in scene_claims if c.subject in entities}
        scene.participants=[entities[e].object_id for e in sorted(selected_subjects)]
        environment_history.update({c.predicate:deepcopy(facts[c.claim_id]) for c in scene_claims if c.category=='ENVIRONMENT'})
        scene.environment=deepcopy(environment_history)
        scene.entry_state=state_facts(events[0]['pre_state_map'])
        audience=AudienceState(**meta('audience',scene.object_id,refs))
        for field,value in audience_history.items():setattr(audience,field,deepcopy(value))
        for c in scene_claims:
            if c.category!='AUDIENCE':continue
            value=deepcopy(facts[c.claim_id]); key=str(c.value)
            if c.predicate in {'knows','learns','discovers'}:
                prior=audience.knows.get(key)
                if prior and prior.state=='CONFLICTED':
                    value.state='CONFLICTED';value.grounding='CONFLICTED'
                    value.source_references=list(dict.fromkeys(prior.source_references+value.source_references))
                    value.evidence=list(dict.fromkeys(prior.evidence+value.evidence))
                    scene.unresolved_questions.append('AUDIENCE_KNOWLEDGE_CONFLICT:'+key)
                audience.knows[key]=value
            elif c.predicate in {'sees','observes','hears','notices'}: audience.perceives[key]=value
            elif c.predicate=='does not know': audience.does_not_know.append(key)
            elif c.predicate in {'believes','thinks'}:audience.believes[key]=value
            elif c.predicate=='may infer':
                audience.may_infer[key]=derived_fact(c.value,c.source_references,'explicit-audience-inference','INFERRED')
            elif c.predicate=='must understand':
                audience.must_understand.append(key);audience.expected_transition[key]=value
            elif c.predicate=='must not yet understand':audience.must_not_yet_understand.append(key)
        # Current prose representation and required downstream presentation are
        # separate: visible-event obligations are not observations of a render.
        for event in events:
            if event['presentation']=='ON-SCREEN':
                key=event['event_id'];audience.must_understand.append(key)
                audience.expected_transition[key]=deepcopy(facts[event['claim_id']])
                audience.required_evidence[key]=['EVENT_PRESENTATION:'+key]
            # Off-screen alone does not authorize concealment: narration or
            # sound might still inform the audience. Access remains unknown.
        spatial={c.claim_id:deepcopy(facts[c.claim_id]) for c in scene_claims if c.category=='SPATIAL'}
        if spatial:scene.spatial_states=[SpatialState(**meta('spatial',scene.object_id,refs),topology=spatial)]
        scene.temporal_states=[TemporalState(**meta('temporal',scene.object_id,refs),
            time_of_day=deepcopy(scene.environment.get('time of day',Fact())))]
        for relation in interpretation.relationships:
            if relation['target'] not in raw_scene['events'] and not set(relation['source_references'])&set(refs):continue
            rfact=derived_fact(relation if relation['epistemic_state']!='UNKNOWN' else None,relation['source_references'],'explicit-relationship',relation['epistemic_state'])
            if relation['domain']=='CAUSAL':scene.causal_requirements[digest(relation)]=rfact
            elif relation['domain']=='TEMPORAL':scene.temporal_states[0].temporal_relationships[digest(relation)]=rfact
            elif relation['domain']=='SPATIAL' and scene.spatial_states:
                scene.spatial_states[0].topology['relationship:'+digest(relation)]=rfact
        for c in scene_claims:
            if c.subject not in entities:continue
            key=(c.subject,c.category,str(c.value) if c.category in {'KNOWLEDGE','POSSESSION','RELATIONSHIP'} else c.predicate)
            character_claims[key]=c
        for subject in sorted(selected_subjects):
            eid=entities[subject].object_id
            character=CharacterState(**meta('character',[scene.object_id,eid],refs),entity_id=eid)
            knowledge=KnowledgeState(**meta('knowledge',[scene.object_id,eid],refs),holder_id=eid)
            belief=BeliefState(**meta('belief',[scene.object_id,eid],refs),holder_id=eid)
            for c in character_claims.values():
                if c.subject!=subject:continue
                value=deepcopy(facts[c.claim_id]);key=str(c.value)
                if c.category=='KNOWLEDGE':
                    if c.predicate=='does not know':knowledge.does_not_know.append(key)
                    else: knowledge.knows[key]=value
                elif c.category=='BELIEF':belief.believes[key]=value
                elif c.category=='PERCEPTION':knowledge.perceptual_access[key]=value
                elif c.category=='EMOTION':character.emotional[c.predicate]=value
                elif c.category=='OBJECTIVE':character.goals[c.predicate]=value
                elif c.category=='POSSESSION':character.physical['possession:'+key]=derived_fact({'action':c.predicate,'prop':c.value},c.source_references,'possession-event',c.epistemic_state)
                elif c.category in {'PHYSICAL','SPATIAL'}:character.physical[c.category.lower()+':'+c.predicate+':'+key]=value
                elif c.predicate in {'enters','exits','leaves','approaches'}:
                    character.physical['location_or_movement']=derived_fact({'relation':c.predicate,'place':c.value},c.source_references,'explicit-location-event',c.epistemic_state)
                elif c.category=='RELATIONSHIP':
                    scene.relationship_states.append(RelationshipState(**meta('relationship',[scene.object_id,c.claim_id],c.source_references),participants=[eid],dimensions={c.predicate:value}))
                else:character.behavior[c.category.lower()+':'+c.predicate]=value
            # Contradictory epistemic reports are not erased to satisfy a schema.
            for key in set(knowledge.knows)&set(knowledge.does_not_know):
                knowledge.knows[key].state='CONFLICTED';knowledge.knows[key].grounding='CONFLICTED'
                knowledge.does_not_know.remove(key);scene.unresolved_questions.append('CHARACTER_KNOWLEDGE_CONFLICT:'+key)
            scene.character_states.append(character);scene.knowledge_states.append(knowledge);scene.belief_states.append(belief)
        for key in set(audience.knows)&set(audience.does_not_know):
            audience.knows[key].state='CONFLICTED';audience.knows[key].grounding='CONFLICTED'
            audience.does_not_know.remove(key);scene.unresolved_questions.append('AUDIENCE_KNOWLEDGE_CONFLICT:'+key)
        audience_history={field:deepcopy(getattr(audience,field)) for field in ('knows','believes','does_not_know')}
        previous_beat=None
        for event in events:
            c=claims[event['claim_id']]
            value=derived_fact({'predicate':c.predicate,'value':c.value},c.source_references,'event-state',c.epistemic_state);key=event['state_key']
            before=state_facts(event['pre_state_map'])
            if key in before and before[key].value==value.value:
                scene.unresolved_questions.append('REPEATED_EVENT_NO_PROVEN_CHANGE:'+event['event_id']);continue
            prior_state=state_facts(event['post_state_map'])
            beat=BeatState(**meta('beat',event['event_id'],[event['source_reference']]),scene_id=scene.object_id,
                purpose=deepcopy(purpose),participants=[entities[event['subject']].object_id],
                preconditions=before,action=deepcopy(value),state_change={key:deepcopy(value)},
                order=len(models['beats']),continuity_inputs=before,continuity_outputs=deepcopy(prior_state),
                authorized_continuity_changes={key:deepcopy(value)})
            # Narrative serialization order is bookkeeping, not temporal proof.
            temporal=next((r for r in interpretation.relationships if r['domain']=='TEMPORAL' and r['target']==event['event_id']),None)
            if temporal and temporal['type']=='UNKNOWN_ORDER':beat.unresolved_questions.append('TEMPORAL_ORDER_UNKNOWN')
            if previous_beat and temporal and temporal['type']=='AFTER':beat.dependencies=[previous_beat.object_id]
            causal=next((r for r in interpretation.relationships if r['domain']=='CAUSAL' and r['target']==event['event_id'] and r['type']!='UNKNOWN_CAUSE'),None)
            if causal:beat.causal_link=derived_fact(causal,causal['source_references'],'causal-link')
            if c.category=='REACTION':beat.reaction=deepcopy(facts[c.claim_id])
            if causal and causal['type'] in {'CAUSES','TRIGGERS'}:
                cause_event=next((e for e in interpretation.events if e['event_id']==causal['source']),None)
                if cause_event:beat.trigger=deepcopy(facts[cause_event['claim_id']])
            scene.required_beats.append(beat.object_id);scene.required_transitions.append(key)
            scene.temporal_states[0].order.append(beat.object_id)
            models['beats'].append(beat);previous_beat=beat
            # Alternatives are proposals only: no authorized implementation freedom.
            policies[beat.object_id]={'audience_id':audience.object_id,'acceptable_classes':sorted(MECHANISMS),
                'implementation_freedom':[],'prohibited_interpretations':list(audience.must_not_yet_understand)}
        scene.exit_state=deepcopy(prior_state);scene.continuity_inputs=deepcopy(scene.entry_state)
        scene.continuity_outputs=deepcopy(scene.exit_state)
        if not scene.required_beats:
            # The selected unit remains in the interpretation; do not invent a
            # transition just to meet the cinematic model's minimum structure.
            continue
        models['scenes'].append(scene);models['audiences'].append(audience)
        models['narratives'].append(NarrativeState(**meta('narrative',scene.object_id,refs),objective=deepcopy(purpose)))
    value={'schema_version':'CinematicStory/1','source_facts':source_facts,'policies':policies,
           **{k:[v.to_dict() for v in values] for k,values in models.items()}}
    # Original claims, exact spans, and all intermediate state travel as a
    # custody sidecar; no unsupported dimension is reconstructed downstream.
    return value, {'interpretation':interpretation.to_dict(),
                   'canonical_interpretation':interpretation.canonical_view(),'fact_lineage':lineage}


def admit(interpretation):
    from .story_interpretation import StoryInterpreter
    if StoryInterpreter(interpretation.sources).run().to_dict()!=interpretation.to_dict():
        raise ValueError('Story admission requires reproducible source grounding')
    value,lineage=cinematic_story(interpretation)
    if not value['beats'] or any(b['purpose']['state'] not in {'ESTABLISHED','INFERRED'} for b in value['beats']): return None, lineage
    return parse_story(value,interpretation.sources[0].project),lineage
