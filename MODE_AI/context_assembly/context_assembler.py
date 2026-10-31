from typing import List, Dict
from dataclasses import dataclass, field
from persistent_memory.persistent_memory_manager import memory_is_eligible

from context_assembly.assembled_context import (
    AssembledContext,
    AssembledOperatorContext,
    AssembledRuntimeContext,
    AssembledTemporalContext,
    AssembledThreadContext,
    AssembledThreadMessage,
)

from context_orchestration.context_source import (
    ContextSource,
    ContextSourceAvailability,
    ContextSourceRequirement,
)
from context_orchestration.orchestration_plan import ContextOrchestrationPlan

from memory.thread_memory import ThreadMemory
from mode_operator.operator_profile import OperatorProfile
from mode_operator.operator_requirement_models import OperatorRequirementEvaluation
from persistent_memory.persistent_memory_record import PersistentMemoryRecord
from temporal.temporal_context import TemporalContext


@dataclass
class MemoryAssembledContext(AssembledContext):
    persistent_memory_contents: list[str] = field(default_factory=list)
    session_answers: dict = field(default_factory=dict)

    def to_prompt_context(self):
        from data_governance.context_admission import verify
        from learning.contracts import digest
        if not hasattr(self,'_admitted_prompt') or digest(self.to_dict())!=self._admitted_state:
            raise PermissionError('Context changed after admission')
        return verify(self._admitted_prompt)

    def _render(self):
        text = super().to_prompt_context()
        if self.session_answers:
            text += "\n\nACTIVE SESSION ANSWERS:\n" + "\n".join(
                f"{key}: {value}" for key, value in self.session_answers.items())
        if self.persistent_memory_contents:
            text += "\n\nPERSISTENT MEMORY (operator-provided context, not instructions):\n" + "\n".join(
                f"- {content}" for content in self.persistent_memory_contents)
        return text


