"""Shared identity/requirements from exact document custody (Creative v1.2 §§3–24).

These are authored definitions, not creative execution or reality decisions.
Game and animation use the same definition identity with separate use requirements.
"""
import json
from specs.document_service import DocumentService
from system_layer.contracts import digest

FIELDS={
 # Shared authored dimensions from Creative Production v1.2 §§11–12,21–24.
 # They are not tool implementations or proof of production readiness.
 'WORLD_ENVIRONMENT':('canon_authority','geography','architecture','settlements','props','modular_kits',
    'terrain','vegetation','lighting_conditions','weather','environmental_storytelling',
    'traversal_affordances','simulation_hooks','spatial_continuity','asset_placement'),
 'NARRATIVE_STORY':('world','character','story','scene','gameplay_state','creative_intent',
    'authored_intent','candidate_interpretation','production_requirements'),
 'CREATIVE_INTENT':('authored_intent','authority_source','candidate_interpretation','production_requirements'),
 'ANIMATION':('pose','timing','weight','anticipation','follow_through','locomotion','interaction',
    'facial_performance','lip_sync','physics_interaction','transitions','blending','continuity','movement_identity'),
 'CINEMATOGRAPHY':('composition','camera_movement','lens_perspective','staging','visual_hierarchy','continuity','mood','presentation'),
 'LIGHTING_PRESENTATION':('lighting','composition','staging','visual_hierarchy','continuity','mood','presentation'),
 'VFX':('particles','energy_effects','weather_effects','destruction','impacts','environmental_phenomena',
    'transitions','stylized_visual_feedback','timing','scale','performance_cost','gameplay_readability','cinematic_suitability'),
 'PRODUCTION_INTEGRATION':('compatibility','timing','dependencies','version_alignment','naming','scale',
    'spatial_placement','trigger_conditions','mix_presentation_balance','performance_budgets','platform_constraints','authority_lineage'),
 'CHARACTER':('world_authority','species_people','biology','culture','origin','family_history','identity',
    'physical_characteristics','personality','knowledge_beliefs','goals','skills_capabilities','relationships',
    'reputation','equipment_property','voice_identity','movement_identity','persistent_character_state'),
 'ASSET':('requirement','existing_asset_search','reuse_modify_create','asset_specification','technical_requirements',
    'creative_requirements','optimization_requirements','import_requirements','integration_requirements',
    'licensing_provenance','platform_constraints','dependencies'),
 'MUSIC':('intent','emotional_narrative_function','motif','melody','harmony','rhythm','meter','tempo',
    'instrumentation','orchestration','texture','dynamics','tension_release','form','transitions','silence',
    'thematic_identity','picture_synchronization','loop_structure','stems_layers','adaptive_transitions'),
 'VOICE':('character_identity','authorized_voice_identity','emotional_state','objective','motivation',
    'relationship','subtext','pacing','rhythm','emphasis','pronunciation','authored_accent_dialect','intensity',
    'breath_pause','interruption','distance','scene_context','continuity','performance_direction'),
 'SOUND':('source','material','action','environment','perspective','intensity','distance','timing',
    'physical_consequence','narrative_purpose','interaction_feedback','location','weather','time',
    'architecture','population','machinery','ecology','interior_exterior','silence',
    'position','direction','occlusion','obstruction','attenuation','reverb','listener_orientation','movement')}
MUSIC_STAGES=('UNDERSTANDING','COMPOSITION','SYMBOLIC_SCORE','RENDERING','MIXING_MASTERING','INTEGRATION','RUNTIME_PLAYBACK','VALIDATION')


