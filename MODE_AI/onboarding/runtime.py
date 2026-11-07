"""Explicit Operator answers through the existing onboarding owner."""
from copy import deepcopy
from system_layer.contracts import authorize,digest


def update(runtime,request,approval):
    from temporal.temporal_context import is_valid_timezone
    from interactive_mode_ai import RuntimeState
    owner=runtime.context.identity.operator_id
    if type(request) is not dict or set(request)!={'expected_profile_hash','thread_id','answers'}:
        raise ValueError('Exact profile update contract required')
    authorize(owner,'OPERATOR_ONBOARDING_UPDATE',request,approval)
    answers=request['answers']
    if type(answers) is not dict or set(answers)!={'preferred_name','timezone','language'}:
        raise ValueError('Only Operator-managed onboarding fields may be updated')
    if any(type(v) is not str or not v.strip() or len(v)>256 for v in answers.values()):raise ValueError('Complete bounded answers required')
    if not is_valid_timezone(answers['timezone'].strip()):raise ValueError('Valid IANA timezone required')
    if runtime.pending_action is not None:raise PermissionError('Resolve pending consent first')
    if runtime.context.runtime_state not in {RuntimeState.IDLE,RuntimeState.LISTENING,RuntimeState.COMPLETE,RuntimeState.CLARIFYING}:
        raise PermissionError('Runtime is not available for profile update')
    running=runtime._supervisor_thread is not None and runtime._supervisor_thread.is_alive()
    runtime._stop_supervisor_listener()
    try:
        context=runtime.context
        if context.active_thread.thread_id!=request['thread_id'] or digest(context.profile.to_dict())!=request['expected_profile_hash']:
            raise ValueError('Operator/thread profile selection changed')
        candidate=deepcopy(context.profile)
        # Build temporal context before persistence so invalid timezone/runtime data
        # cannot leave an accepted profile with an unusable temporal context.
        candidate.update_operator_managed_info(**answers)
        temporal=runtime.temporal_engine.build_for_operator(candidate)
        profile,state=runtime.onboarding_engine.apply_onboarding_answers(context.identity,candidate,**answers,
            expected_profile_hash=request['expected_profile_hash'])
        context.profile=profile;context.onboarding_state=state;context.temporal_context=temporal
        context.assembled_context=None;context.operator_requirement_evaluation=None
        return {'contract':'OperatorOnboardingUpdate/1','state':'APPLIED','profile_hash':digest(profile.to_dict()),
            'answers':dict(preferred_name=profile.operator_managed.preferred_name,timezone=profile.operator_managed.timezone,language=profile.operator_managed.language),
            'thread_id':context.active_thread.thread_id,'persistent_memory_saved':False,'execution_authority':False}
    finally:
        if running:runtime._start_supervisor_listener()
