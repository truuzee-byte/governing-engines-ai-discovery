"""Prompt-scoped coverage of existing ledger statements; never new evidence."""
import json
import re
from copy import deepcopy
from .transformation_provenance import digest
from learning.contracts import digest as objective_digest

PREFIX = '\nINSPECTION COVERAGE CONTRACT (derived requirements, not evidence):\n'
INSTRUCTION = '''
For an InspectionCoverage/1 contract, FINAL selection must satisfy every requested
coverage group: select at least one entry from each group's any_of list. A statement
may satisfy multiple groups. Ordered transitions require prior before result, in
recorded sequence. Include required scoped UNAVAILABLE limitations. Do not select
all supporting entries; use a minimal sufficient selection within the existing
24-statement limit. Missing required coverage fails closed; no answer is repaired.
'''
PATTERNS = {
    'ORDERED_TRANSITIONS': r'state transitions|transition chain|transitions in order',
    'PRODUCING_COMPONENT': r'component|producer|function|stage',
    'GOVERNING_RULE': r'rules?|constraints?',
    'MUTATION_OR_SEPARATE': r'mutation|separate evaluator',
    'OBSERVED': r'\bobserved\b',
    'INFERRED': r'\binferred\b',
    'UNAVAILABLE': r'\bunavailable\b|missing evidence|unknown evidence',
    'OPERATOR_INCONSISTENCY': r'inconsisten',
}


def derive(query, ledger):
    if ledger.get('objective'):
        return objective_coverage(query,ledger)
    if ledger.get('contract')=='CapabilityEvidenceLedger/1':
        return capability_coverage(query,ledger)
    clauses = [re.sub(r'^[\s\d.*\-:)]+', '', s).strip() for s in query.splitlines()]
    clauses = [s for s in clauses if s and not re.match(r'(do not|don.t|never|avoid|no\b)', s, re.I)]
    entries = ledger['entries']
    events = sorted(((sid, src) for sid, src in ledger['sources'].items()
                     if src['source_type'] == 'TRANSITION_RECORD'), key=lambda p: p[1]['sequence'])
    dimensions = []
    for name, pattern in PATTERNS.items():
        requested = [s for s in clauses if re.search(pattern, s, re.I)]
        dimensions.append({'dimension_id': name, 'operator_requested': bool(requested),
                           'requested_by': requested, 'coverage_groups': []})
    dims = {d['dimension_id']: d for d in dimensions}

    def group(name, role, values):
        if values:
            dims[name]['coverage_groups'].append({'group_id': name + ':' + role,
                'any_of': [e['entry_id'] for e in values],
                'coverage_kinds': sorted({e['evidence_class'] for e in values})})

    ordered = []
    for sid, source in events:
        local = [e for e in entries if e['source_id'] == sid]
        for field in ('prior', 'result'):
            values = [e for e in local if e['field'] == field]
            group('ORDERED_TRANSITIONS', sid + ':' + field, values)
            if values: ordered.append(values[0]['entry_id'])
        # Each canonical transition statement carries its recorded producer/stage.
        group('PRODUCING_COMPONENT', sid, local if source['producer'] and source['stage'] else
              [e for e in local if e['field'] == 'producer'])
        group('GOVERNING_RULE', sid, [e for e in local if e['field'] == 'rules'])
    group('MUTATION_OR_SEPARATE', 'relation', [e for e in entries if e['field'] == 'separate_result_relation'])
    group('OBSERVED', 'direct', [e for e in entries if e['evidence_class'] == 'OBSERVED'])
    group('INFERRED', 'derived', [e for e in entries if e['evidence_class'] == 'INFERRED'])
    group('OPERATOR_INCONSISTENCY', 'presentation', [e for e in entries if e['field'] == 'operator_presentation'])
    group('UNAVAILABLE', 'unrecorded_events', [e for e in entries if e['field'] == 'events_outside_recorded_projection'])
    # A correlated disagreement must remain visible in a requested transition or
    # presentation account. One canonical endpoint includes both recorded values.
    for index, conflict in enumerate(ledger['conflicts']):
        endpoints = [e for e in entries if e['entry_id'] in (conflict['left'], conflict['right'])]
        for dimension in ('ORDERED_TRANSITIONS', 'OPERATOR_INCONSISTENCY'):
            group(dimension, 'recorded_conflict:' + str(index), endpoints)
    # Missing producer-emitted reasons are material to a requested transition/rule
    # account. Confidence and missing legacy aliases are not mandatory duplicates.
    if dims['ORDERED_TRANSITIONS']['operator_requested'] or dims['GOVERNING_RULE']['operator_requested']:
        for e in entries:
            if e['source_id'] in dict(events) and e['field'] in ('reason', 'rules', 'producer') and e['evidence_class'] == 'UNAVAILABLE':
                group('UNAVAILABLE', e['scope'], [e])
    result = {'contract': 'InspectionCoverage/1', 'ledger_id': ledger['ledger_id'],
              **{k: ledger[k] for k in ('operator_id', 'thread_id', 'interaction_id')},
              'operator_query': query, 'prompt_hash': digest(query), 'dimensions': dimensions,
              'ordered_entry_ids': ordered, 'execution_authority': False,
              'derivation': 'BOUNDED_POSITIVE_CLAUSE_RULES_NOT_SEMANTIC_VALIDATION'}
    result['coverage_id'] = 'coverage-' + digest(result)[:16]
    return evaluate(result, ledger, [])


