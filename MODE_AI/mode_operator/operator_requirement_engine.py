from __future__ import annotations
from system_layer.contracts import digest

from mode_operator.operator_domain_requirements import get_domain_requirements
from mode_operator.operator_profile import OperatorProfile
from mode_operator.operator_requirement_models import (
    OperatorDataStorageChoice,
    OperatorRequirementDefinition,
    OperatorRequirementDomain,
    OperatorRequirementEvaluation,
    OperatorRequirementResult,
    OperatorRequirementStatus,
    generate_operator_requirement_evaluation_id,
    utc_now_iso,
)
from persistent_memory.persistent_memory_manager import PersistentMemoryManager, memory_is_eligible
from persistent_memory.persistent_memory_record import (
    PersistentMemoryConsentStatus,
    PersistentMemoryDomain,
    PersistentMemoryRecord,
    PersistentMemoryStorageScope,
)


class OperatorRequirementEngine:
    """
    Determines what operator information is required before
    responsible execution may continue.

    This component never stores personal information.
    It only evaluates requirements.
    """

    def __init__(
        self,
        persistent_memory_manager: PersistentMemoryManager,
    ) -> None:
        self.persistent_memory_manager = persistent_memory_manager

    def evaluate(
        self,
        *,
        operator_profile: OperatorProfile,
        thread_id: str,
        input_text: str,
        domain: OperatorRequirementDomain,
        session_answers: dict | None = None,
        persistent_memories: list[PersistentMemoryRecord] | None = None,
    ) -> OperatorRequirementEvaluation:
        domain=OperatorRequirementDomain(domain)
        definitions = get_domain_requirements(domain)

        persistent_domain = self._map_requirement_domain_to_memory_domain(domain)

        # Memory consent is routed before this evaluator. Words such as
        # "remember" in a domain question cannot erase its requirements.
        if persistent_memories is None:
            persistent_memories = self.persistent_memory_manager.retrieve_memories(
                operator_id=operator_profile.operator_id, domain=persistent_domain)
        persistent_memories = [memory for memory in persistent_memories
                               if memory.domain == persistent_domain and memory_is_eligible(memory, operator_profile.operator_id)]

        requirements: list[OperatorRequirementResult] = []

        for definition in definitions:
            session_present = (definition.field_name in (session_answers or {})
                               and session_answers[definition.field_name] is not None
                               and str(session_answers[definition.field_name]).strip() != "")
            source = ({'source':'ACTIVE_SESSION','field_name':definition.field_name,'thread_id':thread_id,
                'value_hash':digest(session_answers[definition.field_name])}
                if session_present else self._requirement_source(
                definition=definition,
                operator_profile=operator_profile,
                persistent_memories=persistent_memories,
            ))
            present = source is not None

            requirements.append(
                OperatorRequirementResult(
                    field_name=definition.field_name,
                    label=definition.label,
                    status=(
                        OperatorRequirementStatus.SATISFIED
                        if present
                        else OperatorRequirementStatus.MISSING
                    ),
                    required=definition.required,
                    sensitivity=definition.sensitivity,
                    reason=definition.reason,
                    value_present=present,
                    metadata={'satisfaction_source':source},
                    storage_choice=(
                        OperatorDataStorageChoice.SESSION_ONLY if session_present else OperatorDataStorageChoice.PERSISTENT
                        if present
                        else OperatorDataStorageChoice.NOT_SELECTED
                    ),
                )
            )

        return OperatorRequirementEvaluation(
            evaluation_id=generate_operator_requirement_evaluation_id(),
            operator_id=operator_profile.operator_id,
            thread_id=thread_id,
            input_text=input_text,
            domain=domain,
            requirements=requirements,
            created_at=utc_now_iso(),
        )

    def _requirement_exists(
        self,
        *,
        definition: OperatorRequirementDefinition,
        operator_profile: OperatorProfile,
        persistent_memories: list[PersistentMemoryRecord],
    ) -> bool:
        return self._requirement_source(definition=definition,operator_profile=operator_profile,
            persistent_memories=persistent_memories) is not None

    def _requirement_source(self,*,definition,operator_profile,persistent_memories):
        operator_data = operator_profile.operator_managed.__dict__

        if definition.field_name in operator_data:
            value = operator_data[definition.field_name]

            if isinstance(value, str) and value.strip():
                return {'source':'OPERATOR_PROFILE','field_name':definition.field_name,'operator_id':operator_profile.operator_id,'value_hash':digest(value)}

            if value is not None and not isinstance(value, str):
                return {'source':'OPERATOR_PROFILE','field_name':definition.field_name,'operator_id':operator_profile.operator_id,'value_hash':digest(value)}

        for memory in persistent_memories:
            if memory.storage_scope != PersistentMemoryStorageScope.PERSISTENT:
                continue

            if memory.consent_status != PersistentMemoryConsentStatus.APPROVED:
                continue

            if memory.data_category == definition.field_name:
                return {'source':'PERSISTENT_MEMORY','memory_id':memory.memory_id,'version':memory.version,
                    'governance_decision_id':memory.governance_decision.get('decision_id'),'field_name':definition.field_name}

        return None

    def _map_requirement_domain_to_memory_domain(
        self,
        domain: OperatorRequirementDomain,
    ) -> PersistentMemoryDomain:
        mapping = {
            OperatorRequirementDomain.GENERAL: PersistentMemoryDomain.GENERAL,
            OperatorRequirementDomain.HEALTH: PersistentMemoryDomain.HEALTH,
            OperatorRequirementDomain.FINANCIAL_PLANNING: PersistentMemoryDomain.FINANCIAL,
            OperatorRequirementDomain.LEGAL_ASSISTANCE: PersistentMemoryDomain.LEGAL,
            OperatorRequirementDomain.EDUCATION: PersistentMemoryDomain.EDUCATION,
            OperatorRequirementDomain.PROFESSIONAL: PersistentMemoryDomain.PROFESSIONAL,
            OperatorRequirementDomain.ENGINEERING: PersistentMemoryDomain.ENGINEERING,
            OperatorRequirementDomain.ENTERPRISE_WORKFLOW: PersistentMemoryDomain.ENTERPRISE_WORKFLOW,
        }

        return mapping.get(domain, PersistentMemoryDomain.GENERAL)
