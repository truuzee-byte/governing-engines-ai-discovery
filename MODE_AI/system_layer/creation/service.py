"""Operator-owned capability declarations and externally evidenced reality.

Persistence is transactional. No method takes an unverified reality-state label.
Construction is delegated to the existing normal BuildRuntime.
"""
from copy import deepcopy
from dataclasses import replace
from uuid import uuid4
from ..contracts import Capability, QuickSpecification, SystemIdentity, STAGES, authorize, digest, now
from ..state.store import SystemStore, _IDENTITY_WRITER
from ..state.operational_admission import issue as operational_admission
from ..chain import analyze, build_obligations


class SystemLayer:
    def inspect_capabilities(self, operator_id, scope):
        from ..capability_inspection import inspect_capabilities
        return inspect_capabilities(self.store.path,self.owner,operator_id,scope)

    def record_capability_evidence(self, value, expected_receipt, approval):
        from ..capability_inspection import record_evidence
        return record_evidence(self,value,expected_receipt,approval)

    def __init__(self, path, runtime, reality_client=None):
        self.store = SystemStore(path)
        self.runtime = runtime
        self.reality_client = reality_client

    @property
    def owner(self):
        return self.runtime.context.identity.operator_id

    def admit_material(self, proposal, expected_receipt, approval, rp_request=None):
        """Exact RP-bound object admission using the existing System receipt store.

        Rejected/pending proposals are auditable and never replace a prior head.
        This is an acceptance boundary, not a second reality decision engine.
        """
        from data_governance.material_admission import MaterialProposal, MaterialAdmissionGate
        from datetime import datetime, timezone
        if type(proposal) is not dict:
            raise ValueError('Exact material proposal required')
        proposed = MaterialProposal(**deepcopy(proposal))
        if proposed.scope.get('operator_id') != self.owner:
            raise PermissionError('Material object owner mismatch')
        authorize(self.owner, 'MATERIAL_ADMISSION',
            {'proposal': proposal, 'expected_receipt': expected_receipt}, approval)
        subject = 'material:' + proposed.object_id
        client = getattr(self.runtime, 'reality_acceptance_client', None)
        with self.store.transaction(self.owner) as (current, _, append):
            before = current.get(subject)
            head = before['receipt_id'] if before else None
            state = before['value']['state'] if before else None
            if head != expected_receipt or state != proposed.prior_state:
                raise PermissionError('Stale material object prior state')
            result = MaterialAdmissionGate(client).evaluate(proposed, rp_request)
            external = result['external_acceptance']
            if result['accepted']:
                deadline = datetime.fromisoformat(external['authority_valid_until'])
                if deadline < datetime.now(timezone.utc):
                    result.update(accepted=False, decision='HOLD_PENDING_VALIDATION',
                        reason_code='RP_EXPIRED_BEFORE_APPLY', resulting_state=deepcopy(state))
                    result.pop('admission_id')
                    result['admission_id'] = 'material-admission:' + digest(result)
            refs = [r for r in (result['external_receipt_id'], head) if r]
            audit = append('admission:' + result['admission_id'], result,
                'MATERIAL_ADMISSION_DECISION', approval, refs)
            if result['accepted']:
                record = append(subject, {'object_type': proposed.object_type,
                    'state': deepcopy(proposed.candidate_state), 'scope': proposed.scope,
                    'epistemic_state': proposed.epistemic_state, 'rp_state': result['rp_state'],
                    'admission_receipt': audit['receipt_id']}, 'MATERIAL_STATE_APPLIED',
                    approval, [audit['receipt_id'], *refs], material_decision=result)
            else:
                record = before
        if external is not None:
            self.runtime.understanding_engine.receive_rp_outcome(external)
        observer = getattr(self.runtime, '_observe_runtime_event', None)
        if observer is not None:
            observer('material_admission', {'admission_receipt': audit['receipt_id'],
                'claim_id': proposed.claim_id, 'object_id': proposed.object_id,
                'decision': result['decision'], 'rp_state': result['rp_state'],
                'rp_receipt': result['external_receipt_id'],
                'rp_chain': result['external_chain_id'], 'binding_hash': result['binding_hash']})
        return {'admission': audit, 'object': record, 'applied': result['accepted']}

    def require_internal_execution(self):
        """Use current governed identity at each execution boundary, not request labels."""
        record = self.store.get(self.owner, 'identity')
        if record is None:
            raise PermissionError('Governed runtime identity required for execution')
        identity = SystemIdentity(**record['value'])
        if identity.operational_boundaries['runtime_profile'] != 'INTERNAL':
            raise PermissionError('Only internal runtime execution is permitted')
        self._verify_method(identity.to_dict())

    def identity(self, identity, approval):
        identity = SystemIdentity(**identity)
        authorize(self.owner, 'SYSTEM_IDENTITY', identity.to_dict(), approval)
        self._verify_method(identity.to_dict())
        with self.store.transaction(self.owner) as (current, _, append):
            if 'identity' in current:
                raise PermissionError('Protected identity cannot be changed through Capability Update')
            return append('identity', identity.to_dict(), 'SYSTEM_IDENTITY', approval,
                          identity_admission=_IDENTITY_WRITER)

    def _verify_method(self, identity):
        from pathlib import Path
        import hashlib
        method = identity['construction_method']
        path = Path(method['reference'])
        if not path.is_absolute() or hashlib.sha256(path.read_bytes()).hexdigest() != method['sha256']:
            raise PermissionError('Protected construction method integrity check failed')

    def declare(self, capability, quick_specification, approval):
        cap = Capability(**capability)
        quick = QuickSpecification(**quick_specification)
        if cap.operator_id != self.owner or quick.requested_capability != cap.name or quick.purpose != cap.purpose:
            raise PermissionError('Capability/Quick Spec ownership or meaning mismatch')
        if quick.deployment_target != cap.scope['deployment']:
            raise PermissionError('Quick Spec deployment mismatch')
        if any(getattr(cap, k) != 'UNCONFIRMED' for k in
                ('implementation_state', 'integration_state', 'validation_state', 'operational_state')) or cap.rp_state != 'PENDING_VALIDATION':
            raise PermissionError('Declarations cannot inject reality states')
        value = {'capability': cap.to_dict(), 'quick_specification': quick.to_dict()}
        authorize(self.owner, 'DECLARE', value, approval)
        with self.store.transaction(self.owner) as (current, _, append):
            if 'identity' not in current:
                raise PermissionError('Approved System Identity required')
            prior = current.get(cap.capability_id)
            if prior and prior['value']['control'] in {'EXECUTING', 'ROLLBACK_IN_PROGRESS'}:
                raise PermissionError('Capability mutation is already in progress')
            if prior and cap.version != prior['value']['capability']['version'] + 1:
                raise ValueError('Capability version must extend history')
            if prior and cap.supersedes != prior['receipt_id']:
                raise ValueError('Explicit supersession receipt required')
            value['stages'] = [{'stage': s, 'status': 'COMPLETE', 'reference': digest(value)} for s in STAGES[:3]]
            value['control'] = 'ACTIVE'
            value['reality'] = None
            value['target_state'] = cap.declared_state if cap.declared_state in {'DISABLED', 'DEPRECATED', 'SUPERSEDED'} else 'OPERATIONAL'
            value['prior_supported_state'] = (deepcopy(prior['value']) if prior and
                prior['value']['capability']['validation_state'] == 'VALIDATED' and
                prior['value']['capability']['rp_state'] == 'CONFIRMED' and
                len(prior['value']['stages']) == len(STAGES) else None)
            return append(cap.capability_id, value, 'DECLARE', approval)

    def _record(self, identity):
        record = self.store.get(self.owner, identity)
        if not record or 'capability' not in record['value']:
            raise ValueError('Unknown capability')
        if record['value'].get('control') == 'EVIDENCE_ONLY':
            raise PermissionError('Evidence inventory is not an admitted operational workflow')
        return record

    def inventory(self, request, approval):
        """Record explicitly authorized inspection without promoting capability state."""
        from ..audit.structural_inventory_auditor import inspect
        required = {'system_id', 'system_version', 'root', 'files', 'purpose'}
        if type(request) is not dict or set(request) != required:
            raise ValueError('Exact structural inventory request required')
        authorize(self.owner, 'STRUCTURAL_INVENTORY', request, approval)
        subject = 'inventory:' + request['system_id']
        before = self.store.get(self.owner, subject)
        value = inspect(request['root'], request['files'], system_id=request['system_id'],
            system_version=request['system_version'],
            scope={'operator_id': self.owner, 'purpose': request['purpose']},
            version=before['value']['version'] + 1 if before else 1,
            supersedes=before['receipt_id'] if before else None)
        with self.store.transaction(self.owner) as (current, _, append):
            if current.get(subject) != before:
                raise PermissionError('Inventory changed during inspection')
            return append(subject, value, 'STRUCTURAL_INVENTORY', approval,
                          [before['receipt_id']] if before else [], operational_admission=operational_admission(
                              self.owner,subject,'STRUCTURAL_INVENTORY',request,value,approval))

    def discover_sources(self,request,approval):
        from ..audit.source_discovery import discover
        if type(request) is not dict or set(request)!={'system_id','root','extensions','limit','purpose'}:
            raise ValueError('Exact source discovery request required')
        if any(type(request[k]) is not str or not request[k].strip() for k in ('system_id','purpose')):
            raise ValueError('Explicit system and discovery purpose required')
        authorize(self.owner,'STRUCTURAL_SOURCE_DISCOVERY',request,approval)
        value=discover(request['root'],request['extensions'],request['limit'])
        value.update(system_id=request['system_id'],purpose=request['purpose'],operator_id=self.owner)
        value['discovery_hash']=digest({k:v for k,v in value.items() if k!='discovery_hash'})
        subject='source-discovery:'+request['system_id']
        with self.store.transaction(self.owner) as (current,_,append):
            prior=current.get(subject)
            return append(subject,value,'STRUCTURAL_SOURCE_DISCOVERY',approval,[prior['receipt_id']] if prior else [],
                operational_admission=operational_admission(self.owner,subject,'STRUCTURAL_SOURCE_DISCOVERY',request,value,approval))

    def operational_understanding(self, model, approval):
        """Preserve a proposed operational model; no state or RP promotion."""
        from ..audit.operational_understanding_validator import evaluate
        authorize(self.owner, 'OPERATIONAL_UNDERSTANDING', model, approval)
        identity = model['definition']['capability_id']
        inventory = self.store.get(self.owner, 'inventory:' + identity)
        if inventory is None:
            raise ValueError('Authorized structural inventory required before operational model admission')
        assessment = evaluate(model, inventory['value'],
                              current_system_version=inventory['value']['system_version'])
        subject = 'operational-understanding:' + identity
        with self.store.transaction(self.owner) as (current, _, append):
            if current.get('inventory:' + identity) != inventory:
                raise PermissionError('Structural inventory changed during model assessment')
            prior = current.get(subject)
            if model['version'] != (prior['value']['model']['version'] + 1 if prior else 1):
                raise ValueError('Operational model must extend current version')
            if model['supersedes'] != (prior['receipt_id'] if prior else None):
                raise ValueError('Exact operational model supersession required')
            return append(subject, {'model': model, 'assessment': assessment},
                          'OPERATIONAL_UNDERSTANDING', approval, [inventory['receipt_id']] +
                          ([prior['receipt_id']] if prior else []), operational_admission=operational_admission(
                              self.owner,subject,'OPERATIONAL_UNDERSTANDING',model,{'model':model,'assessment':assessment},approval))

    def operational_sources(self,request,approval):
        from ..audit.operation_source_binding import assess
        if type(request) is not dict or set(request)!={'system_id','model_receipt','inventory_receipt','bindings'}:
            raise ValueError('Exact operational source binding request required')
        authorize(self.owner,'OPERATIONAL_SOURCES',request,approval)
        identity=request['system_id']
        model=self.store.get(self.owner,'operational-understanding:'+identity)
        inventory=self.store.get(self.owner,'inventory:'+identity)
        if model is None or inventory is None or model['receipt_id']!=request['model_receipt'] or inventory['receipt_id']!=request['inventory_receipt']:
            raise ValueError('Current operational model and inventory required')
        result=assess(model['value']['model'],inventory['value'],request['bindings'])
        with self.store.transaction(self.owner) as (current,_,append):
            if current.get('operational-understanding:'+identity)!=model or current.get('inventory:'+identity)!=inventory:
                raise PermissionError('Operational source binding changed during assessment')
            return append('operational-sources:'+identity,result,'OPERATIONAL_SOURCES',approval,[model['receipt_id'],inventory['receipt_id']],
                operational_admission=operational_admission(self.owner,'operational-sources:'+identity,'OPERATIONAL_SOURCES',request,result,approval))

    def _dependencies_current(self, capability):
        for identity in capability.dependencies:
            record = self.store.get(self.owner, identity)
            if not self._operational_current(record):
                return False
        return True

    def _operational_current(self, record):
        """Consume external proof, not an imported operational-state label."""
        from ..reality import CapabilityRealityClient
        if not record or not isinstance(self.reality_client, CapabilityRealityClient):
            return False
        try:
            item = record['value']
            cap = Capability(**item['capability'])
            result = self.reality_client.verify_recorded(cap, item['reality'])
            body = result['finding']['body']
            return (cap.operator_id == self.owner and item.get('control') == 'ACTIVE'
                and cap.operational_state == 'OPERATIONAL'
                and body['rp_state'] == 'CONFIRMED' and body['finding'] == 'OPERATIONAL')
        except Exception:
            # Missing, malformed, expired or unverifiable history is not readiness.
            return False

    def _stage(self, value, stage, reference, status='COMPLETE'):
        expected = STAGES[len(value['stages'])]
        if stage != expected or not reference or status not in {'COMPLETE', 'NOT_APPLICABLE'}:
            raise PermissionError('Stage cannot be skipped: ' + expected)
        value['stages'].append({'stage': stage, 'status': status, 'reference': reference})

    def audit(self, identity, transition):
        if self.reality_client is None:
            raise PermissionError('External capability audit is not provisioned')
        before = self._record(identity)
        cap = Capability(**before['value']['capability'])
        result = self.reality_client.audit(cap, transition, 'audit:' + uuid4().hex)
        body = result['finding']['body']
        with self.store.transaction(self.owner) as (current, _, append):
            if current[identity] != before:
                raise PermissionError('Capability changed during audit')
            value = deepcopy(before['value'])
            value['reality'] = result
            value['gap'] = body.get('gap')
            if body.get('drift'):
                value['review_state'] = body['drift']['state']
                if body['drift'].get('halt'):
                    value['control'] = 'CAPABILITY_HALT'
            elif value['control'] == 'CAPABILITY_HALT' and body['rp_state'] == 'CONFIRMED':
                value['control'] = 'PAUSE'
            value['capability']['rp_state'] = body['rp_state']
            value['capability']['last_audit_at'] = body['evaluated_at']
            value['capability']['evidence_references'].append(body['receipt_id'])
            if body['rp_state'] == 'CONFIRMED':
                field = {'IMPLEMENTED': 'implementation_state', 'INTEGRATED': 'integration_state',
                         'VALIDATED': 'validation_state', 'NOT_IMPLEMENTED': 'implementation_state'}.get(body['finding'])
                if field:
                    value['capability'][field] = body['finding']
            # Operational promotion occurs only through registration below.
            if body['finding'] in {'DEGRADED', 'FAILED', 'NOT_IMPLEMENTED', 'UNCONFIRMED'}:
                value['capability']['operational_state'] = body['finding']
            if len(value['stages']) == 3:
                self._stage(value, 'RP_AUDIT', body['receipt_id'])
            receipt = append(identity, value, 'RP_AUDIT', {'authority': 'EXTERNAL_RP'}, [body['receipt_id']])
        self.runtime.understanding_engine.receive_rp_outcome(result['acceptance'])
        self._observe(receipt)
        return receipt

    def control(self, identity, action, expected_receipt, approval):
        if action not in {'PAUSE', 'RESUME', 'CANCEL', 'REJECT'}:
            raise ValueError('Unsupported operator control')
        body = {'capability_id': identity, 'receipt_id': expected_receipt, 'action': action}
        authorize(self.owner, action, body, approval)
        with self.store.transaction(self.owner) as (current, _, append):
            previous = current[identity]
            if previous['receipt_id'] != expected_receipt:
                raise PermissionError('Stale operator control')
            if action == 'RESUME' and previous['value']['control'] in {'CAPABILITY_HALT', 'ROLLBACK_IN_PROGRESS'}:
                raise PermissionError('External revalidation or rollback completion required')
            value = deepcopy(previous['value'])
            value['control'] = 'ACTIVE' if action == 'RESUME' else action
            return append(identity, value, action, approval)

    def prepare(self, identity, envelope, governing_specs, reuse_search, approval):
        """Bind a complete execution request without inventing missing requirements."""
        before = self._record(identity)
        value = deepcopy(before['value'])
        cap = Capability(**value['capability'])
        self.require_internal_execution()
        if value['control'] != 'ACTIVE':
            raise PermissionError('Only active internal capability construction is permitted')
        if len(value['stages']) != 4:
            raise PermissionError('External RP audit must precede construction planning')
        payload = {'capability_receipt': before['receipt_id'], 'envelope': envelope,
                   'governing_specs': governing_specs, 'reuse_search': reuse_search}
        authorize(self.owner, 'SPECIFICATION_APPROVAL', payload, approval)
        request = envelope['request']
        if (request['system_purpose'] != cap.purpose or request['runtime_target'] != cap.scope['deployment']
                or envelope['authorization']['operator_id'] != self.owner):
            raise PermissionError('Execution specification changes capability meaning or deployment')
        if not governing_specs or any(not s.get('reference') or not s.get('sha256') for s in governing_specs):
            raise ValueError('Versioned governing specification chain required')
        with self.store.transaction(self.owner) as (current, _, __):
            candidates = [r['value']['capability'] for r in current.values() if 'capability' in r['value']]
        matches = [c['capability_id'] for c in candidates if c['capability_id'] != identity and
                   (c['purpose'] == cap.purpose or c['name'] == cap.name)]
        if matches:
            raise PermissionError('Existing capability requires governed reuse/conflict resolution: ' + str(matches))
        required_searches = {'aliases', 'unintegrated', 'builder_library', 'other_runtimes', 'approved_modules', 'conflicts'}
        if set(reuse_search) != required_searches or any(type(v) is not dict or
                v.get('status') not in {'SEARCHED', 'NOT_APPLICABLE'} or not v.get('reference')
                or not v.get('reason') for v in reuse_search.values()):
            raise PermissionError('Every governed reuse search needs a result or explicit non-applicability')
        if any(v.get('matches') for v in reuse_search.values()):
            raise PermissionError('Reuse matches require an approved reuse specification')
        self._stage(value, 'EXISTING_CAPABILITY_SEARCH', {'registry_matches': matches, 'sources': reuse_search})
        # External finding is retained; a local gap is not independently confirmed.
        self._stage(value, 'GAP', value['reality']['finding']['body']['receipt_id'])
        structure = analyze(cap)
        if structure['unresolved']:
            raise PermissionError('Structural conflict: ' + '; '.join(structure['unresolved']))
        for stage in ('CHAIN_RECOGNITION', 'CHAIN_RELATIONSHIP_MAPPING', 'MECHANISM_DERIVATION'):
            self._stage(value, stage, digest(structure))
        from datetime import datetime, timezone
        def dependency_current(identity):
            return self._operational_current(current.get(identity))
        unresolved_dependencies = [d for d in cap.dependencies if not dependency_current(d)]
        if unresolved_dependencies:
            raise PermissionError('Dependencies not operational: ' + str(unresolved_dependencies))
        self._stage(value, 'DEPENDENCY_ANALYSIS', {'dependencies': cap.dependencies})
        if not cap.required_outputs or not cap.required_evidence or not cap.validation_requirements or not cap.authority_requirements:
            raise ValueError('Specification sufficiency unresolved')
        authority_reference = self.store.get(self.owner, 'identity')['value']['construction_method']['authority_reference']
        if set(cap.authority_requirements) - {authority_reference}:
            raise PermissionError('Unsupported capability authority obligation; explicit adapter required')
        if set(cap.approval_requirements) - {'SPECIFICATION_APPROVAL', 'EXECUTION_APPROVAL', 'OPERATOR_ACCEPTANCE'}:
            raise PermissionError('Unsupported capability approval obligation')
        if not set(cap.required_outputs) <= set(request['artifact_structure']['required_outputs']):
            raise ValueError('Required capability outputs omitted')
        if not set(cap.required_evidence) <= set(request['evidence']['requirements']):
            raise ValueError('Required capability evidence omitted')
        if not set(cap.validation_requirements) <= set(request['validation']['requirements']):
            raise ValueError('Required capability validation omitted')
        if not set(cap.invariants) <= set(request['governance_constraints']):
            raise ValueError('Capability invariants/prohibitions omitted')
        for mechanism in cap.mechanisms:
            if not set(mechanism['authority_requirement']) <= {authority_reference}:
                raise PermissionError('Required mechanism authority is unsupported')
            if not set(mechanism['evidence_required']) <= set(request['evidence']['requirements']):
                raise PermissionError('Required mechanism evidence omitted')
            if not set(mechanism['invariant_protected']) <= set(request['governance_constraints'] + request['completion']['requirements']):
                raise PermissionError('Required mechanism invariant omitted')
            predicates = mechanism.get('completion_requirements')
            if not predicates or not set(predicates) <= set(request['completion']['requirements']):
                raise PermissionError('Required mechanism lacks executable completion obligations')
        if not set(build_obligations(cap)) <= set(request['evidence']['requirements']):
            raise PermissionError('Canonical execution specification must retain complete chain/mechanism obligations')
        self._stage(value, 'SPECIFICATION_SUFFICIENCY', digest(payload))
        if request.get('clarification_required') is not False:
            raise PermissionError('Clarification unresolved')
        self._stage(value, 'CLARIFICATION', 'Complete structured operator specification', 'NOT_APPLICABLE')
        self._stage(value, 'CREATION_COMPONENT', digest(payload))
        self._stage(value, 'GOVERNING_SPEC_CHAIN', governing_specs)
        self._stage(value, 'OPERATOR_APPROVAL', approval)
        self._stage(value, 'TARGET_EXECUTION_SPEC', digest(envelope))
        value.update(envelope=deepcopy(envelope), structural_analysis=structure, governing_specs=governing_specs)
        value['construction_state'] = 'SPECIFICATION_APPROVED'
        with self.store.transaction(self.owner) as (current, _, append):
            if current[identity] != before:
                raise PermissionError('Capability changed during planning')
            return append(identity, value, 'SPECIFICATION_APPROVAL', approval)

    def construct(self, identity, expected_receipt, approval):
        self.require_internal_execution()
        before = self._record(identity)
        value = deepcopy(before['value'])
        if before['receipt_id'] != expected_receipt or value['control'] != 'ACTIVE':
            raise PermissionError('Stale or inactive construction approval')
        payload = {'capability_receipt': expected_receipt, 'envelope_hash': digest(value['envelope'])}
        authorize(self.owner, 'EXECUTION_APPROVAL', payload, approval)
        if value['envelope']['request']['execution'].get('approved_commands'):
            raise PermissionError('No rollback adapter registered for command-driven runtime mutation')
        from pathlib import Path
        import base64
        from builder.core.execution_contract import contained
        root = Path(value['envelope']['request']['execution']['repository_target'])
        if not root.is_absolute():
            raise PermissionError('Absolute construction target required')
        root = root.resolve()
        identity_record = self.store.get(self.owner, 'identity')['value']
        self._verify_method(identity_record)
        boundaries = identity_record['operational_boundaries']
        mutable_roots = boundaries.get('mutable_roots', [])
        if not mutable_roots or not any(root.is_relative_to(Path(p).resolve()) for p in mutable_roots):
            raise PermissionError('Construction outside approved mutable roots')
        protected = [Path(p).resolve() for p in boundaries.get('protected_paths', [])]
        protected.append(Path(identity_record['construction_method']['reference']).resolve())
        snapshot = {}
        for path in value['envelope']['request']['artifact_structure']['files']:
            target = contained(root, path)
            if any(target == p or target.is_relative_to(p) for p in protected):
                raise PermissionError('Protected governance surface')
            if target.exists() and (path not in value['envelope']['request']['artifact_structure']['existing_files'] or
                    path not in value['envelope']['request']['execution']['authorized_read_scope']):
                raise PermissionError('Rollback capture requires explicit MODIFY read custody')
            snapshot[path] = base64.b64encode(target.read_bytes()).decode() if target.is_file() else None
        value['rollback_snapshot'] = {'root': str(root), 'files': snapshot, 'prior_reality': value['reality']}
        self._stage(value, 'EXECUTION_APPROVAL', approval)
        # Durable reservation prevents two workers from executing this approval.
        self._stage(value, 'BUILDER', digest(value['envelope']))
        value['control'] = 'EXECUTING'
        value['construction_state'] = 'IN_DEVELOPMENT'
        with self.store.transaction(self.owner) as (current, _, append):
            if current[identity] != before:
                raise PermissionError('Construction already claimed')
            reservation = append(identity, value, 'CONSTRUCTION_CLAIM', approval)
        try:
            def guard():
                if self._record(identity)['value']['control'] != 'EXECUTING':
                    raise PermissionError('Capability construction paused, cancelled or changed')
                if not self._dependencies_current(Capability(**value['capability'])):
                    raise PermissionError('Capability dependency is no longer current')
            outcome = self.runtime.build_runtime.execute(deepcopy(value['envelope']), capability_guard=guard)
            self.runtime._capture_build_outcome(outcome)
        except Exception as exc:
            outcome = {'state': 'FAILED', 'error': str(exc)}
        with self.store.transaction(self.owner) as (current, _, append):
            latest = current[identity]
            value = deepcopy(latest['value'])
            value['build_outcome'] = outcome
            value['rollback_snapshot']['after'] = {path: __import__('hashlib').sha256(
                contained(root, path).read_bytes()).hexdigest() if contained(root, path).is_file() else None
                for path in snapshot}
            # Pause/cancel remains effective if issued during execution.
            if value['control'] == 'EXECUTING': value['control'] = 'ACTIVE'
            if outcome.get('build', {}).get('validation_status') == 'PASS':
                value['construction_state'] = 'VALIDATION_PENDING'
                self._stage(value, 'CONSTRUCTION', outcome['build']['receipt_path'])
            elif value['control'] == 'ACTIVE':
                value['control'] = 'CONSTRUCTION_BLOCKED'
            receipt = append(identity, value, 'CONSTRUCTION_RESULT', approval,
                             outcome.get('observation_ids', []))
        self._observe(receipt)
        return receipt

    def validate(self, identity, requests):
        """Each dimension is an independently scoped external RP evaluation."""
        from ..validation import DIMENSIONS, require_dimensions
        required = DIMENSIONS
        if set(requests) != required or self.reality_client is None:
            raise PermissionError('Complete external validation dimensions required')
        before = self._record(identity)
        value = deepcopy(before['value'])
        if len(value['stages']) == len(STAGES):
            value['stages'] = value['stages'][:STAGES.index('INTEGRATION')]
        if value['control'] not in {'ACTIVE', 'REVALIDATION_REQUIRED'} or len(value['stages']) != STAGES.index('INTEGRATION'):
            raise PermissionError('Successful construction required before integration validation')
        cap = Capability(**value['capability'])
        require_dimensions(requests, value)
        validations = {}
        for dimension in sorted(required):
            request = requests[dimension]
            validations[dimension] = self.reality_client.audit(cap, request, 'audit:' + uuid4().hex)
        value['validations'] = validations
        complete = all(v['finding']['body']['rp_state'] == 'CONFIRMED' for v in validations.values())
        complete = complete and validations['operational']['finding']['body']['finding'] == value['target_state']
        halted = any((v['finding']['body'].get('drift') or {}).get('halt') is True for v in validations.values())
        if halted:
            value['control'] = 'CAPABILITY_HALT'
            complete = False
        if complete:
            self._stage(value, 'INTEGRATION', validations['integration']['finding']['body']['receipt_id'])
            self._stage(value, 'TESTING', [validations[d]['finding']['body']['receipt_id'] for d in ('dependency', 'functional', 'runtime')])
            self._stage(value, 'RP_VALIDATION', validations['operational']['finding']['body']['receipt_id'])
            self._stage(value, 'GOVERNANCE_VALIDATION', validations['governance']['finding']['body']['receipt_id'])
        value['validation_complete'] = complete
        value['construction_state'] = 'VALIDATED' if complete else 'VALIDATION_PENDING'
        if not complete:
            operational = validations['operational']['finding']['body']
            value['capability']['rp_state'] = operational['rp_state']
            value['capability']['operational_state'] = (operational['finding'] if operational['finding'] in
                {'DEGRADED', 'FAILED', 'NOT_IMPLEMENTED', 'UNCONFIRMED'} else 'UNCONFIRMED')
        if complete and value['control'] == 'REVALIDATION_REQUIRED':
            value['control'] = 'ACTIVE'
        with self.store.transaction(self.owner) as (current, _, append):
            if current[identity] != before:
                raise PermissionError('Capability changed during validation')
            receipt = append(identity, value, 'VALIDATION', {'authority': 'EXTERNAL_RP'},
                [v['finding']['body']['receipt_id'] for v in validations.values()])
        for validation in validations.values():
            self.runtime.understanding_engine.receive_rp_outcome(validation['acceptance'])
        self._observe(receipt)
        return receipt

    def accept(self, identity, expected_receipt, approval):
        from datetime import datetime, timezone
        from ..reality import CapabilityRealityClient
        from ..validation import require_dimensions
        with self.store.transaction(self.owner) as (current, _, append):
            before = current[identity]
            if before['receipt_id'] != expected_receipt:
                raise PermissionError('Stale operator acceptance')
            value = deepcopy(before['value'])
            authorize(self.owner, 'OPERATOR_ACCEPTANCE', {'capability_receipt': expected_receipt}, approval)
            if value['control'] != 'ACTIVE' or not value.get('validation_complete'):
                raise PermissionError('Capability lacks completed governed validation')
            if not isinstance(self.reality_client, CapabilityRealityClient):
                raise PermissionError('External capability verification is not provisioned')
            cap = Capability(**value['capability'])
            expected_target = cap.declared_state if cap.declared_state in {'DISABLED', 'DEPRECATED', 'SUPERSEDED'} else 'OPERATIONAL'
            if (value['target_state'] != expected_target or
                    value['validations']['operational']['finding']['body']['finding'] != expected_target):
                raise PermissionError('Operational finding differs from declared target')
            require_dimensions({d: v['acceptance']['request'] for d, v in value['validations'].items()}, value)
            for validation in value['validations'].values():
                verified = self.reality_client.verify_recorded(Capability(**value['capability']), validation)
                body = verified['finding']['body']
                if body['rp_state'] != 'CONFIRMED':
                    raise PermissionError('Recorded validation does not confirm capability')
                deadline = min(datetime.fromisoformat(body['valid_until']),
                    datetime.fromisoformat(validation['acceptance']['authority_valid_until']))
                if deadline < datetime.now(timezone.utc):
                    raise PermissionError('Validation expired before acceptance')
            from pathlib import Path
            import hashlib
            from builder.core.execution_contract import contained
            snapshot = value['rollback_snapshot']
            for path, expected in snapshot['after'].items():
                target = contained(Path(snapshot['root']), path)
                if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != expected:
                    raise PermissionError('Artifact changed after validation')
            self._stage(value, 'OPERATOR_ACCEPTANCE', approval)
            self._stage(value, 'CAPABILITY_REGISTRATION', expected_receipt)
            self._stage(value, 'SYSTEM_LAYER_STATE_UPDATE', expected_receipt)
            self._stage(value, 'OPERATIONAL', {
                'receipt': value['validations']['operational']['finding']['body']['receipt_id'],
                'operator_target': value['target_state']},
                'COMPLETE' if value['target_state'] == 'OPERATIONAL' else 'NOT_APPLICABLE')
            value['capability'].update(implementation_state='IMPLEMENTED', integration_state='INTEGRATED',
                validation_state='VALIDATED', operational_state=value['target_state'], rp_state='CONFIRMED',
                last_validation_at=value['validations']['operational']['finding']['body']['evaluated_at'])
            value['reality'] = value['validations']['operational']
            value['construction_state'] = value['target_state']
            value['gap'] = value['reality']['finding']['body'].get('gap')
            value['review_state'] = None if not value['gap'] else 'SYSTEM_LAYER_REVIEW_REQUIRED'
            receipt = append(identity, value, 'CAPABILITY_REGISTRATION', approval, [expected_receipt])
        self._observe(receipt)
        return receipt

    def rollback(self, identity, expected_receipt, approval):
        """Restore approved bytes; restored operational claims require fresh RP."""
        from pathlib import Path
        import base64
        import hashlib
        from builder.core.execution_contract import contained
        body = {'capability_receipt': expected_receipt}
        authorize(self.owner, 'ROLLBACK', body, approval)
        with self.store.transaction(self.owner) as (current, _, append):
            before = current[identity]
            if before['receipt_id'] != expected_receipt or before['value']['control'] == 'EXECUTING':
                raise PermissionError('Stale or executing rollback')
            value = deepcopy(before['value'])
            snapshot = value['rollback_snapshot']
            root = Path(snapshot['root'])
            for path, expected in snapshot['after'].items():
                target = contained(root, path)
                observed = hashlib.sha256(target.read_bytes()).hexdigest() if target.is_file() else None
                if observed != expected:
                    raise PermissionError('Rollback target changed; operator review required')
            value['control'] = 'ROLLBACK_IN_PROGRESS'
            reservation = append(identity, value, 'ROLLBACK_BEGIN', approval)
        try:
            for path, contents in snapshot['files'].items():
                target = contained(root, path)
                if contents is None:
                    if target.exists(): target.unlink()
                else:
                    target.write_bytes(base64.b64decode(contents, validate=True))
            value['control'] = 'REVALIDATION_REQUIRED'
            value['capability'].update(operational_state='UNCONFIRMED', rp_state='PENDING_VALIDATION')
            prior = value.get('prior_supported_state')
            if prior:
                restored_capability = deepcopy(prior['capability'])
                restored_capability.update(version=value['capability']['version'] + 1,
                    supersedes=expected_receipt, operational_state='UNCONFIRMED', rp_state='PENDING_VALIDATION')
                value['capability'] = restored_capability
                value['target_state'] = prior['target_state']
                value['build_outcome'] = deepcopy(prior['build_outcome'])
                value['envelope'] = deepcopy(prior['envelope'])
                value['stages'] = deepcopy(prior['stages'][:STAGES.index('INTEGRATION')])
                value['restored_history_reference'] = expected_receipt
                value['rollback_snapshot']['after'] = deepcopy(prior['rollback_snapshot']['after'])
                value['validation_complete'] = False
                value.pop('validations', None)
        except Exception:
            # Durable ROLLBACK_BEGIN remains visible and cannot claim completion.
            raise
        with self.store.transaction(self.owner) as (current, __, append):
            if current[identity]['receipt_id'] != reservation['receipt_id']:
                raise PermissionError('Operator state changed during rollback; review required')
            receipt = append(identity, value, 'ROLLBACK_RESTORED', approval, [expected_receipt])
        self._observe(receipt)
        return receipt

    def learning_change(self, identity, event):
        """Use existing governed event semantics; never fabricate its approval."""
        from learning.runtime import command
        import json
        record = self._record(identity)
        purpose = record['value']['capability']['purpose']
        entities = {item['id'] for item in event['changed_entities'] if item.get('type') == 'capability'}
        if (record['receipt_id'] not in event['implementation_refs']
                or event['scope'].get('capability') != purpose
                or not {identity, purpose}.issubset(entities)):
            raise PermissionError('ArchitectureChangeEvent must identify this accepted capability receipt')
        if record['action'] not in {'CAPABILITY_REGISTRATION', 'ROLLBACK_RESTORED'}:
            raise PermissionError('No accepted architecture change')
        return command(self.runtime, '/learning architecture_change ' + json.dumps(event))

    def admit_library(self, identity, descriptor, approval):
        required = {'identity', 'inputs', 'outputs', 'supported_parameters', 'execution_contract',
            'dependencies', 'compatibility', 'validation', 'failure_behavior', 'limitations',
            'deployment_scope', 'mutation_boundaries', 'version', 'receipt_requirements'}
        if type(descriptor) is not dict or set(descriptor) != required:
            raise ValueError('Complete Builder Library admission contract required')
        record = self._record(identity)
        cap = record['value']['capability']
        if record['action'] != 'CAPABILITY_REGISTRATION' or cap['operational_state'] != 'OPERATIONAL':
            raise PermissionError('Operational registration required for library admission')
        if not self._operational_current(record):
            raise PermissionError('Fresh authenticated operational finding required for library admission')
        if descriptor['identity'] != identity or descriptor['deployment_scope'] != cap['scope']:
            raise PermissionError('Library admission identity/scope mismatch')
        if (descriptor['version'] != cap['version'] or not descriptor['execution_contract']
                or not descriptor['validation'] or not descriptor['failure_behavior']
                or descriptor['dependencies'] != cap['dependencies']
                or descriptor['mutation_boundaries'] != record['value']['envelope']['request']['execution']):
            raise PermissionError('Library contract does not preserve registered behavior')
        body = {'capability_receipt': record['receipt_id'], 'descriptor': descriptor}
        authorize(self.owner, 'LIBRARY_UPDATE', body, approval)
        with self.store.transaction(self.owner) as (current, _, append):
            if current[identity] != record:
                raise PermissionError('Capability changed during library admission')
            return append('library:' + identity, body, 'LIBRARY_UPDATE', approval, [record['receipt_id']])

    def recommend(self, learning_id, quick_specification):
        from learning.runtime import service
        record = service(self.runtime).store.get(self.owner, learning_id)
        if record is None or record.get('status') != 'APPROVED' or not self.runtime.learning_memory_gateway.available(self.owner, learning_id):
            raise PermissionError('Active governed Learning record required')
        quick = QuickSpecification(**quick_specification)
        value = {'learning_id': learning_id, 'source_hash': digest(record),
            'quick_specification': quick.to_dict(), 'state': 'PROPOSED', 'construction_authority': False}
        with self.store.transaction(self.owner) as (_, __, append):
            return append('recommendation:' + digest(value), value, 'LEARNING_RECOMMENDATION',
                {'authority': 'Learning', 'execution_authority': False}, [learning_id])

    def _observe(self, receipt):
        value = receipt['value']
        outcome = value.get('build_outcome', {})
        build = outcome.get('build', {})
        reality, validations = {}, []
        if receipt['action'] in {'VALIDATION', 'CAPABILITY_REGISTRATION'}:
            validations = [v['acceptance'] for v in value.get('validations', {}).values()]
            reality = value.get('validations', {}).get('operational', {}).get('acceptance', {})
        elif receipt['action'] == 'RP_AUDIT':
            reality = (value.get('reality') or {}).get('acceptance', {})
            if reality:
                validations = [reality]
        metadata = {'runtime_component': 'system_layer', 'affected_runtime_stage': receipt['action'],
            'correlation_id': receipt['subject'], 'interaction_id': outcome.get('request_id', receipt['receipt_id']),
            'runtime_session_id': getattr(self.runtime, '_observation_session_id', self.runtime.context.active_thread.thread_id),
            'observed_outcome': receipt, 'objective_id': receipt['subject'],
            'specification_id': build.get('spec_id'), 'build_id': build.get('build_id'),
            'rp_request': reality.get('request'), 'rp_result': reality.get('rp_state'), 'rp_receipt': reality.get('receipt_id'),
            'produced_receipts': [receipt['receipt_id']] + [v['receipt_id'] for v in validations],
            'validation_references': [v['decision_id'] for v in validations],
            'validation_results': [{'source': 'External Reality Primacy', 'state': v['rp_state'],
                'decision_id': v['decision_id']} for v in validations],
            'source_traces': list(outcome.get('observation_ids', [])) + receipt['references'],
            'execution_path': [s['stage'] for s in value['stages']],
            'execution_attempted': receipt['action'] == 'CONSTRUCTION_RESULT' and outcome.get('execution_attempted', False),
            'output_artifacts': build.get('files_written', []),
            'authority_source': receipt['authorization'].get('authority', 'Operator'),
            'authorization_receipts': [{'reference': receipt['receipt_id'], 'authorization': receipt['authorization']}],
            'required_evidence_fields': ['correlation_id', 'observed_outcome', 'produced_receipts']}
        record = self.runtime.runtime_observation_collector.collect(operator_id=self.owner,
            thread_id=self.runtime.context.active_thread.thread_id, runtime_state_end=receipt['action'],
            trace_reference=receipt['receipt_id'], metadata=metadata,
            runtime_error=outcome.get('state') if receipt['action'] == 'CONSTRUCTION_RESULT' and
                outcome.get('state') in {'BUILD_FAIL', 'GENERATION_FAILED', 'FAILED'} else None)
        self.runtime.context.runtime_observation = record
        from integration.interaction_learning import evaluate
        try:
            evaluate(self.runtime, record)
        except Exception as error:
            self.runtime.context.learning_error = 'System observation Learning evaluation blocked: ' + str(error)
        return record