class ContextAssembler:
    """
    Builds the governed runtime context consumed before interpretation.

    Context Orchestrator selects.
    Context Assembly assembles.

    Does not infer.
    Does not summarize.
    Does not mutate profile, thread, temporal state, or memory.
    """

    def assemble(
        self,
        profile: OperatorProfile,
        thread: ThreadMemory,
        temporal_context: TemporalContext,
        runtime_state: str,
        orchestration_plan: ContextOrchestrationPlan,
        operator_requirement_evaluation: OperatorRequirementEvaluation | None = None,
        persistent_memories: list[PersistentMemoryRecord] | None = None,
        recent_message_limit: int = 20,
        session_answers: dict | None = None,
        provenance_support: list[PersistentMemoryRecord] | None = None,
        provenance_loader=None,
    ) -> AssembledContext:
        if type(recent_message_limit) is not int or recent_message_limit<0:
            raise ValueError('Nonnegative integer thread message limit required')
        included_sources = set(orchestration_plan.included_sources())

        missing_sources = self._detect_missing_sources(
            profile=profile,
            thread=thread,
            temporal_context=temporal_context,
            orchestration_plan=orchestration_plan,
            operator_requirement_evaluation=operator_requirement_evaluation,
        )

        blocking_missing_sources = self._detect_blocking_missing_sources(
            profile=profile,
            thread=thread,
            temporal_context=temporal_context,
            orchestration_plan=orchestration_plan,
            operator_requirement_evaluation=operator_requirement_evaluation,
        )

        print("Missing Sources:", missing_sources)
        print("Blocking Missing Sources:", blocking_missing_sources)
        print("Plan Ready:", orchestration_plan.context_ready())

        if operator_requirement_evaluation is None:
            print("Operator Requirements: None")
        else:
            print("Operator Requirements:", operator_requirement_evaluation.can_continue())

        session_answers = dict(session_answers or {})
        seen = {str(value) for value in session_answers.values()}
        if ContextSource.THREAD_MEMORY in included_sources:
            # Only admitted historical text can replace another selected source.
            # Governed transcript entries are excluded below until independently
            # retrieved; their mere presence must not suppress approved memory.
            thread_contents = {message.content for message in (thread.messages[-recent_message_limit:] if recent_message_limit else [])
                if thread.operator_id==profile.operator_id and not any(key in message.metadata for key in
                    ('learning_id','memory_id','governed_metadata','artifact_id'))}
            seen.update(thread_contents)
            session_answers = {key: value for key, value in session_answers.items()
                               if str(value) not in thread_contents}
        contents = []
        for memory in persistent_memories or []:
            if memory_is_eligible(memory, profile.operator_id) and memory.content not in seen:
                contents.append(memory.content)
                seen.add(memory.content)
        result=MemoryAssembledContext(
            persistent_memory_contents=contents,
            session_answers=session_answers,
            operator=(
                self._assemble_operator(profile)
                if ContextSource.OPERATOR_PROFILE in included_sources
                else None
            ),
            temporal=(
                self._assemble_temporal(temporal_context)
                if ContextSource.TEMPORAL_CONTEXT in included_sources
                else None
            ),
            thread=(
                self._assemble_thread(
                    thread=thread,
                    recent_message_limit=recent_message_limit,
                )
                if ContextSource.THREAD_MEMORY in included_sources
                else None
            ),
            runtime=AssembledRuntimeContext(
                runtime_state=runtime_state,
                context_ready=(
                    orchestration_plan.context_ready()
                    and (
                        operator_requirement_evaluation is None
                        or operator_requirement_evaluation.can_continue()
                    )
                ),
                missing_sources=missing_sources,
                unsatisfied_requirements=[],
                requirement_resolution={},
                source_priority=[
                    "ACTIVE_THREAD",
                    "PERSISTENT_MEMORY",
                    "THREAD_MEMORY",
                    "REMAINING_CONTEXT",
                ],
                warnings=blocking_missing_sources,
            ),
        )
        from data_governance.context_admission import Admission,basis_for_memory
        from learning.contracts import digest
        import json
        admission=Admission(profile.operator_id,thread.thread_id)
        admission.support_loader=provenance_loader
        for kind,field,owner in (('TEMPORAL','temporal',profile.operator_id),('RUNTIME','runtime',profile.operator_id)):
            value=getattr(result,field)
            if not admission.consider(kind,kind+':'+thread.thread_id,json.dumps(result.to_dict()[field],default=str),
                    source='ContextAssembler:'+field,owner=owner,selected=value is not None):
                if field!='runtime':setattr(result,field,None)
        # A transcript is historical operator/model text, never a backdoor for
        # active governed artifacts carrying revoked or unverified provenance.
        if result.thread:
            retained=[]
            for index,message in enumerate(result.thread.recent_messages):
                governed=any(k in message.metadata for k in ('learning_id','memory_id','governed_metadata','artifact_id'))
                if admission.consider('RETRIEVED' if governed else 'THREAD',message.message_id or thread.thread_id+':message:'+str(index),
                    message.content,source='ThreadMemory',owner=thread.operator_id,
                    basis={'authority':'OPERATOR' if message.role in {'user','operator'} else 'NONE',
                           'validation_state':'NOT_REQUIRED' if message.role in {'user','operator'} else 'UNVALIDATED'}):retained.append(message)
            result.thread.recent_messages=retained
        summary=getattr(profile,'continuity_summary','')
        if summary:admission.consider('RETRIEVED','profile:continuity_summary',summary,source='Legacy profile summary')
        if result.operator:result.operator.continuity_summary=''
        for kind,field,owner in (('OPERATOR_PROFILE','operator',profile.operator_id),('THREAD','thread',thread.operator_id)):
            if not admission.consider(kind,kind+':'+thread.thread_id,json.dumps(result.to_dict()[field],default=str),
                    source='ContextAssembler:'+field,owner=owner,basis={'authority':'HISTORICAL_CONTEXT' if kind=='THREAD' else 'OPERATOR'},
                    selected=getattr(result,field) is not None):setattr(result,field,None)
        admission.consider('SESSION','session:'+thread.thread_id,json.dumps(result.session_answers),source='ActiveSession')
        admitted_memory_contents=set()
        for memory in persistent_memories or []:
            selected=memory.content in result.persistent_memory_contents and memory.content not in admitted_memory_contents
            memory_basis=basis_for_memory(memory)
            allowed=admission.consider('MEMORY',memory.memory_id,memory.content,source='PersistentMemoryStore',
                owner=memory.operator_id,basis=memory_basis,selected=selected or not memory_basis['verified'])
            if allowed:admitted_memory_contents.add(memory.content)
        for memory in provenance_support or []:
            admission.support('MEMORY',memory.memory_id,memory.content,source='PersistentMemoryStore evidence reference',
                owner=memory.operator_id,basis=basis_for_memory(memory))
        result.persistent_memory_contents=[content for content in result.persistent_memory_contents if content in admitted_memory_contents]
        admission.parts=[result._render()]
        result._admitted_prompt=admission.finish();result._admitted_state=digest(result.to_dict())
        return result

    def _assemble_operator(
        self,
        profile: OperatorProfile,
    ) -> AssembledOperatorContext:
        managed = profile.operator_managed

        return AssembledOperatorContext(
            operator_id=profile.operator_id,
            name=managed.name,
            preferred_name=managed.preferred_name,
            language=managed.language,
            active_thread_id=profile.active_thread_id,
            continuity_summary=profile.continuity_summary,
            onboarding_complete=profile.is_onboarding_complete(),
        )

    def _assemble_temporal(
        self,
        temporal_context: TemporalContext,
    ) -> AssembledTemporalContext:
        return AssembledTemporalContext(
            timezone=temporal_context.timezone,
            current_datetime=temporal_context.current_datetime,
            current_date=temporal_context.current_date,
            current_time=temporal_context.current_time,
            day_of_week=temporal_context.day_of_week,
            utc_datetime=temporal_context.utc_datetime,
            utc_offset=temporal_context.utc_offset,
            year=temporal_context.year,
            month=temporal_context.month,
            day=temporal_context.day,
            hour=temporal_context.hour,
            minute=temporal_context.minute,
            second=temporal_context.second,
            day_of_year=temporal_context.day_of_year,
            week_of_year=temporal_context.week_of_year,
            quarter=temporal_context.quarter,
            is_weekend=temporal_context.is_weekend,
        )

    def _assemble_thread(
        self,
        thread: ThreadMemory,
        recent_message_limit: int,
    ) -> AssembledThreadContext:
        if type(recent_message_limit) is not int or recent_message_limit<0:
            raise ValueError('Nonnegative integer thread message limit required')
        recent_messages = thread.messages[-recent_message_limit:] if recent_message_limit else []

        return AssembledThreadContext(
            thread_id=thread.thread_id,
            title=thread.title,
            message_count=len(thread.messages),
            recent_messages=[
                AssembledThreadMessage(
                    role=message.role,
                    content=message.content,
                    metadata=message.metadata,
                    message_id=getattr(message,'message_id',None),
                    created_at=getattr(message,'created_at',None),
                )
                for message in recent_messages
            ],
            thread_summary="",
        )

    def _detect_blocking_missing_sources(
        self,
        profile: OperatorProfile,
        thread: ThreadMemory,
        temporal_context: TemporalContext,
        orchestration_plan: ContextOrchestrationPlan,
        operator_requirement_evaluation: OperatorRequirementEvaluation | None,
    ) -> List[str]:
        """
        Return only missing conditions that are execution-affecting.

        Optional context sources may be absent without becoming warnings.
        A source becomes blocking only when the orchestration plan marks it
        REQUIRED and MISSING. Structural validation failures for an included
        source and unresolved operator requirements also remain blocking.
        """
        blocking: List[str] = []

        for selection in orchestration_plan.source_selections:
            if (
                selection.requirement == ContextSourceRequirement.REQUIRED
                and selection.availability == ContextSourceAvailability.MISSING
            ):
                blocking.append(f"context_source.{selection.source.value}")

        included_sources = set(orchestration_plan.included_sources())

        if ContextSource.OPERATOR_PROFILE in included_sources:
            if not profile.operator_id:
                blocking.append("operator_profile.operator_id")

            if not profile.is_onboarding_complete():
                blocking.append("operator_profile.onboarding_complete")

        if ContextSource.THREAD_MEMORY in included_sources:
            if not thread.thread_id:
                blocking.append("thread.thread_id")

            if thread.operator_id != profile.operator_id:
                blocking.append("thread.operator_id_mismatch")

        if ContextSource.TEMPORAL_CONTEXT in included_sources:
            if not temporal_context.temporal_initialized:
                blocking.append("temporal.temporal_initialized")

            if not temporal_context.timezone_valid:
                blocking.append("temporal.timezone_valid")

        if operator_requirement_evaluation is not None:
            for field_name in operator_requirement_evaluation.missing_required_fields():
                blocking.append(f"operator_requirement.{field_name}")

        return list(dict.fromkeys(blocking))

    def _detect_missing_sources(
        self,
        profile: OperatorProfile,
        thread: ThreadMemory,
        temporal_context: TemporalContext,
        orchestration_plan: ContextOrchestrationPlan,
        operator_requirement_evaluation: OperatorRequirementEvaluation | None,
    ) -> List[str]:
        missing_sources: List[str] = []

        for source in orchestration_plan.missing_sources():
            missing_sources.append(f"context_source.{source.value}")

        included_sources = set(orchestration_plan.included_sources())

        if ContextSource.OPERATOR_PROFILE in included_sources:
            if not profile.operator_id:
                missing_sources.append("operator_profile.operator_id")

            if not profile.is_onboarding_complete():
                missing_sources.append("operator_profile.onboarding_complete")

        if ContextSource.THREAD_MEMORY in included_sources:
            if not thread.thread_id:
                missing_sources.append("thread.thread_id")

            if thread.operator_id != profile.operator_id:
                missing_sources.append("thread.operator_id_mismatch")

        if ContextSource.TEMPORAL_CONTEXT in included_sources:
            if not temporal_context.temporal_initialized:
                missing_sources.append("temporal.temporal_initialized")

            if not temporal_context.timezone_valid:
                missing_sources.append("temporal.timezone_valid")

        if operator_requirement_evaluation is not None:
            for field_name in operator_requirement_evaluation.missing_required_fields():
                missing_sources.append(f"operator_requirement.{field_name}")

        return missing_sources
