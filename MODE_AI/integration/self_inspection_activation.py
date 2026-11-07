"""Read-only inspection prerequisite, not a capability inventory or diagnosis."""
import json
import re
from learning.contracts import digest

SOURCE = 'SelfInspectionPrerequisite/1'
PREFIX = '\nSELF-INSPECTION PREREQUISITE (routing state, not architecture evidence):\n'
BOUNDED_RESULT = 'UNAVAILABLE: Current capability cannot be established from available inspected evidence.'


def objective_evidence_requirements(query):
    """Bound explicit own-objective diagnosis; never choose files or infer gaps.

    The current inspection router has registry and completed-interaction readers,
    not a subject-to-source resolver. Requested evidence remains an obligation,
    not a claim that a subsystem or its evidence is absent.
    """
    from runtime_observation.inspection_target import requirements
    target=requirements(query)
    if target is not None:return target
    if re.fullmatch(r'\s*Inspect Learning[.!]?\s*',query,re.I):
        return {'contract':'ObjectiveEvidenceRequirements/1','subject':'Learning',
                'required_classes':['SUBJECT_SPECIFIC_EVIDENCE'],'resolution':'UNAVAILABLE',
                'reason':'EXPLICIT_DOMAIN_INSPECTION','limits':'Learning-wide inspection only.',
                'execution_authority':False}
    if classify(query) != 'CURRENT_CAPABILITY': return None
    if not (re.search(r'\bobjective\b', query, re.I) and
            re.search(r'\binspect|self.diagnos|diagnos', query, re.I) and
            re.search(r'\bprevent|\bblock|\bmissing|\bdetermine|\bgap|\bnot established', query, re.I)):
        return None
    subject = re.search(r'\binspect\s+your\s+(?:current\s+)?([\w -]{1,64}?)\s+(?:system|subsystem)\b', query, re.I)
    requested = [('SYSTEM_CAPABILITY', r'capabilit|system layer|registry'),
                 ('IMPLEMENTATION', r'implementation|implemented|mechanism|interface'),
                 ('INTEGRATION', r'path|handoff|integration|consumer'),
                 ('RUNTIME_BEHAVIOR', r'runtime|behavior|operational'),
                 ('QUALIFICATION_VALIDATION', r'qualification|validation|validated|tests?')]
    classes = [name for name, pattern in requested if re.search(pattern, query, re.I)]
    return {'contract':'ObjectiveEvidenceRequirements/1',
            'subject':subject.group(1).strip() if subject else 'UNRESOLVED',
            'required_classes':classes or ['SUBJECT_SPECIFIC_EVIDENCE'],
            'resolution':'UNAVAILABLE',
            'reason':'NO_OBJECTIVE_TO_SOURCE_RESOLVER_IN_CURRENT_INSPECTION_ROUTE',
            'limits':'Lexical request obligations only; not semantic completeness or evidence of missing capability.',
            'execution_authority':False}


def bounded_result(query):
    requirements = objective_evidence_requirements(query)
    if requirements is None: return BOUNDED_RESULT
    if requirements.get('contract')=='ObjectiveEvidenceRequirements/2':
        b=requirements['target_binding']
        return ('UNAVAILABLE: Operative inspection target '+b['resolution']+'. Question: '+
                (b['operative_question'] or 'AMBIGUOUS_MULTIPLE_OPERATIVE_QUESTIONS')+
                ' Enclosing subject is context only; no broader-domain diagnosis was substituted. '
                'This does not establish that the requested capability is absent.')
    return ('UNAVAILABLE: The current inspected evidence is insufficient to diagnose the objective completion blocker. '
            'Subject: '+requirements['subject']+'. Required evidence domains not resolved for inspection: '+
            ', '.join(requirements['required_classes'])+'. '
            'No supported bounded source route resolved this objective. '
            'This does not establish that the capability or its evidence is absent.')


