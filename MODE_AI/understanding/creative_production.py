"""Shared creative preparation. Requires later Kernel execution and external RP.

Creative Production v1.2: actual play and observed rendered output are distinct
from source, compilation, file presence, and a declared production capability.
"""
from copy import deepcopy
from specs.document_service import DocumentService
from system_layer.contracts import digest

CAPABILITIES = ('WORLD_ENVIRONMENT','CHARACTER_CONSTRUCTION','ASSET_CONSTRUCTION',
    'NARRATIVE_STORY','CREATIVE_INTENT','MUSIC_COMPOSITION','VOICE_PERFORMANCE',
    'SOUND_DESIGN_SFX','FOLEY_AMBIENCE','SPATIAL_AUDIO','ANIMATION','CINEMATOGRAPHY',
    'LIGHTING_PRESENTATION','VFX','PRODUCTION_INTEGRATION')

PROOF_REQUIREMENTS = {
    'GAME': ('ACTUAL_PLAY','INPUT_RESPONSE_OBSERVED','RUNTIME_OUTCOME_OBSERVED',
             'PACKAGED_BUILD_OBSERVED','PACKAGED_LAUNCH_OBSERVED','PACKAGED_PLAY_OBSERVED'),
    'ANIMATION': ('RENDERED_OUTPUT_OBSERVED','FRAME_CONTENT_INSPECTED','MOTION_OBSERVED'),
}

def observation_requirements(request):
    """Claim-bound output requirements; no thresholds or successful results inferred."""
    requirements=list(PROOF_REQUIREMENTS[request['medium']])
    audio={'MUSIC_COMPOSITION','VOICE_PERFORMANCE','SOUND_DESIGN_SFX','FOLEY_AMBIENCE','SPATIAL_AUDIO'}
    if audio.intersection(request['capabilities']):
        requirements.append('AUDIO_PLAYBACK_OBSERVED')
        requirements.append('AUDIO_SYNCHRONIZATION_OBSERVED' if request['medium']=='ANIMATION' else 'INTERACTIVE_AUDIO_STATE_OBSERVED')
    return requirements