def capability_coverage(query,ledger):
    # Every bounded record is requested for a registry listing. No hidden semantic
    # completeness claim: these groups cover exactly the selected registry scope.
    groups=[{'group_id':e['scope'],'any_of':[e['entry_id']],
             'coverage_kinds':[e['evidence_class']]} for e in ledger['entries']]
    result={'contract':'InspectionCoverage/1','ledger_id':ledger['ledger_id'],
        **{k:ledger[k] for k in ('operator_id','thread_id','interaction_id')},
        'operator_query':query,'prompt_hash':digest(query),'dimensions':[
        {'dimension_id':'CAPABILITY_REGISTRY_SCOPE','operator_requested':True,
         'requested_by':[query],'coverage_groups':groups}], 'ordered_entry_ids':[],
        'execution_authority':False,'derivation':'EXPLICIT_BOUNDED_REGISTRY_SCOPE_NOT_WHOLE_SYSTEM_VALIDATION'}
    result['coverage_id']='coverage-'+digest(result)[:16]
    return evaluate(result,ledger,[])

def objective_coverage(query,ledger):
    if ledger['objective']['query_hash']!=objective_digest(query):raise PermissionError('Objective query mismatch')
    fields=['registry_record','operator_objective',*['evidence_class_'+k for k in ('CODE','INTEGRATION','TEST','RUNTIME','QUALIFICATION')],
            'objective_unknowns','inspected_capacity']
    target=ledger['objective'].get('target_binding')
    if target is not None:
        from .inspection_target import verify
        verify(query,target)
        fields=['operator_objective','inspection_target','target_implementation','target_unknowns']
    elif ledger['objective'].get('domain')=='LEARNING':
        from .learning_inspection import CLASSES
        fields=['operator_objective',*['learning_class_'+k for k in CLASSES],'objective_unknowns']
    groups=[{'group_id':field,'any_of':[e['entry_id'] for e in ledger['entries'] if e['field']==field],
             'coverage_kinds':sorted({e['evidence_class'] for e in ledger['entries'] if e['field']==field})}
            for field in fields]
    result={'contract':'InspectionCoverage/1','ledger_id':ledger['ledger_id'],
        **{k:ledger[k] for k in ('operator_id','thread_id','interaction_id')},
        'operator_query':query,'prompt_hash':objective_digest(query),'dimensions':[
        {'dimension_id':'OBJECTIVE_EVIDENCE','operator_requested':True,'requested_by':[query],'coverage_groups':groups}],
        'ordered_entry_ids':[],'execution_authority':False,
        'derivation':('BOUND_TARGET_SEMANTIC_OBLIGATIONS_NOT_GENERAL_ENTAILMENT' if target is not None else
                      'FIXED_LEARNING_EVIDENCE_CLASSES_AVAILABLE_OR_UNAVAILABLE_NOT_BEHAVIORAL_VALIDATION'
                      if ledger['objective'].get('domain')=='LEARNING' else
                      'REGISTERED_SUBJECT_AND_EXPLICIT_STATEMENT_CAPACITY_ONLY_NOT_GENERAL_DIAGNOSIS')}
    result['coverage_id']='coverage-'+digest(result)[:16]
    return evaluate(result,ledger,[])