def current_self_claim(text):
    """Reject unsolicited implementation assertions; ordinary answers stay normal."""
    return bool(re.search(
        r'\b(?:i|mode)\s+(?:(?:currently|now)\s+)?(?:can|cannot|can.t)\s+(?:currently\s+)?'
        r'(?:inspect|introspect|audit|access)\s+(?:(?:my|its|the|my own)\s+)?'
        r'(?:runtime|implementation|code|architecture|internals?|completed interactions)\b|'
        r'\b(?:i|mode)\s+(?:lack|lacks|have|has|do not have|does not have|don.t have)\s+'
        r'(?:an?\s+)?(?:self.inspection|introspection|inspection)\s+(?:interface|capability|mechanism)\b|'
        r'\bmy\s+(?:current\s+)?(?:architecture|implementation)\s+(?:lacks|has|cannot|can.t)\b',
        text, re.I))


def is_file_operation_objective(query):
    """Bounded intent recognition only; never an execution/approval grant."""
    return bool(re.match(
        r'^\s*(?:please\s+)?(?:organize|sort|relocate|move|rename)\b'
        r'[^.!?\n]*\b(?:files?|folders?|director(?:y|ies)|workspace)\b',
        query, re.I))


def classify(query):
    from runtime_observation.inspection_target import requested
    if requested(query) or re.fullmatch(r'\s*Inspect Learning[.!]?\s*',query,re.I):
        return 'CURRENT_CAPABILITY'
    text = re.sub(r'\s+', ' ', query.replace('\u2019', "'")).strip().lower()
    # Mentioning a self question inside an ordinary writing/translation task
    # does not request an assertion about the running MODE instance.
    if (re.match(r'^(?:translate|write (?:a |an )?(?:story|poem|dialogue)|draft (?:a |an )?(?:story|dialogue))\b', text)
            and not re.search(r'\b(?:then|also|and)\s+(?:tell|inspect|explain|state|what|why|are|can)\b', text)):
        return None
    if re.search(r'\binspect\s+(?:the\s+)?completed\s+interaction\b', text):
        return 'COMPLETED_INTERACTION'
    if re.search(r'\b(?:why did|how did|what made) (?:you|mode)\b|\byour (?:last|previous|recent) (?:interaction|response|behavior)\b|\bwhat state caused (?:this|that|the) result\b', text):
        return 'COMPLETED_INTERACTION'
    self_ref = re.search(r'\b(?:you|your|yourself|mode)\b', text)
    capability = re.search(
        r'\binspect (?:yourself|mode)\b|\b(?:what|which) (?:can|can.t|cannot) (?:you|mode)\b|'
        r'\b(?:are you|is mode) (?:currently |still )?capable\b|'
        r'\b(?:your|mode.s) (?:current )?(?:capabilit\w*|limitation\w*|architecture|implementation|runtime|internal state)\b|'
        r'\bwhat (?:capability|mechanism|interface) do you (?:need|lack|have)\b|'
        r'\bwhat (?:prevents|stops|blocks) you\b|'
        r'\b(?:can you|does mode) (?:currently|right now|actually)\b|'
        r'\b(?:can|could) you (?:satisfy|achieve|meet) (?:this|that|the) objective\b|'
        r'\b(?:your|mode(?:.s)?) (?:architecture|implementation|capabilities|limitations)\b|\b(?:can|cannot|can.t) you\b.*\b(?:right now|at present)\b', text)
    if self_ref and capability:
        return 'CURRENT_CAPABILITY'
    # Permission to inspect the task environment is not a request to inspect
    # MODE. Explicit self-inspection questions above still take precedence.
    if is_file_operation_objective(query):
        return None
    # Ambiguous requests for own state/evidence receive a bounded check.
    if self_ref and re.search(r'\b(?:inspect|introspect|self-inspection|self-diagnos\w*|current state|runtime behavior|missing capability)\b', text):
        return 'CURRENT_CAPABILITY'
    return None


def prerequisite(query, owner, thread, *, ledger=None, status='AVAILABLE'):
    return {'contract': SOURCE, 'operator_id': owner, 'thread_id': thread,
            'query_hash': digest(query), 'requested_scope': classify(query),
            'available_scope': ('CAPABILITY_REGISTRY' if ledger.get('contract')=='CapabilityEvidenceLedger/1' else 'COMPLETED_INTERACTION') if ledger else None,
            'ledger_id': ledger['ledger_id'] if ledger else None, 'status': status,
            'execution_authority': False,
            'limitation': 'Completed-interaction evidence does not establish whole current implementation capability or absence.'}


