"""Mode consumes signed external RP results. No RP decision implementation."""
import base64
from copy import deepcopy
import hashlib
import json
from uuid import uuid4
from datetime import datetime, timezone
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')).hexdigest()


class RealityAcceptanceClient:
    def __init__(self,transport,public_keys,clock=None):
        self._transport=transport;self._keys=dict(public_keys);self._used=set()
        self._clock=clock or (lambda: datetime.now(timezone.utc))

    def evaluate(self,request):
        request=deepcopy(request)
        try:
            if request["request_id"] in self._used: raise ValueError("Transition request already consumed; obtain a new governed evaluation")
            self._used.add(request["request_id"])
            request["nonce"]=uuid4().hex
            reply=deepcopy(self._transport(deepcopy(request)))
            return self.verify_response(request, reply)
        except Exception as error:
            return {'accepted':False,'rp_state':None,'request':request,'response':locals().get('reply'),
                    'reason':'External RP acceptance blocked: '+type(error).__name__+': '+str(error)}

    def verify_response(self, request, reply):
        """Verify a retained signed response at consumption time; no new RP decision.

        The original nonce/request stays bound. This does not consume a new
        transition or renew validity; expiry is checked against the current clock.
        """
        request=deepcopy(request);reply=deepcopy(reply)
        key=Ed25519PublicKey.from_public_bytes(self._keys[reply['key_id']])
        key.verify(base64.b64decode(reply['signature'],validate=True),bytes.fromhex(digest(reply['body'])))
        body=reply['body']
        if body['contract']!='RPTransitionResponse/1' or body['request_hash']!=digest(request) or body['request_id']!=request['request_id']:
            raise ValueError('RP response request mismatch')
        view=body['show_chain']
        if not view or view['status']!='VERIFIED':raise ValueError('External RP did not return an intact decision')
        data=view['structured'];outcome=data['outcome'];decision=data['source_decision']['transition']
        state=data['final_state']
        if state not in {'CONFIRMED','DISCONFIRMED','PENDING_VALIDATION'}:raise ValueError('Unknown RP state')
        if digest(data['scope'])!=digest(request['scope']) or outcome['claim_id']!=request['claim_id']:
            raise ValueError('RP scope/claim mismatch')
        if decision['source_state']!=request['source_state'] or decision['proposed_target_state']!=request['target_state']:
            raise ValueError('RP transition mismatch')
        if decision['transition_id'] != data['decision_id']:
            raise ValueError('RP transition identity mismatch')
        if outcome['final_state']!=state or data['outcome']['validity']['evaluated_at']!=body['evaluated_at']:
            raise ValueError('RP state/time mismatch')
        policy=request['evaluation']['authority']
        def instant(value):
            value=datetime.fromisoformat(value) if isinstance(value,str) else value
            if value.tzinfo is None: raise ValueError('Unzoned RP validity time')
            return value
        now=instant(self._clock())
        if not instant(policy['valid_from']) <= instant(body['evaluated_at']) <= now <= instant(policy['valid_until']):
            raise ValueError('Stale RP authorization; revalidation required')
        original=data['source_decision']['chain']['provenance']['input_snapshots']['resolution']['claim_snapshot']
        if digest(original)!=digest(request['evaluation']['resolution']['claim_snapshot']):
            raise ValueError('RP claim/version mismatch')
        return {'accepted':state=='CONFIRMED','rp_state':state,'request':request,'response':reply,
                'acceptance_checked_at':now.isoformat(),'authority_valid_until':policy['valid_until'],
                'outcome':deepcopy(outcome),'decision_id':data['decision_id'],'chain_id':data['chain_id'],
                'receipt_id':data['receipt_id'],'reason':data['rationale']}