class CreativePreparation:
    def __init__(self,path):self.documents=DocumentService(path)

    def inspect_frames(self,owner,references,preparation=None,*,collector,thread_id,project_id=None):
        from runtime_observation.frame_inspection import inspect_frames
        binding={}
        if preparation is not None:
            self._check_preparation(owner,preparation)
            if project_id is not None and project_id!=preparation['request']['project_id']:
                raise PermissionError('Frame preparation project mismatch')
            project_id=preparation['request']['project_id']
            binding['creative_preparation_hash']=preparation['preparation_hash']
        if type(project_id) is not str or not project_id.strip():raise ValueError('Explicit frame project required')
        if type(references) is not list or not 1<=len(references)<=32:raise ValueError('Bounded selected frame references required')
        contents=[]
        for ref in references:
            if type(ref) is not dict or set(ref)!={'object_id','version','expected_hash'}:raise ValueError('Exact frame source reference required')
            if preparation is not None and ref not in preparation['request']['assets']:raise PermissionError('Frame not selected by preparation')
            record=self.documents.retrieve(owner,**ref)
            if record['metadata']['project_id']!=project_id:raise PermissionError('Frame project mismatch')
            contents.append(record['content'])
        value=inspect_frames(contents)
        observation=collector.collect(operator_id=owner,thread_id=thread_id,trace_reference=binding.get('creative_preparation_hash') or digest(references),
            runtime_error=None if value['state']=='MEASURED' else 'Frame comparison incomplete',
            metadata={**binding,'runtime_component':'runtime_observation.frame_inspection','project_id':project_id,
                'creative_evidence_kind':'FRAME_SOURCE_INSPECTED',
                'source_references':deepcopy(references),'observed_outcome':value,'required_evidence_fields':['observed_outcome']})
        self._require_persisted_observation(collector, observation)
        return {'contract':'CreativeFrameInspection/1','preparation_hash':binding.get('creative_preparation_hash'),'inspection':value,
            'observation_id':observation.observation_id,'observation_hash':digest(observation.to_dict()),
            'completion':'UNPROVEN','execution_authority':False}

    def inspect_audio(self,owner,reference,project_id,*,collector,thread_id,preparation=None):
        import base64
        import json
        from runtime_observation.audio_inspection import inspect_pcm,MAX_BYTES
        record=self.documents.retrieve(owner,**reference)
        if record['metadata']['project_id']!=project_id:raise PermissionError('Audio project mismatch')
        binding={}
        if preparation is not None:
            self._check_preparation(owner,preparation)
            if preparation['request']['project_id']!=project_id or reference not in preparation['request']['assets']:
                raise PermissionError('Audio source not selected by this preparation')
            binding['creative_preparation_hash']=preparation['preparation_hash']
        if len(record['content'])>MAX_BYTES*2:raise ValueError('Encoded audio exceeds inspection bound')
        def unique(pairs):
            value={}
            for key,item in pairs:
                if key in value:raise ValueError('Duplicate audio source field')
                value[key]=item
            return value
        payload=json.loads(record['content'],object_pairs_hook=unique)
        if type(payload) is not dict or set(payload)!={'schema_version','encoding','data','sha256'} or payload['schema_version']!='AudioSource/1' or payload['encoding']!='BASE64_WAV':
            raise ValueError('Explicit WAV source encoding required')
        value=inspect_pcm(base64.b64decode(payload['data'],validate=True),payload['sha256'])
        observation=collector.collect(operator_id=owner,thread_id=thread_id,trace_reference=record['record_hash'],
            runtime_error=None if value['state']=='MEASURED' else 'Audio inspection incomplete',
            metadata={**binding,'runtime_component':'runtime_observation.audio_inspection','project_id':project_id,
                'creative_evidence_kind':'AUDIO_STRUCTURE_INSPECTED','source_reference':reference,
                'observed_outcome':value,'quality_metrics':value['metrics'],
                'required_evidence_fields':['observed_outcome']})
        self._require_persisted_observation(collector, observation)
        return {'contract':'CreativeAudioInspection/1','source_reference':reference,'inspection':value,
                'observation_id':observation.observation_id,'observation_hash':digest(observation.to_dict()),
                'completion':'UNPROVEN','execution_authority':False}

    @staticmethod
    def _require_persisted_observation(collector, observation):
        stored = collector.store.load_record(observation.operator_id, observation.observation_id)
        if observation.collection_errors or stored is None or digest(stored.to_dict()) != digest(observation.to_dict()):
            raise OSError('Creative Observation custody failed; no evidence reference issued')

    def _check_preparation(self,owner,preparation):
        if (type(preparation) is not dict or preparation.get('contract')!='CreativeProductionPreparation/1'
                or preparation.get('operator_id')!=owner
                or preparation.get('preparation_hash')!=digest({k:v for k,v in preparation.items() if k!='preparation_hash'})):
            raise ValueError('Creative preparation identity/integrity mismatch')
        if preparation.get('required_observations')!=observation_requirements(preparation['request']):
            raise ValueError('Creative proof requirements changed')
        # A caller can recompute a public digest. Re-resolve source custody and
        # canonical preparation fields rather than trusting embedded state labels.
        resolved=self.prepare(owner,preparation['request'])
        if resolved!=preparation:
            raise ValueError('Creative preparation differs from canonical source resolution')

    def operational_models(self,owner,preparation,bindings,*,system_store):
        """Resolve existing System operational models, not a second capability registry."""
        from system_layer.audit.operational_understanding_validator import evaluate
        self._check_preparation(owner,preparation)
        if type(bindings) is not list:raise ValueError('Explicit operational bindings required')
        result=[];seen=set()
        for binding in bindings:
            if type(binding) is not dict or set(binding)!={'capability_id','system_id','model_receipt','inventory_receipt'}:
                raise ValueError('Exact operational binding required')
            capability=binding['capability_id']
            if capability not in preparation['request']['capabilities'] or capability in seen:
                raise ValueError('Unrequested or duplicate capability binding')
            seen.add(capability)
            model=system_store.get(owner,'operational-understanding:'+binding['system_id'])
            inventory=system_store.get(owner,'inventory:'+binding['system_id'])
            if model is None or inventory is None:
                result.append({'capability_id':capability,'state':'NOT_RETRIEVED','binding':dict(binding)});continue
            if model['receipt_id']!=binding['model_receipt'] or inventory['receipt_id']!=binding['inventory_receipt']:
                raise ValueError('Operational model or inventory superseded')
            assessment=evaluate(model['value']['model'],inventory['value'],current_system_version=inventory['value']['system_version'])
            sources=system_store.get(owner,'operational-sources:'+binding['system_id'])
            source_map=None
            if sources is not None:
                from system_layer.audit.operation_source_binding import assess
                if sources['value']['model_hash']!=model['value']['model']['model_hash'] or sources['value']['inventory_hash']!=inventory['value']['inventory_hash']:
                    source_map={'state':'REVIEW_REQUIRED','reason':'OPERATION_SOURCE_BINDING_SUPERSEDED'}
                else:source_map=assess(model['value']['model'],inventory['value'],sources['value']['bindings'])
            state='REVIEW_REQUIRED' if source_map and source_map['state']=='REVIEW_REQUIRED' else assessment['state']
            result.append({'capability_id':capability,'binding':dict(binding),'model':model['value']['model'],
                           'assessment':assessment,'state':state,'source_map':source_map,
                           'source_receipt':sources['receipt_id'] if sources else None})
        return {'contract':'CreativeOperationalResolution/1','preparation_hash':preparation['preparation_hash'],
                'capabilities':result,'unbound':[c for c in preparation['request']['capabilities'] if c not in seen],
                'execution_authority':False,'completion':'UNPROVEN'}

    def prepare(self,owner,request):
        fields={'project_id','medium','capabilities','assets','reuse_inventory_references','output_requirements'}
        if type(request) is not dict or not fields.issubset(request) or set(request)-fields-{'model_references'}:
            raise ValueError('Complete creative preparation request required')
        if type(request['project_id']) is not str or not request['project_id'].strip():raise ValueError('Project required')
        if request['medium'] not in PROOF_REQUIREMENTS:raise ValueError('Unsupported production medium')
        capabilities=request['capabilities']
        if type(capabilities) is not list or not capabilities or any(c not in CAPABILITIES for c in capabilities) or len(set(capabilities))!=len(capabilities):
            raise ValueError('Explicit unique shared capabilities required')
        requirements=request['output_requirements']
        if type(requirements) is not list or not requirements or any(type(r) is not str or not r.strip() for r in requirements):
            raise ValueError('Operator output requirements required')
        assets=[]
        for refs,kind in ((request['assets'],'asset'),(request['reuse_inventory_references'],'inventory')):
            if type(refs) is not list or len(refs)>256:raise ValueError('Bounded source selection required')
            for ref in refs:
                if type(ref) is not dict or set(ref)!={'object_id','version','expected_hash'}:raise ValueError('Exact creative source reference required')
                record=self.documents.retrieve(owner,**ref)
                if record['metadata']['project_id']!=request['project_id']:raise PermissionError('Creative source project mismatch')
                assets.append({'role':kind,'record':record})
        missing=[]
        if not request['reuse_inventory_references']:missing.append('EXISTING_ASSET_INVENTORY_NOT_RETRIEVED')
        shared=[]
        if 'model_references' in request:
            from .creative_models import SharedCreativeModels
            refs=request['model_references']
            if type(refs) is not list or len(refs)>256:raise ValueError('Bounded shared models required')
            resolver=SharedCreativeModels(self.documents.store.path)
            seen=set()
            for ref in refs:
                model=resolver.resolve(owner,ref,request['project_id'],request['medium'])
                if model['identity'] in seen:raise ValueError('Conflicting or duplicate shared identity selection')
                seen.add(model['identity']);shared.append(model)
                if model['state']=='REVIEW_REQUIRED':missing.append('SHARED_MODEL_REVIEW:'+model['identity'])
        # Inventory references establish custody only. Their claims still need inspection.
        value={'contract':'CreativeProductionPreparation/1','operator_id':owner,'request':deepcopy(request),
            'sources':assets,'shared_models':shared,'missing':missing,'state':'PREPARATION_ONLY',
            'capabilities':[{'capability_id':c,'operational_understanding':'NOT_ESTABLISHED'} for c in capabilities],
            'required_observations':observation_requirements(request),
            'validation':'PENDING_VALIDATION','execution':'NOT_EXECUTED','execution_authority':False,
            'completion':'UNPROVEN','required_external_validation':'REALITY_PRIMACY',
            'insufficient_completion_evidence':['SOURCE_PRESENT','COMPILED','FILE_EXISTS','COMMAND_EXIT_ZERO']}
        value['preparation_hash']=digest(value)
        return value

    def locate_observations(self,owner,preparation,references,*,observation_store):
        """Locate pinned Observation records for external validation; never judge them."""
        self._check_preparation(owner,preparation)
        required=observation_requirements(preparation['request'])
        if preparation.get('required_observations')!=required:raise ValueError('Creative proof requirements changed')
        if type(references) is not list or len(references)>256:raise ValueError('Bounded pinned observations required')
        located=[];unavailable=[];excluded=[];supplemental=[];seen=set()
        for ref in references:
            if type(ref) is not dict or set(ref)!={'observation_id','expected_hash'}:raise ValueError('Exact observation reference required')
            key=(ref['observation_id'],ref['expected_hash'])
            if key in seen:continue
            seen.add(key)
            try:record=observation_store.load_record(owner,ref['observation_id'])
            except FileNotFoundError:
                unavailable.append(dict(ref));continue
            if record is None:
                unavailable.append(dict(ref));continue
            value=record.to_dict()
            if digest(value)!=ref['expected_hash']:raise ValueError('Observation changed after selection')
            metadata=value['metadata'];kind=metadata.get('creative_evidence_kind')
            if (metadata.get('creative_preparation_hash')!=preparation['preparation_hash']
                    or metadata.get('project_id')!=preparation['request']['project_id']):
                raise PermissionError('Observation does not govern this creative preparation')
            if kind not in required:
                if kind in {'AUDIO_STRUCTURE_INSPECTED','FRAME_SOURCE_INSPECTED'}:
                    supplemental.append({'reference':dict(ref),'kind':kind,'observation':value,
                                         'satisfies_required_output_observation':False})
                    continue
                excluded.append({'reference':dict(ref),'reason':'NOT_REQUIRED_OUTPUT_OBSERVATION'});continue
            located.append({'reference':dict(ref),'kind':kind,'observation':value,
                'completeness':value.get('evidence_completeness','PARTIAL'),
                'collection_errors':value.get('collection_errors',[]),'sufficiency':'NOT_EVALUATED'})
        return {'contract':'CreativeEvidenceLocation/1','preparation_hash':preparation['preparation_hash'],
            'required':required,'located':located,'unavailable':unavailable,'excluded':excluded,'supplemental':supplemental,
            'missing':[kind for kind in required if not any(e['kind']==kind for e in located)],
            'validation':'PENDING_VALIDATION','completion':'UNPROVEN','execution_authority':False}