def evaluate(contract, ledger, selected):
    result = deepcopy(contract)
    known = {e['entry_id']: e for e in ledger['entries']}
    if contract['ledger_id'] != ledger['ledger_id'] or any(i not in known for i in selected):
        raise PermissionError('Coverage ledger mismatch')
    order = [i for i in contract['ordered_entry_ids'] if i in selected]
    order_ok = [selected.index(i) for i in order] == sorted(selected.index(i) for i in order)
    for d in result['dimensions']:
        groups = d['coverage_groups']
        support = sorted({i for g in groups for i in g['any_of']})
        hits = [i for i in selected if i in support]
        missing = [g['group_id'] for g in groups if not set(selected).intersection(g['any_of'])]
        d.update(supporting_entry_ids=support, relevant_ledger_evidence_exists=bool(support),
                 covered_by_any_selected_statement=bool(hits), selected_entry_ids=hits,
                 coverage_kind=sorted({known[i]['evidence_class'] for i in hits}),
                 unavailable_disclosure_required=any('UNAVAILABLE' in g['coverage_kinds'] and
                     g['coverage_kinds'] == ['UNAVAILABLE'] for g in groups),
                 failure_reason=None)
        if not d['operator_requested']: status = 'NOT_REQUESTED'
        elif not support: status = 'NO_RELEVANT_EVIDENCE'
        elif missing or d['dimension_id'] == 'ORDERED_TRANSITIONS' and not order_ok:
            status = 'MISSING_REQUIRED_COVERAGE'
            d['failure_reason'] = {'missing_groups': missing, 'recorded_order_preserved': order_ok}
        else: status = 'COVERED'
        d['status'] = status
    result['selected_statement_ids'] = list(selected)
    result['complete'] = not any(d['status'] == 'MISSING_REQUIRED_COVERAGE' for d in result['dimensions'])
    return result


def from_prompt(prompt):
    from data_governance.context_admission import AdmittedPrompt, verify
    from .evidence_ledger import from_prompt as ledger_from_prompt
    if not isinstance(prompt, AdmittedPrompt): return None
    verify(prompt)
    found = [s for s in prompt.sources if s['record']['source'] == 'InspectionCoverage/1'
             and s['record']['artifact_type'] == 'RUNTIME' and s['record']['decision'] == 'ADMITTED']
    if not found: return None
    if len(found) != 1: raise PermissionError('Ambiguous inspection coverage')
    value = json.JSONDecoder().raw_decode(found[0]['content'].split(PREFIX, 1)[1])[0]
    ledger = ledger_from_prompt(prompt)
    if ledger is None or value != derive(value['operator_query'], ledger):
        raise PermissionError('Coverage derivation or scope mismatch')
    return value


class CoverageIncomplete(PermissionError):
    def __init__(self, report):
        self.report = report
        super().__init__('MISSING_REQUIRED_COVERAGE: ' + json.dumps(report, separators=(',', ':')))


def require(prompt, selected):
    contract = from_prompt(prompt)
    if contract is None: return None
    from .evidence_ledger import from_prompt as ledger_from_prompt
    report = evaluate(contract, ledger_from_prompt(prompt), selected)
    if not report['complete']: raise CoverageIncomplete(report)
    return report


def require_published(prompt, text):
    if from_prompt(prompt) is None: return
    from .evidence_ledger import from_prompt as ledger_from_prompt, line
    ledger = ledger_from_prompt(prompt)
    if ledger.get('objective'):
        from .evidence_ledger import objective_publication
        return objective_publication(text,prompt)
    known = {line(ledger, e): e['entry_id'] for e in ledger['entries']}
    lines = text.splitlines()
    if not 1 <= len(lines) <= 24 or len(set(lines)) != len(lines) or any(v not in known for v in lines):
        raise PermissionError('Coverage publication requires exact ledger statements; fallback refused')
    require(prompt, [known[v] for v in lines])
