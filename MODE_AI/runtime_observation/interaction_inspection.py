"""Read-only, owner-scoped correlation. Local records are evidence, not truth."""
import json
import hashlib
from pathlib import Path
from copy import deepcopy
from memory.thread_store import ThreadStore
from runtime_observation.observation_store import RuntimeObservationStore
from runtime_observation.observation_record import RuntimeObservationRecord

ROOT=Path(__file__).resolve().parents[1]
MAX_BYTES=64*1024*1024

def _sha(data):return hashlib.sha256(data).hexdigest()

class _ReadOnlyThreads(ThreadStore):
    def __init__(self,path):self.storage_dir=Path(path)
    def _operator_dir(self,owner):
        self._validate_identity(owner)
        return self.storage_dir/owner

class InteractionInspector:
    def __init__(self,observation_root=None,thread_root=None,trace_path=None,transformation_root=None):
        self.observation_root=Path(observation_root or ROOT/'runtime_data/runtime_observations')
        self.thread_root=Path(thread_root or ROOT/'data/threads')
        self.trace_path=Path(trace_path or ROOT/'runtime_traces/interactions.jsonl')
        self.transformation_root=Path(transformation_root or ROOT/'runtime_data/transformation_provenance')

    def _owned(self,owner,thread):
        ThreadStore._validate_identity(owner);ThreadStore._validate_identity(thread)
        path=self.thread_root/owner/(thread+'.json')
        self._contained(path,self.thread_root)
        if not path.is_file():raise PermissionError('Owned persisted thread required')
        if path.stat().st_size>MAX_BYTES:raise ValueError('Thread inspection bound exceeded')
        return _ReadOnlyThreads(self.thread_root).load_thread(owner,thread)

    @staticmethod
    def _contained(path,root):
        if not path.resolve().is_relative_to(root.resolve()):raise PermissionError('Evidence path escaped owner store')
        for part in [path,*path.parents]:
            if part==root:break
            if part.is_symlink():raise PermissionError('Linked evidence path refused')

    def _records(self,owner,thread):
        owned=self._owned(owner,thread)
        directory=self.observation_root/owner
        self._contained(directory,self.observation_root)
        paths=list(directory.glob('*.json'))
        if len(paths)>2048 or sum(p.stat().st_size for p in paths)>MAX_BYTES:
            raise ValueError('Observation inspection bound exceeded')
        for path in paths:self._contained(path,self.observation_root)
        # Reuse the existing deserializer/scope checks without its mkdir initializer.
        store=RuntimeObservationStore.__new__(RuntimeObservationStore);store.storage_dir=self.observation_root
        records=store.load_records_by_thread(owner,thread)
        completed={m.metadata.get('runtime_observation_id') for m in owned.messages if m.role=='mode'}
        return [r for r in records if r.observation_id in completed and r.response_text and r.runtime_state_end]

    def candidates(self,operator_id,thread_id,interaction_id=None):
        rows=[]
        for r in self._records(operator_id,thread_id):
            m=r.metadata;identity=m.get('interaction_id');u=m.get('understanding',{})
            if identity and (interaction_id is None or identity==interaction_id):
                raw=json.loads((self.observation_root/operator_id/(r.observation_id+'.json')).read_bytes())
                rows.append({'interaction_id':identity,'created_at':raw.get('created_at') or '',
                    'controller_clarification_required':m.get('interpreted_intent',{}).get('clarification_required'),
                    'understanding_operation_state':u.get('state')})
        return sorted(rows,key=lambda x:(x['created_at'],x['interaction_id']),reverse=True)[:8]

    def inspect_interaction(self,operator_id,thread_id,interaction_id):
        ThreadStore._validate_identity(interaction_id)
        matches=[r for r in self._records(operator_id,thread_id) if r.metadata.get('interaction_id')==interaction_id]
        if len(matches)!=1:raise PermissionError('One completed owner/thread interaction required')
        opath=self.observation_root/operator_id/(matches[0].observation_id+'.json')
        snapshot=opath.read_bytes()
        raw=json.loads(snapshot)
        r=RuntimeObservationRecord.from_dict(raw)
        if (r.operator_id!=operator_id or r.thread_id!=thread_id or r.observation_id!=matches[0].observation_id
                or r.metadata.get('interaction_id')!=interaction_id):
            raise PermissionError('Observation identity changed during correlation')
        m=r.metadata;u=m.get('understanding',{});intent=m.get('interpreted_intent',{})
        rows=[];trace_errors=[]
        if self.trace_path.exists():
            if self.trace_path.is_symlink() or self.trace_path.stat().st_size>MAX_BYTES:raise ValueError('Trace inspection bound exceeded')
            with self.trace_path.open('rb') as stream:
                for number,line in enumerate(stream,1):
                    try:
                        data=json.loads(line)
                        if type(data) is not dict:raise ValueError('Trace row must be an object')
                    except (ValueError,UnicodeError):trace_errors.append(number);continue
                    if data.get('interaction_id')==interaction_id:
                        if data.get('session_id')!=thread_id:raise PermissionError('Trace thread correlation conflict')
                        rows.append((number,line,data))
        if len(rows)>1:raise PermissionError('Ambiguous duplicate trace rows')
        trace=rows[0][2] if rows else {};sources={};unavailable=[]
        def field(key,value,source):
            if value=='':value=None
            sources[key]={'status':'UNAVAILABLE' if value is None else 'RECORDED','source':source if value is not None else None}
            if value is None:unavailable.append(key)
            return deepcopy(value)
        disposition=trace.get('disposition')
        disposition_source='trace_row.disposition'
        if disposition is None:
            disposition=m.get('clarification_state',{}).get('disposition')
            disposition_source='Observation.metadata.clarification_state.disposition'
        observed={
            'controller':{k:field('controller.'+k,trace.get(k),'trace_row') for k in
                ('clarification_required','halt_required','ambiguity_score','selected_posture')},
            'clarification_disposition':field('clarification_disposition',disposition,disposition_source),
            'public_result':{'clarification_required':field('public_result.clarification_required',intent.get('clarification_required'),'Observation.metadata.interpreted_intent'),
                'halt_required':field('public_result.halt_required',intent.get('halt_required'),'Observation.metadata.interpreted_intent'),
                'failure_state':field('public_result.failure_state',m.get('observed_outcome',{}).get('failure_state'),'Observation.metadata.observed_outcome'),
                'success':field('public_result.success',m.get('completion_claim',{}).get('controller_success'),'Observation.metadata.completion_claim')},
            'publication_gate':field('publication_gate',m.get('response_governance'),'Observation.metadata.response_governance'),
            'runtime_phase':{'before':field('runtime_phase.before',raw.get('runtime_state_start'),'Observation.runtime_state_start'),
                'after':field('runtime_phase.after',raw.get('runtime_state_end'),'Observation.runtime_state_end')},
            'understanding':{k:field('understanding.'+k,u.get(k),'Observation.metadata.understanding') for k in
                ('request_id','result_id','understanding_id','transition_id','state','readiness','reason','warnings','errors','retry_information')},
            'declared_controller_component':field('declared_controller_component',m.get('authority_source'),'Observation.metadata.authority_source'),
            'declared_understanding_component':field('declared_understanding_component',u.get('producer'), 'Observation.metadata.understanding.producer'),
            'clarification_count':field('clarification_count',raw.get('clarification_count'),'Observation.clarification_count')}
        # Gate bodies can contain unrelated details: project the decision only.
        if observed['publication_gate'] is not None:
            observed['publication_gate']={k:observed['publication_gate'].get(k) for k in ('decision','allowed','reasons','publication_scope')}
        conflicts=[]
        for key in ('clarification_required','halt_required'):
            if key in trace and key in intent and trace[key]!=intent[key]:conflicts.append('Trace/public result disagree: '+key)
        result={'contract':'InteractionInspection/1','operator_id':operator_id,'thread_id':thread_id,
            'interaction_id':interaction_id,'observation_id':r.observation_id,'observed':observed,
            'field_sources':sources,'unavailable':unavailable,'correlation_conflicts':conflicts,
            'known_ids':{k:m.get(k) for k in ('interaction_id','reasoning_id','correlation_id','runtime_session_id')},
            'evidence_references':{'observation':{'path':str(opath),'sha256':_sha(snapshot)},
                'trace_row':{'path':str(self.trace_path),'line':rows[0][0],'sha256':_sha(rows[0][1])} if rows else None},
            'trace_parse_error_lines':trace_errors[:20],'interpretation':None,
            'validation_state':'RECORDED_NOT_INDEPENDENTLY_VALIDATED','execution_authority':False,
            'limits':['No missing events reconstructed. No code-analysis explanation supplied.',
                'Recorded COMPLETE is a runtime phase, not proof of external success.',
                'Scope/byte hashes establish correlation and byte identity, not truth.']}
        from .transformation_provenance import TransformationStore
        events=TransformationStore(self.transformation_root).read(operator_id,thread_id,interaction_id)
        result['transformation_provenance']={'status':'OBSERVED' if events else 'UNAVAILABLE','records':events,
            'recording_errors':m.get('transformation_recording_errors',[])+m.get('understanding_provenance_errors',[]),
            'historical_backfill':False,'validation_state':'RECORDED_NOT_INDEPENDENTLY_VALIDATED'}
        if len(json.dumps(result).encode('utf-8'))>16384:raise ValueError('Inspection projection bound exceeded')
        return result

def inspect_interaction(operator_id,thread_id,interaction_id):
    return InteractionInspector().inspect_interaction(operator_id,thread_id,interaction_id)