def assess(query, prompt, generated=None):
    """Publication prerequisite independent of the model's own route choice."""
    scope = classify(query)
    if scope is None and generated is not None and current_self_claim(generated):
        scope = 'CURRENT_CAPABILITY'
    if scope is None: return None
    from data_governance.context_admission import AdmittedPrompt, verify
    from runtime_observation.evidence_ledger import from_prompt as ledger_from_prompt
    from runtime_observation.inspection_coverage import from_prompt as coverage_from_prompt, require_published
    result = {'required': True, 'requested_scope': scope, 'execution_authority': False,
              'allowed': False, 'reason': 'SELF_INSPECTION_EVIDENCE_UNAVAILABLE'}
    requirements = objective_evidence_requirements(query)
    if requirements is not None:
        # An ordinary registry listing still cannot discharge objective coverage.
        candidate=ledger_from_prompt(prompt) if isinstance(prompt,AdmittedPrompt) else None
        objective=(candidate or {}).get('objective',{})
        if (objective.get('query_hash')!=digest(query) or objective.get('subject')!=requirements['subject'] or
                objective.get('resolution')!='BOUNDED_SOURCES_INSPECTED'):
            result.update(reason='OBJECTIVE_EVIDENCE_DOMAINS_UNRESOLVED', objective_evidence=requirements)
            return result
        if requirements.get('contract')=='ObjectiveEvidenceRequirements/2':
            from runtime_observation.inspection_target import verify as verify_target
            try:
                if objective.get('target_binding')!=requirements['target_binding']:
                    raise PermissionError('Requested target changed')
                verify_target(query,objective['target_binding'])
            except (ValueError,KeyError,PermissionError):
                result.update(reason='OBJECTIVE_TARGET_UNRESOLVED_OR_CHANGED');return result
        elif objective.get('domain')=='LEARNING':
            from runtime_observation.learning_inspection import CLASSES
            if (requirements['subject'].casefold()!='learning' or objective.get('required_classes')!=list(CLASSES)):
                result.update(reason='OBJECTIVE_LEARNING_DOMAIN_MISMATCH');return result
        else:
            facts={(e['value']['maximum'],e['value']['component']) for e in candidate['entries']
                   if e['field']=='inspected_capacity' and e['evidence_class']=='OBSERVED'}
            if len(facts)!=1:
                result.update(reason='OBJECTIVE_BLOCKING_PREDICATE_UNAVAILABLE',objective_evidence=objective)
                return result
    if not isinstance(prompt, AdmittedPrompt): return result
    verify(prompt)
    rows = [s for s in prompt.sources if s['record']['source'] == SOURCE and
            s['record']['artifact_type'] == 'RUNTIME' and s['record']['decision'] == 'ADMITTED']
    if len(rows) != 1: return result
    receipt = json.JSONDecoder().raw_decode(rows[0]['content'].split(PREFIX, 1)[1])[0]
    ledger = ledger_from_prompt(prompt)
    expected = prerequisite(query, prompt.scope['operator_id'], prompt.scope['thread_id'], ledger=ledger,
                            status=receipt.get('status'))
    if receipt != expected or receipt['status'] != 'AVAILABLE' or ledger is None:
        return result
    coverage = coverage_from_prompt(prompt)
    if coverage is None or coverage['operator_query'] != query: return result
    result.update(ledger_id=ledger['ledger_id'], coverage_id=coverage['coverage_id'],
                  inspected_interaction_id=ledger['interaction_id'], available_scope=receipt['available_scope'])
    if generated is not None:
        try: require_published(prompt, generated)
        except (PermissionError, ValueError):
            result['reason'] = 'SELF_INSPECTION_EXPLANATION_NOT_GROUNDED_OR_COMPLETE'
            return result
        result['inspected_response_hash'] = digest(generated)
        if scope == 'CURRENT_CAPABILITY':
            from runtime_observation.capability_ledger import registry_request
            if ledger.get('contract')=='CapabilityEvidenceLedger/1' and (ledger.get('objective') or registry_request(query)):
                result.update(allowed=True,reason=None)
                return result
            result['reason'] = 'CURRENT_CAPABILITY_NOT_ESTABLISHED_BY_COMPLETED_INTERACTION_EVIDENCE'
            return result
    result.update(allowed=True, reason=None)
    return result
