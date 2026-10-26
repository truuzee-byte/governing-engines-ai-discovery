"""Prospective diagnostic events. No semantic writes or execution authority.

One exclusive-created file per event, hash-linked within an interaction. This
detects modification/gaps, not a privileged local administrator rewriting history.
"""
import json
import hashlib
import os
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone
from contextlib import contextmanager
from contextvars import ContextVar
from threading import RLock
from memory.thread_store import ThreadStore

_scope = ContextVar('transformation_provenance', default=None)
_lock = RLock()
UNAVAILABLE = 'UNAVAILABLE'

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

class TransformationStore:
    def __init__(self,root=None):
        self.root=Path(root or 'runtime_data/transformation_provenance').resolve()
        # Owner/thread/interaction custody creates deep paths on Windows.
        if os.name=='nt' and not str(self.root).startswith('\\\\?\\'):
            self.root=Path('\\\\?\\'+str(self.root))

    def _directory(self,owner,thread,interaction):
        for value in (owner,thread,interaction):ThreadStore._validate_identity(value)
        from .interaction_inspection import InteractionInspector
        path=self.root/owner/thread/interaction
        InteractionInspector._contained(path,self.root)
        return path

    def read(self,owner,thread,interaction):
        path=self._directory(owner,thread,interaction)
        files=sorted(path.glob('*.json'))
        if len(files)>16 or sum(f.stat().st_size for f in files)>32768:
            raise ValueError('Transformation inspection bound exceeded')
        rows=[];previous=None
        for sequence,f in enumerate(files,1):
            from .interaction_inspection import InteractionInspector
            InteractionInspector._contained(f,self.root)
            raw=f.read_bytes();row=json.loads(raw)
            h=row.pop('record_hash')
            if (row['operator_id']!=owner or row['thread_id']!=thread or row['interaction_id']!=interaction
                    or row['sequence']!=sequence or row['previous_hash']!=previous or digest(row)!=h):
                raise PermissionError('Transformation custody/correlation failure')
            row['record_hash']=h;previous=h
            rows.append({'record':row,'reference':{'path':str(f),'sha256':hashlib.sha256(raw).hexdigest()}})
        return rows

    def append(self,owner,thread,interaction,event):
        with _lock:
            fields={'producer','prior','incoming_event','context_used','rules','transformation','result',
                    'reason','downstream_consumers','direct_evidence','confidence','correlation'}
            if set(event)!=fields:raise ValueError('Exact transformation event fields required')
            prior=self.read(owner,thread,interaction)
            row={'contract':'TransformationProvenance/1','transition_id':'transformation-'+uuid4().hex,
                'operator_id':owner,'thread_id':thread,'interaction_id':interaction,
                'sequence':len(prior)+1,'previous_hash':prior[-1]['record']['record_hash'] if prior else None,
                'timestamp':datetime.now(timezone.utc).isoformat(),'epistemic_status':'OBSERVED',
                'validation_state':'RECORDED_NOT_INDEPENDENTLY_VALIDATED','execution_authority':False,**event}
            row['unavailable']=[k for k,v in event.items() if v==UNAVAILABLE]
            row['record_hash']=digest(row)
            body=json.dumps(row,ensure_ascii=False,sort_keys=True).encode()
            if len(prior)>=16 or len(body)>8192 or sum(len(json.dumps(r['record']).encode()) for r in prior)+len(body)>32768:
                raise ValueError('Transformation recording bound exceeded')
            path=self._directory(owner,thread,interaction);path.mkdir(parents=True,exist_ok=True)
            with (path/(f'{row["sequence"]:03d}-'+row['transition_id']+'.json')).open('xb') as stream:
                stream.write(body);stream.flush();os.fsync(stream.fileno())
            return row['transition_id']

@contextmanager
def recording(owner,thread,*,interaction=None,store=None,correlation=None):
    context={'owner':owner,'thread':thread,'interaction':interaction,'store':store or TransformationStore(),
             'correlation':correlation or {},'errors':[]}
    token=_scope.set(context)
    try:yield context
    finally:_scope.reset(token)

def emit(*,component,stage,prior,event,context,rules,transformation,result,
         reason=UNAVAILABLE,consumers=UNAVAILABLE,evidence=UNAVAILABLE,interaction=None,correlation=None):
    scope=_scope.get()
    if scope is None:return None
    try:
        return scope['store'].append(scope['owner'],scope['thread'],interaction or scope['interaction'],{
            'producer':{'component':component,'stage':stage},'prior':prior,'incoming_event':event,
            'context_used':context,'rules':rules,'transformation':transformation,'result':result,
            'reason':reason or UNAVAILABLE,'downstream_consumers':consumers,'direct_evidence':evidence,
            'confidence':UNAVAILABLE,'correlation':{**scope['correlation'],**(correlation or {})}})
    except Exception as exc:
        # Diagnostics cannot silently change the producer's operational result.
        scope['errors'].append({'type':type(exc).__name__,'stage':stage})
        return None