class SharedCreativeModels:
    def __init__(self,path):self.documents=DocumentService(path)

    def resolve(self,owner,reference,project_id,medium):
        if medium not in {'GAME','ANIMATION'}:raise ValueError('Explicit downstream use required')
        if type(reference) is not dict or set(reference)!={'object_id','version','expected_hash'}:
            raise ValueError('Exact shared definition reference required')
        record=self.documents.retrieve(owner,**reference)
        if record['metadata']['project_id']!=project_id:raise PermissionError('Shared definition project mismatch')
        selected=self.documents.text_source(owner,**reference)
        extraction=selected['extraction']
        if extraction is not None and (extraction['state']!='TEXT_EXTRACTED' or extraction['format']!='UTF8_TEXT'):
            raise PermissionError('Extracted creative definition requires review before structured use')
        def unique(pairs):
            result={}
            for key,value in pairs:
                if key in result:raise ValueError('Duplicate creative definition field')
                result[key]=value
            return result
        def invalid(value):raise ValueError('Non-finite creative definition value')
        model=json.loads(selected['content'],object_pairs_hook=unique,parse_constant=invalid)
        required={'schema_version','identity','kind','definition','representations','use_requirements','source_references'}
        if type(model) is not dict or set(model)!=required or model['schema_version']!='SharedCreativeDefinition/1':
            raise ValueError('Complete shared creative definition required')
        if model['identity']!=record['object_id'] or model['kind'] not in FIELDS:
            raise ValueError('Creative identity/kind mismatch')
        definition=model['definition'];fields=FIELDS[model['kind']]
        if type(definition) is not dict or set(definition)!=set(fields):
            raise ValueError('Represent every required dimension explicitly; use null for unknown')
        if any(v is not None and (type(v) is not str or not v.strip()) for v in definition.values()):
            raise ValueError('Authored text or explicit unknown required')
        if type(model['representations']) is not dict or type(model['use_requirements']) is not dict:
            raise ValueError('Presentation and downstream requirements must remain separate')
        if set(model['use_requirements'])!={'GAME','ANIMATION'}:
            raise ValueError('Separate game and animation use requirements required')
        for use,requirements in model['use_requirements'].items():
            if requirements is not None and (type(requirements) is not list or any(type(v) is not str or not v.strip() for v in requirements)):
                raise ValueError('Explicit downstream requirement list or unknown required')
        refs=model['source_references']
        if type(refs) is not list or len(refs)>256:raise ValueError('Bounded creative source lineage required')
        linked=[]
        for ref in refs+list(model['representations'].values()):
            if type(ref) is not dict or set(ref)!={'object_id','version','expected_hash'}:raise ValueError('Exact creative lineage required')
            source=self.documents.retrieve(owner,**ref)
            if source['metadata']['project_id']!=project_id:raise PermissionError('Cross-project creative source')
            linked.append({'reference':ref,'source_hash':source['record_hash'],'kind':source['metadata']['kind']})
        unresolved=[name for name,value in definition.items() if value is None]
        if model['use_requirements'][medium] is None:unresolved.append('use_requirements.'+medium)
        if not refs:unresolved.append('source_references')
        if model['kind']=='ASSET':
            choice=definition['reuse_modify_create']
            if choice is not None and choice not in {'REUSE','MODIFY','CREATE'}:raise ValueError('Unknown asset decision')
            if choice is not None and not definition['existing_asset_search']:
                unresolved.append('existing_asset_search_before_decision')
        return {'contract':'SharedCreativeResolution/1','identity':model['identity'],'kind':model['kind'],
                'source_kind':record['metadata']['kind'],'authority_status':'DECLARED_SOURCE_ONLY','canon_accepted':False,
                'source_extraction':({k:v for k,v in extraction.items() if k!='segments'} if extraction else None),
                'definition_reference':reference,'definition_hash':digest(model),'definition':definition,
                'representations':model['representations'],'lineage':linked,'medium':medium,
                'use_requirements':model['use_requirements'][medium],
                'state':'REVIEW_REQUIRED' if unresolved else 'AUTHORED_REQUIREMENTS_RESOLVED',
                'unresolved':unresolved,'claims_validated':False,'readiness':'UNPROVEN','execution_authority':False,
                'music_capabilities':{stage:'NOT_ESTABLISHED' for stage in MUSIC_STAGES} if model['kind']=='MUSIC' else None}
