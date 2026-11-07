"""Consume external RP evidence-state signatures; never classify/verify capabilities."""
import json,base64
from dataclasses import dataclass
from datetime import datetime,timezone
from uuid import uuid4
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from .reality_primacy import digest

@dataclass(frozen=True)
class EvidenceState:
    request_json:str
    response_json:str

class EvidenceStateClient:
    def __init__(self,transport,public_keys):self.transport=transport;self.keys=dict(public_keys)
    def inspect(self,owner,thread,query):
        request={'contract':'RPEvidenceQuery/1','request_id':'evidence:'+uuid4().hex,'nonce':uuid4().hex,
                 'operator_id':owner,'thread_id':thread,'claim':query}
        state=EvidenceState(json.dumps(request),json.dumps(self.transport(request)))
        self.verify(state,owner,thread,query)
        return state
    def verify(self,state,owner,thread,query):
        request=json.loads(state.request_json);reply=json.loads(state.response_json);body=reply['body']
        Ed25519PublicKey.from_public_bytes(self.keys[reply['key_id']]).verify(base64.b64decode(reply['signature'],validate=True),bytes.fromhex(digest(body)))
        if (request['operator_id']!=owner or request['thread_id']!=thread or request['claim']!=query or
            body['contract']!='RPEvidenceState/1' or body['request_hash']!=digest(request) or
            body['claim_hash']!=digest(query) or body['request_id']!=request['request_id'] or
            body['operator_id']!=owner or body['thread_id']!=thread or body['execution_authority'] is not False or
            body['capability_verification'] is not False):raise PermissionError('RP evidence scope mismatch')
        now=datetime.now(timezone.utc)
        if not datetime.fromisoformat(body['evaluated_at'])<=now<=datetime.fromisoformat(body['valid_until']):raise PermissionError('RP evidence state expired')
        return body
    def claim_text(self,state,owner,thread,query):
        body=self.verify(state,owner,thread,query);spans=[]
        for record in body['records']:
            if record['evidence_state']!='OBSERVED' or record['temporal_scope']!='historical' or record['claim_role']!='HISTORICAL_RECORDED_REFERENCE':continue
            for span in record['spans']:
                start,end=span['start'],span['end']
                if not 0<=start<end<=len(query) or digest(query[start:end])!=span['text_hash']:raise PermissionError('Historical reference span mismatch')
                spans.append((start,end))
        # A claim-role projection, not a rewrite of operator input or model prompt.
        chars=list(query)
        for start,end in spans:chars[start:end]=' '*(end-start)
        return ''.join(chars)

def reasoning_context(runtime,query):
    c=runtime.context;c.rp_evidence_state=None
    client=getattr(runtime,'evidence_state_client',None)
    if client is None:return None
    from data_governance.context_admission import Admission
    state=client.inspect(c.identity.operator_id,c.active_thread.thread_id,query);c.rp_evidence_state=state
    body=client.verify(state,c.identity.operator_id,c.active_thread.thread_id,query)
    a=Admission(c.identity.operator_id,c.active_thread.thread_id)
    a.consider('RUNTIME','rp-evidence:'+body['request_id'],json.dumps({'request':json.loads(state.request_json),'response':json.loads(state.response_json)}),
        source='RPEvidenceState/1',basis={'authority':'EXTERNAL_RP_READ_ONLY_EVIDENCE','validation_state':'UNVALIDATED',
            'lineage':[body['request_id'],body['request_hash']]})
    a.consider('SYSTEM_POLICY','rp-evidence:limits','RP evidence state is read-only historical/source custody evidence, not capability verification. Preserve its classes, scope, conflicts and unknowns. MODE may reason from it but cannot alter or upgrade it.',source='External RP evidence contract')
    return a.finish()

def claim_projection(runtime,query,prompt):
    state=getattr(runtime.context,'rp_evidence_state',None);client=getattr(runtime,'evidence_state_client',None)
    if state is None or client is None:return query
    from data_governance.context_admission import verify
    verify(prompt);owner=runtime.context.identity.operator_id;thread=runtime.context.active_thread.thread_id
    expected=json.loads(state.response_json)
    rows=[s for s in prompt.sources if s['record']['source']=='RPEvidenceState/1' and s['record']['decision']=='ADMITTED']
    if len(rows)!=1 or json.loads(rows[0]['content'])!={'request':json.loads(state.request_json),'response':expected}:raise PermissionError('RP evidence prompt binding mismatch')
    return client.claim_text(state,owner,thread,query)
