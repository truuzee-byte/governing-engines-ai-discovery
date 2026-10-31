"""Inspectable bounded admission inventory; classification is not enforcement.

One row per listed public admission route (not per sentence, helper, or branch).
UNRESOLVED_GAP deliberately includes partial RP coverage: no completion percentage
is inferred from the presence of a gate on another route.
"""
from copy import deepcopy

STATUS = {'RP_GOVERNED', 'NON_MATERIAL_EXEMPT', 'BLOCKED', 'UNRESOLVED_GAP'}


def _route(path, symbol, status, claim, transition, reason, baseline='UNGOVERNED'):
    return dict(entry_point=symbol, file=path, status=status, material_claim=claim,
                material_transition=transition, reason=reason, baseline=baseline)


SYSTEM_MUTATIONS = {
    'record_capability_evidence': 'Operator-approved typed evidence inventory, not independent RP admission or qualification promotion. Exact stronger-state transitions remain unavailable.',
    'identity': 'Identity authority is locally approved; no RP transition request.',
    'declare': 'Declaration preserves pending reality, but mutation is not RP evaluated.',
    'inventory': 'Source inspection is locally measured; no RP material-state admission.',
    'discover_sources': 'Discovery is evidence custody, not independent RP validation.',
    'operational_understanding': 'Local completeness assessment does not admit RP-confirmed knowledge.',
    'operational_sources': 'Local source binding is not an RP transition decision.',
    'audit': 'External capability finding verified; exact registry mutation has no general binding.',
    'control': 'Operator control transition has no RP binding; never delay a safety halt.',
    'prepare': 'Exact operator approval and local structural checks; no RP readiness claim.',
    'construct': 'Construction reserves state and invokes Builder before post-build RP.',
    'validate': 'Dimensions use external RP; registry mutation and all preconditions not one bound proposal.',
    'accept': 'Fresh dimension checks and artifact readback; exact registration transition not RP-bound.',
    'rollback': 'Direct approved filesystem restoration; fresh reality required afterward, not before mutation.',
    'learning_change': 'Existing Learning event gate; no complete new material transition binding.',
    'admit_library': 'Operational registration required; no separately bound library admission verdict.',
    'recommend': 'A provisional recommendation, not an accepted capability or execution authorization.',
}

SYSTEM_READS = {
    'inspect_capabilities': 'Owned read-only correlated registry evidence; no truth adjudication, state mutation or execution authority.',
}


def coverage():
    rows = [_route('system_layer/creation/service.py', 'SystemLayer.' + method,
        'UNRESOLVED_GAP', True, True, reason,
        'PARTIALLY_GOVERNED' if method in {'audit', 'validate', 'accept', 'learning_change'} else 'UNGOVERNED')
        for method, reason in SYSTEM_MUTATIONS.items()]
    rows += [_route('system_layer/creation/service.py', 'SystemLayer.' + method,
        'NON_MATERIAL_EXEMPT', False, False, reason, 'NOT_IMPLEMENTED')
        for method, reason in SYSTEM_READS.items()]
    rows += [_route('system_layer/creation/service.py', 'SystemLayer.admit_material',
        'RP_GOVERNED', True, True, 'Exact canonical signed RP proposal binding and atomic System receipt/state write.', 'NOT_IMPLEMENTED')]
    rows += [
        _route('data_governance/response_gate.py', 'governed_interaction', 'UNRESOLVED_GAP', True, False,
               'Detected consequential publication is RP-bound; grammatical materiality coverage is bounded.', 'PARTIALLY_GOVERNED'),
        _route('understanding/understanding_store.py', 'UnderstandingStore.commit', 'UNRESOLVED_GAP', True, True,
               'Semantic custody can commit; no common material transition gate. Handoff now explicitly pending RP.'),
        _route('understanding/understanding_store.py', 'UnderstandingStore.delete_permanently', 'UNRESOLVED_GAP', False, True,
               'Owner policy deletion is not externally RP-bound.'),
        _route('understanding/cinematic_runtime.py', 'execute', 'BLOCKED', True, False,
               'Candidate DOCUMENT only; no reality admission or executor authority. Local authored meaning remains separate.'),
        _route('understanding/story_interpretation.py', 'StoryInterpreter.run', 'BLOCKED', True, False,
               'Source-derived interpretation is pending RP; cannot self-issue a verdict.'),
        _route('specs/cinematic_specification.py', 'executor_handoff', 'BLOCKED', True, True,
               'Preparation only. Per-fact RP/disposition inventory and explicit NOT_READY; no executor eligibility.'),
        _route('understanding/creative_production.py', 'CreativePreparation.prepare', 'BLOCKED', True, False,
               'UNPROVEN preparation, no execution or canonical truth admission.'),
        _route('knowledge/registry.py', 'KnowledgeRegistry.register', 'UNRESOLVED_GAP', True, True,
               'Source-linked pending reality; lifecycle mutation is not RP-bound.'),
        _route('persistent_memory/persistent_memory_manager.py', 'PersistentMemoryManager.confirm_candidate', 'UNRESOLVED_GAP', True, True,
               'Explicit consent and attested source remain; persistent admission lacks external RP.'),
        _route('persistent_memory/persistent_memory_manager.py', 'PersistentMemoryManager.lifecycle', 'UNRESOLVED_GAP', False, True,
               'Operator lifecycle authority is not a scoped external reality decision.'),
        _route('learning/service.py', 'LearningService.review', 'UNRESOLVED_GAP', True, True,
               'Evidence-backed candidate eligibility includes RP; exact learned mutation has no common binding.', 'PARTIALLY_GOVERNED'),
        _route('learning/service.py', 'LearningService.revalidate', 'UNRESOLVED_GAP', True, True,
               'Fresh RP evidence for maintenance/update; safety suspension and exact prior/candidate transition differ.', 'PARTIALLY_GOVERNED'),
        _route('specs/handoff_gate.py', 'approve_builder_handoff', 'UNRESOLVED_GAP', True, True,
               'Local schema/snapshot/authority checks do not establish RP-governed readiness.'),
        _route('integration/build_runtime.py', 'BuildRuntime.execute', 'UNRESOLVED_GAP', True, True,
               'Post-build RP exists; pre-execution readiness and mandatory Kernel cutover remain absent.', 'PARTIALLY_GOVERNED'),
        _route('builder/core/build_entry.py', 'run_builder_core', 'UNRESOLVED_GAP', True, True,
               'require_kernel defaults false. Bootstrap execution remains an explicit cutover blocker.'),
        _route('interactive_mode_ai.py', 'ModeRuntime._set_state', 'UNRESOLVED_GAP', False, True,
               'Only registered reality dependencies are checked; operational chat state alone is not a material verdict.', 'PARTIALLY_GOVERNED'),
        _route('understanding/cinematic_validation.py', 'compare', 'BLOCKED', True, False,
               'Requirement-bound measurements never claim external RP confirmation.'),
        _route('runtime_observation/observation_collector.py', 'RuntimeObservationCollector', 'NON_MATERIAL_EXEMPT', False, False,
               'Captures measurements and runtime history, does not adjudicate their truth.'),
        _route('memory/thread_store.py', 'ThreadStore.save_thread', 'UNRESOLVED_GAP', True, True,
               'Conversation custody and continuity are not a generic external material-admission boundary.'),
    ]
    if any(row['status'] not in STATUS for row in rows):
        raise ValueError('Unclassified governance route')
    return deepcopy(rows)
