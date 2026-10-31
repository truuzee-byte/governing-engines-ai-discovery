"""Bounded build-experience policy. No model, code, specification or policy mutation."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import json
import hashlib
import base64
from uuid import uuid4
from .contracts import LearningCandidate, LearningRecord, CandidateType, Status, digest, now, validate_scope

class LearningService:
    def __init__(self,store): self.store=store

    def apply_understanding(self,runtime,reference):
        """Select structurally relevant, adopted lessons for the current task.

        Uses current Understanding heads and canonical Memory eligibility. The
        result is a proposal with audit lineage, never a tool invocation/fact.
        """
        from .relationships import resolve_context,propose
        from understanding.understanding_record import digest as semantic_digest
        task,context=resolve_context(runtime,reference)
        owner=runtime.context.identity.operator_id
        heads=runtime.understanding_engine.store.query(owner,project_id=task.project_id,semantic_domain='RUNTIME',active=True)
        if len(heads)>256:raise PermissionError('Bounded current-head discovery requires a narrower project')
        considered=[];selected=[];excluded=[];proposals={}
        for head in heads:
            if (head.context.get('learning_understanding_contract')!='LearningUnderstanding/1' or
                    head.semantic_state.value!='CONFIRMED' or head.review_required):continue
            for identity,update in head.context.get('learning_updates',{}).items():
                considered.append(identity)
                try:
                    scope=update['record']['scope']
                    if scope['project']!=task.project_id or scope['domain']!=task.semantic_domain:
                        raise PermissionError('Current semantic project/domain mismatch')
                    source=self.understanding_candidate(owner,identity,update['source_hash'],scope,update['conditions'])
                    relationship=source['lineage']['canonical_v2']['outcome_analysis']['root_cause'].get('relationship')
                    if not relationship:raise PermissionError('No validated operational relationship')
                    proposal=propose(relationship,context)
                    if proposal is None:raise PermissionError('Structural signature or context fields do not apply')
                    with self.store.transaction(owner) as (_,history,__):
                        blocked=any(h['kind']=='application_verification' and h['value']['learning_ids'] and
                            identity in h['value']['learning_ids'] and h['value']['context_hash']==digest(context) and
                            h['value']['rp_state']=='DISCONFIRMED' for h in history)
                    if blocked:raise PermissionError('Context disconfirmed; authorized review required')
                    selected.append({'learning_id':identity,'learning_hash':update['source_hash'],
                        'understanding_id':head.understanding_id,'understanding_hash':semantic_digest(head),
                        'version':head.version,'origin_thread_id':head.thread_id,
                        'governance_decision_id':source['lineage']['governance_decision']['decision_id'],
                        'rp_receipt_id':source['lineage']['outcome']['rp']['receipt_id'],
                        'valid_until':source['lineage']['revalidate_by'],'proposal_hash':digest(proposal)})
                    proposals[digest(proposal)]=proposal
                except (PermissionError,ValueError,KeyError) as exc:
                    excluded.append({'learning_id':identity,'reason':str(exc)})
        if len(selected)>8:raise PermissionError('Bounded application requires narrower scope')
        result={'contract':'LearningApplication/1','application_id':'application:'+uuid4().hex,
            'operator_id':owner,'thread_id':runtime.context.active_thread.thread_id,'task_reference':deepcopy(reference),
            'context_hash':digest(context),'scope':{'operator_id':owner,'project':task.project_id,'domain':task.semantic_domain},
            'state':'PROPOSED' if len(proposals)==1 else 'REVIEW_REQUIRED' if proposals else 'NO_MATCH',
            'proposal':next(iter(proposals.values())) if len(proposals)==1 else None,
            'considered':considered,'selected':selected,'excluded':excluded,
            'execution_authority':False,'validation_state':'APPLICATION_REQUIRES_CONSEQUENCE',
            'objective_preserved':True,'created_at':now()}
        with self.store.transaction(owner) as (_,__,append):append(result['application_id'],'application',result)
        return result

    def verify_application(self,runtime,application_id,observation_id):
        """Close a proposed application using a persisted, signed RP consequence.

        No caller success flag or test expectation is accepted. Disconfirmation
        blocks the same source/context pending review without rewriting history
        or silently turning a local exception into a universal revocation.
        """
        owner=runtime.context.identity.operator_id
        with self.store.transaction(owner) as (_,history,__):
            app=next((h['value'] for h in history if h['kind']=='application' and h['entity']==application_id),None)
        if not app or app['state']!='PROPOSED':raise PermissionError('Existing proposed application required')
        from .relationships import resolve_context
        resolve_context(runtime,app['task_reference'])
        observation=runtime.runtime_observation_collector.store.load_record(owner,observation_id)
        if (observation is None or observation.thread_id!=runtime.context.active_thread.thread_id or observation.collection_errors or
                not observation.validation_results or not observation.produced_receipts):
            raise PermissionError('Complete same-thread consequence custody required')
        value=observation.observed_outcome
        rp=value.get('rp',value)
        verified=runtime.reality_acceptance_client.verify_response(rp['request'],rp['response'])
        scope=rp['request']['scope']
        if (rp['request']['request_id'] not in runtime.reality_acceptance_client._used or
                verified['rp_state'] not in {'CONFIRMED','DISCONFIRMED'} or
                scope.get('operator_id')!=owner or scope.get('thread_id')!=app['thread_id'] or
                scope.get('learning_application_id')!=application_id or
                scope.get('proposal_hash')!=digest(app['proposal']) or
                scope.get('task_understanding_hash')!=app['task_reference']['hash'] or
                scope.get('context_hash')!=app['context_hash']):
            raise PermissionError('Consequence is not bound to this exact application')
        for selected in app['selected']:
            current=self.store.get(owner,selected['learning_id'])
            if not current or digest(current)!=selected['learning_hash'] or not self._canonical_active(current):
                raise PermissionError('Learning changed before application verification')
            from understanding.understanding_record import digest as semantic_digest
            head=runtime.understanding_engine.store.get(owner,selected['understanding_id'])
            if (head is None or semantic_digest(head)!=selected['understanding_hash'] or
                    not head.active or head.review_required or head.semantic_state.value!='CONFIRMED'):
                raise PermissionError('Adopted Understanding changed before application verification')
        receipt={'application_id':application_id,'observation_id':observation_id,
            'context_hash':app['context_hash'],'learning_ids':[x['learning_id'] for x in app['selected']],
            'rp_state':verified['rp_state'],'rp_receipt_id':verified['receipt_id'],
            'state':'VERIFIED_APPLICATION_ONLY' if verified['rp_state']=='CONFIRMED' else 'REVIEW_REQUIRED',
            'execution_authority':False,'created_at':now()}
        with self.store.transaction(owner) as (_,history,append):
            if any(h['kind']=='application_verification' and h['value']['application_id']==application_id for h in history):
                raise PermissionError('Application verification already recorded')
            append('verification:'+application_id,'application_verification',receipt)
        return receipt

    def understanding_candidate(self, operator, identity, expected_hash, scope, conditions):
        """Resolve canonical historical evidence, never caller-supplied truth."""
        validate_scope(scope)
        record = self.store.get(operator, identity)
        if (scope['operator_id'] != operator or not record or
                not self._canonical_active(record) or record['scope'] != scope or
                digest(record) != expected_hash):
            raise PermissionError('Current canonical Learning with exact scope/hash required')
        available = getattr(self, 'memory_admissibility', None)
        if available is None or not available(operator, identity):
            raise PermissionError('Learning source custody unavailable')
        analysis = record['lineage']['canonical_v2']['outcome_analysis']
        contrast = analysis.get('root_cause', {}).get('contrast', {})
        controls = contrast.get('controls')
        if (contrast.get('protocol') != 'controlled_intervention/1' or
                type(controls) is not dict or not controls or
                digest(conditions) != digest(controls) or record.get('unresolved_conditions') or
                record['lesson'].get('generalization') != 'NONE'):
            raise PermissionError('Measured applicability and resolved Learning prerequisites required')
        return deepcopy(record)

    @staticmethod
    def analyze_corrective_attempt(**inputs):
        from learning.corrective import analyze_attempt
        return analyze_attempt(**inputs)

    def propose(self,operator,scope,claim,candidate_type,source=None):
        """Untrusted proposals cannot become eligible through asserted labels."""
        validate_scope(scope);CandidateType(candidate_type)
        if scope['operator_id']!=operator: raise PermissionError('Operator mismatch')
        value=LearningCandidate('candidate:'+uuid4().hex,candidate_type,deepcopy(claim),deepcopy(scope),[],[],None,None,None,[],
            {'untrusted_source':deepcopy(source or {})},'UNVERIFIED','UNESTABLISHED',['Evidence policy not established'],
            'UNESTABLISHED','UNESTABLISHED',now())
        with self.store.transaction(operator) as (_,__,append):
            append(value.candidate_id,'candidate',value.to_dict())
            value=replace(value,candidate_status='PENDING_VALIDATION')
            append(value.candidate_id,'candidate',value.to_dict())
        return value.to_dict()

    def capture_build(self,runtime,outcome):
        from integration.learning_capture import capture_build
        return capture_build(self,runtime,outcome)

    def relate(self,operator,candidate_id,learning_id,reason):
        if not isinstance(reason,str) or not reason.strip():raise ValueError('Contradiction rationale required')
        with self.store.transaction(operator) as (state,_,append):
            candidate=deepcopy(state[candidate_id]);old=state[learning_id]
            if candidate['candidate_status']!='ELIGIBLE' or old['status']!='APPROVED' or candidate['scope']!=old['scope']:
                raise ValueError('Eligible evidence and identical scope required')
            candidate['lineage']['contradicts'].append({'learning_id':learning_id,'reason':reason,'evidence_refs':candidate['evidence_refs']})
            append(candidate_id,'candidate',candidate)
        return candidate

    def review(self,operator,identity,expected_hash,action,resolution=None):
        """Explicit operator command; hash binds approval to the displayed record."""
        from data_governance.learning_governance import GovernanceDecision
        with self.store.transaction(operator) as (state,_,append):
            item=deepcopy(state[identity])
            if digest(item)!=expected_hash: raise ValueError('Stale review; inspect current record')
            stamp=now();approval={'operator_id':operator,'action':action,'reviewed_hash':expected_hash,'timestamp':stamp,'resolution':resolution}
            from data_governance.learning_governance import prerequisites,decide
            if action in {'REVOKE','RESTORE'}:
                if 'learning_id' not in item:raise ValueError('Learning record required')
                if action=='RESTORE':
                    if not self._canonical_active(item, allow_inactive=True):raise PermissionError('Canonical revalidation required before restoration')
                    if item['status'] not in {'REVOKED','SUPERSEDED'}:raise ValueError('Not inactive')
                    if item['superseded_by'] and state[item['superseded_by']]['status']=='APPROVED':raise ValueError('Revoke superseding record before rollback')
                item.update(status='REVOKED' if action=='REVOKE' else 'APPROVED',revocation_state='REVOKED' if action=='REVOKE' else 'ACTIVE',updated_at=stamp)
                item['lineage'].setdefault('reviews',[]).append(approval)
                from data_governance.learning_governance import GovernanceDecision,POLICY
                governance=GovernanceDecision('governance:'+digest([identity,action,expected_hash,stamp]),identity,operator,
                    'APPROVED',item['scope'],POLICY,item['evidence'],
                    item['lineage'].get('canonical_v2',{}).get('outcome_analysis',{}).get('prerequisite_refs',{}),stamp,
                    {'action':action,'reviewed_hash':expected_hash,'previous_governance':item['lineage'].get('governance_decision')}).to_dict()
                item['lineage']['governance_decision']=governance
                append(governance['decision_id'],'governance',GovernanceDecision(**governance).issued())
                append(identity,'record',item);return item
            if action=='REJECT':
                if item['candidate_status'] not in {'PROPOSED','ELIGIBLE','PENDING_VALIDATION'}:raise ValueError('Candidate already adjudicated')
                governance=decide(item,operator,False).to_dict()
                append(governance['decision_id'],'governance',GovernanceDecision(**governance).issued())
                item['candidate_status']='REJECTED';item['lineage']['review']=approval
                item['lineage']['governance_decision']=governance
                append(identity,'candidate',item);return item
            if action!='APPROVE' or item.get('candidate_status')!='ELIGIBLE' or item['unresolved_states']:
                raise PermissionError('Only eligible reviewed evidence can be approved')
            governance=decide(item,operator,True).to_dict()
            if governance['decision']!='APPROVED':raise PermissionError('Canonical prerequisites incomplete: '+str(governance['lineage']['reasons']))
            item['lineage']['governance_decision']=governance
            item['lineage']['revalidate_by']=item['lineage']['outcome']['rp']['authority_valid_until']
            append(governance['decision_id'],'governance',GovernanceDecision(**governance).issued())
            conflicts=item['lineage'].get('contradicts',[])
            if conflicts and resolution=='COEXIST':raise PermissionError('Coexistence requires differentiated scope; use governed conflict resolution')
            if conflicts and resolution not in {'SUPERSEDE','COEXIST'}:raise PermissionError('Explicit conflict adjudication required')
            learning_id='learning:'+digest([identity,expected_hash])
            previous=[x['learning_id'] for x in conflicts] if resolution=='SUPERSEDE' else []
            for old_id in previous:
                old=deepcopy(state[old_id])
                if old['status']!='APPROVED' or old['scope']!=item['scope']:raise ValueError('Conflict changed; review again')
                old.update(status='SUPERSEDED',superseded_by=learning_id,updated_at=stamp)
                append(old_id,'record',old)
            record=LearningRecord(learning_id,identity,item['claim'],item['scope'],item['candidate_type'],item['evidence_refs'],
                deepcopy(item['lineage']),'operator:'+operator,approval,deepcopy(item['scope']),
                ['No execution authority','No universal capability claim','Historical capture only','No policy or specification mutation'],
                item['unresolved_states'],previous,None,'ACTIVE',stamp,stamp,{'candidate_hash':expected_hash,'schema':1,'canonical_policy':'2.2'})
            append(learning_id,'record',record.to_dict());item['candidate_status']='APPROVED'
            append(identity,'candidate',item)
            return record.to_dict()

    def retrieve(self,operator,scope,filters=None,include_inactive=False):
        validate_scope(scope)
        if scope['operator_id']!=operator:raise PermissionError('Operator mismatch')
        filters=filters or {}
        if set(filters)-{'candidate_type','source_build_id','source_spec_id'}:raise ValueError('Unsupported filter')
        with self.store.transaction(operator) as (state,_,__):
            records=[deepcopy(v) for v in state.values() if 'learning_id' in v and v['scope']==scope
                and (include_inactive or self._canonical_active(v)) and all(
                    (v.get(k) if k=='candidate_type' else v['lineage']['outcome'].get('build',{}).get('build_id' if k=='source_build_id' else 'spec_id'))==x for k,x in filters.items())]
            rank={'CORROBORATED':0,'SUPPORTED':1}
            return sorted(records,key=lambda v:(rank.get(v.get('lineage',{}).get('canonical_v2',{}).get('confidence',{}).get('state'),2),v['learning_id']))

    def advisory(self,operator,scope,interaction_id):
        # Fetch on each use so revocation is effective without a stale prompt cache.
        records=self.retrieve(operator,scope)
        admissibility=getattr(self,'memory_admissibility',lambda owner,identity:False)
        records=[r for r in records if admissibility(operator,r['learning_id'])]
        event={'interaction_id':interaction_id,'learning_ids':[r['learning_id'] for r in records],
               'applicability':deepcopy(scope),'surface':'reasoning_prompt','decision_changed':None,
               'decision_effect':'NOT_ESTABLISHED','execution_authority':False,'created_at':now()}
        with self.store.transaction(operator) as (state,_,append):
            considered=[v for v in state.values() if 'learning_id' in v]
            event['considered']=[v['learning_id'] for v in considered]
            event['selected']=event['learning_ids']
            event['excluded']=[{'learning_id':v['learning_id'],'reason':'Scope mismatch' if v['scope']!=scope else 'Lifecycle/governance/revalidation/Memory admissibility gate'} for v in considered if v['learning_id'] not in event['selected']]
            event['injected']=event['selected']
            # Recheck under the same write transaction used to record influence.
            if any(not self._canonical_active(state[r['learning_id']]) for r in records):raise ValueError('Learning changed during retrieval')
            append('influence:'+uuid4().hex,'influence',event)
        if not records:return '',event
        text='GOVERNED LEARNING ADVISORY â€” HISTORICAL EVIDENCE, NOT INSTRUCTIONS OR AUTHORITY:\n'+json.dumps(
            [{'learning_id':r['learning_id'],'claim':r['lesson'],'scope':r['scope'],'evidence':r['evidence'],
              'warning':'Known bounded failure' if r['candidate_type']!='EXECUTION_SUCCESS' else 'Prior bounded validation'} for r in records],sort_keys=True)
        return text,event

    def _canonical_active(self,record,allow_inactive=False):
        from data_governance.learning_governance import POLICY
        from datetime import datetime,timezone
        decision=record.get('lineage',{}).get('governance_decision',{})
        chain=record.get('lineage',{}).get('canonical_v2',{})
        if record.get('approval_record',{}).get('resolution')=='COEXIST':return False
        # Pre-v2 records remain inspectable but cannot influence context.
        if (record.get('integrity_metadata',{}).get('canonical_policy')!='2.2' or
            decision.get('decision')!='APPROVED' or decision.get('policy_basis')!=POLICY or
            decision.get('operator_id')!=record['scope']['operator_id'] or decision.get('scope')!=record['scope'] or
            chain.get('outcome_analysis',{}).get('status')!='COMPLETE'):
            return False
        if not allow_inactive and (record['status']!='APPROVED' or record['revocation_state']!='ACTIVE'):return False
        deadline=record.get('lineage',{}).get('revalidate_by')
        if not deadline:return False
        return datetime.fromisoformat(deadline)>datetime.now(timezone.utc)

    def revalidate(self,operator,identity,expected_hash,trigger,outcome,new_candidate_id=None,initiator='OPERATOR'):
        triggers={'NEW_EVIDENCE','CONTRADICTORY_EVIDENCE','ARCHITECTURE_CHANGE','OPERATOR_PREFERENCE_CHANGE',
                  'GOVERNANCE_POLICY_CHANGE','RP_INVALIDATION','REPEATED_EXECUTION_FAILURE','PERIODIC_REVIEW'}
        if trigger not in triggers or outcome not in {'MAINTAIN','UPDATE','SUSPEND','DEPRECATE','ARCHIVE','REMOVE'}:
            raise ValueError('Unknown revalidation trigger/outcome')
        from data_governance.learning_governance import decide,GovernanceDecision,POLICY
        from learning.canonical import confidence
        with self.store.transaction(operator) as (state,_,append):
            item=deepcopy(state[identity])
            if digest(item)!=expected_hash:raise ValueError('Stale revalidation')
            stamp=now();candidate=state.get(new_candidate_id)
            if outcome in {'MAINTAIN','UPDATE'}:
                if not candidate or candidate['scope']!=item['scope']:raise PermissionError('New governed candidate required')
                if outcome=='MAINTAIN' and (candidate['claim'].get('rp_claim') or {}).get('claim_text')!=(item['lesson'].get('rp_claim') or {}).get('claim_text'):
                    raise PermissionError('Maintaining a lesson requires evidence for the same claim')
                decision=decide(candidate,operator,True).to_dict()
                if decision['decision']!='APPROVED':raise PermissionError('Incomplete revalidation evidence')
                if candidate['source_rp_decision_id']==item['lineage']['canonical_v2']['reality_validation']['decision_id']:
                    raise PermissionError('Repetition does not renew evidence')
                decision['subject_id']=identity
                decision['lineage']['new_candidate_id']=new_candidate_id
                item['evidence']=list(dict.fromkeys(item['evidence']+candidate['evidence_refs']))
                previous=deepcopy(item['lineage']['canonical_v2'])
                item['lineage']['canonical_v2']=deepcopy(candidate['lineage']['canonical_v2'])
                item['lineage'].pop('dependency_graph',None)  # changed evidence needs a new completeness declaration
                item['lineage']['canonical_v2']['confidence']=confidence(
                    previous['confidence']['supporting']+candidate['lineage']['canonical_v2']['confidence']['supporting'],
                    candidate['lineage']['canonical_v2']['confidence']['contradicting'],previous['confidence']['history'])
                item['lineage']['revalidate_by']=candidate['lineage']['outcome']['rp']['authority_valid_until']
                item['lineage']['governance_decision']=decision
                if outcome=='UPDATE':item['lesson']=deepcopy(candidate['claim'])
                item.update(status='APPROVED',revocation_state='ACTIVE')
            else:
                status={'SUSPEND':'SUSPENDED','DEPRECATE':'DEPRECATED','ARCHIVE':'ARCHIVED','REMOVE':'REMOVED'}[outcome]
                item.update(status=status,revocation_state=status)
                if (candidate and candidate['scope']==item['scope'] and
                    candidate.get('lineage',{}).get('canonical_v2',{}).get('rp_complete') and
                    candidate['claim'].get('rp_state')=='DISCONFIRMED' and
                    (candidate['claim'].get('rp_claim') or {}).get('claim_text')==(item['lesson'].get('rp_claim') or {}).get('claim_text')):
                    old_support=item['lineage']['canonical_v2']['confidence']
                    item['lineage']['canonical_v2']['confidence']=confidence(old_support['supporting'],
                        old_support['contradicting']+[candidate['source_rp_decision_id']],old_support['history'])
                decision=GovernanceDecision('governance:'+digest([identity,trigger,outcome,stamp]),identity,operator,'APPROVED',
                    item['scope'],POLICY,item['evidence'],item.get('lineage',{}).get('canonical_v2',{}).get('outcome_analysis',{}).get('prerequisite_refs',{}),stamp,
                    {'action':outcome,'trigger':trigger,'subject_hash':expected_hash,'initiator':initiator}).to_dict()
            event={'trigger':trigger,'outcome':outcome,'timestamp':stamp,'new_candidate_id':new_candidate_id,'governance_decision':decision,'initiator':initiator}
            item['lineage']['governance_decision']=decision
            item['lineage'].setdefault('revalidation_history',[]).append(event)
            item['updated_at']=stamp
            append(decision['decision_id'],'governance',GovernanceDecision(**decision).issued());append(identity,'record',item)
            return item

    def expire_due(self,operator):
        """Lazy periodic review before runtime use; expiry never renews evidence."""
        from datetime import datetime,timezone
        with self.store.transaction(operator) as (state,_,__):
            records=[deepcopy(v) for v in state.values() if v.get('status')=='APPROVED' and 'learning_id' in v]
        changed=[]
        for record in records:
            deadline=record.get('lineage',{}).get('revalidate_by')
            if not deadline:continue  # Historical pre-v2 records are already quarantined.
            if datetime.fromisoformat(deadline)<=datetime.now(timezone.utc):
                changed.append(self.revalidate(operator,record['learning_id'],digest(record),'PERIODIC_REVIEW','SUSPEND',initiator='POLICY'))
        return changed

    def consume_new_evidence(self,candidate):
        chain=candidate.get('lineage',{}).get('canonical_v2',{})
        if not chain.get('rp_complete') or candidate['claim'].get('rp_state')!='DISCONFIRMED':return []
        owner=candidate['scope']['operator_id'];changed=[]
        for record in self.retrieve(owner,candidate['scope']):
            if (record['lesson'].get('rp_claim') or {}).get('claim_text')==(candidate['claim'].get('rp_claim') or {}).get('claim_text'):
                changed.append(self.revalidate(owner,record['learning_id'],digest(record),'RP_INVALIDATION','SUSPEND',candidate['candidate_id'],initiator='POLICY'))
        return changed
