from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
import threading
import time
from core.mode_controller import process_interaction
from models.runtime_models import OperatorInput

from mode_operator.operator_identity import OperatorIdentity
from mode_operator.operator_profile import OperatorProfile
from mode_operator.operator_store import OperatorStore
from mode_operator.operator_requirement_engine import OperatorRequirementEngine
from mode_operator.operator_requirement_models import (
    OperatorRequirementDomain,
    OperatorRequirementEvaluation,
)

from onboarding.onboarding_engine import OnboardingEngine
from onboarding.onboarding_state import OnboardingState

from runtime_state.pending_action_router import PendingActionRouter
from runtime_state.pending_action import create_memory_save_pending_action

from memory.thread_memory import ThreadMemory
from memory.thread_store import ThreadStore

from temporal.temporal_context import TemporalContext, is_valid_timezone
from temporal.temporal_engine import TemporalEngine

from context_assembly.context_assembler import ContextAssembler
from context_assembly.assembled_context import AssembledContext

from context_orchestration.context_orchestrator import ContextOrchestrator
from context_orchestration.context_source import ContextSource
from context_orchestration.orchestration_plan import ContextOrchestrationPlan

from persistent_memory.persistent_memory_manager import PersistentMemoryManager
from persistent_memory.persistent_memory_record import PersistentMemoryDomain, PersistentMemoryStorageScope, classify_memory_consent

from runtime_observation.observation_collector import RuntimeObservationCollector
from runtime_observation.observation_record import RuntimeObservationRecord, generate_observation_id, utc_now_iso
from understanding import UnderstandingEngine, UnderstandingRequest, AuthorityContext, AuthorityLevel

from knowledge.knowledge_classifier import KnowledgeClassifier
from knowledge.knowledge_domain import KnowledgeClassification, KnowledgeDomain
from knowledge.knowledge_router import KnowledgeRoute, KnowledgeRouter
from integration.mode_runtime_hooks import attach_bridge, process_supervisor_messages

class RuntimeState(str, Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    INTERPRETING = "INTERPRETING"
    CLARIFYING = "CLARIFYING"
    BUILDING = "BUILDING"
    VALIDATING = "VALIDATING"
    HALTED = "HALTED"
    COMPLETE = "COMPLETE"
    ERROR = "ERROR"


@dataclass
class BootContext:
    identity: OperatorIdentity
    profile: OperatorProfile
    onboarding_state: OnboardingState
    active_thread: ThreadMemory
    temporal_context: TemporalContext
    assembled_context: Optional[AssembledContext] = None
    knowledge_classification: Optional[KnowledgeClassification] = None
    knowledge_route: Optional[KnowledgeRoute] = None
    orchestration_plan: Optional[ContextOrchestrationPlan] = None
    operator_requirement_evaluation: Optional[OperatorRequirementEvaluation] = None
    runtime_observation: Optional[RuntimeObservationRecord] = None
    understanding_result: object = None
    reality_primacy_result: object = None
    runtime_state: RuntimeState = RuntimeState.IDLE


class ModeRuntime:
    def __init__(
        self,
        operator_id: Optional[str] = None,
        operator_storage_dir: str = "data/operators",
        thread_storage_dir: str = "data/threads",
        rp_config: Optional[dict] = None,
        capability_rp_config: Optional[dict] = None,
        objective_rp_config: Optional[dict] = None,
    ) -> None:
        self.operator_id = operator_id
        self.rp_config = rp_config
        self.capability_rp_config = capability_rp_config
        self.objective_rp_config = objective_rp_config
        self._objective_rp_process = None
        self._capability_rp_process = None
        self._rp_process = None
        self.rp_readiness = 'NOT_CONFIGURED'
        self.operator_store = OperatorStore(storage_dir=operator_storage_dir)
        self.thread_store = ThreadStore(storage_dir=thread_storage_dir)

        self.temporal_engine = TemporalEngine()

        self.knowledge_classifier = KnowledgeClassifier()
        self.knowledge_router = KnowledgeRouter()

        self.persistent_memory_manager = PersistentMemoryManager()
        self.operator_requirement_engine = OperatorRequirementEngine(
            persistent_memory_manager=self.persistent_memory_manager,
        )

        self.context_orchestrator = ContextOrchestrator()
        self.context_assembler = ContextAssembler()
        self.runtime_observation_collector = RuntimeObservationCollector()
        self._observation_session_id = generate_observation_id()
        self._observed_transitions = []
        self._retrieved_memory_ids = []
        self.understanding_engine = UnderstandingEngine()

        self.onboarding_engine = OnboardingEngine(
            operator_store=self.operator_store,
            thread_store=self.thread_store,
        )

        self.pending_action = None
        self.pending_action_router = PendingActionRouter()
        from integration.build_runtime import BuildRuntime
        self.build_runtime = BuildRuntime(self)
        
        self.context: Optional[BootContext] = None
        self.supervisor_bridge = None
        self.supervisor_adapter = None
        self.supervisor_task_id = "mode-development"

        self._supervisor_stop_event = threading.Event()
        self._supervisor_thread = None
        self._supervisor_lifecycle_lock = threading.Lock()
        self._interaction_lock = threading.RLock()
    
    def _start_supervisor_listener(self) -> None:
        with self._supervisor_lifecycle_lock:
            self._start_supervisor_listener_locked()

    def _start_supervisor_listener_locked(self) -> None:
        if self._supervisor_thread is not None:
            if self._supervisor_thread.is_alive():
                return

        self._supervisor_stop_event.clear()

        self._supervisor_thread = threading.Thread(
            target=self._supervisor_listener_loop,
            name="mode-supervisor-listener",
            daemon=True,
        )

        self._supervisor_thread.start()

    def _stop_supervisor_listener(self) -> None:
        with self._supervisor_lifecycle_lock:
            self._supervisor_stop_event.set()
            if self._supervisor_thread is not None:
                self._supervisor_thread.join()
                self._supervisor_thread = None


    def _supervisor_listener_loop(self) -> None:
        while not self._supervisor_stop_event.is_set():
            try:
                if (
                    self.supervisor_bridge is not None
                    and self.supervisor_adapter is not None
                ):
                    process_supervisor_messages(
                        self,
                        self.supervisor_task_id,
                        self.supervisor_adapter,
                    )

            except Exception as error:
                print(f"\nSupervisor Bridge Listener Error: {error}")

            self._supervisor_stop_event.wait(0.25)
        
    def boot(self) -> BootContext:
        self._print_header()

        self._print_step("Loading Runtime")
        self._print_success("Runtime Initialized")

        self._print_step("Authenticating Operator")
        resolved_operator_id = self._select_operator_profile()

        identity, profile, onboarding_state = self.onboarding_engine.initialize_operator(
            operator_id=resolved_operator_id
        )

        self.operator_store.set_current_operator_id(identity.operator_id)
        self._print_success("Operator Loaded")

        self._print_step("Loading Profile")
        identity.require_profile_match(profile.operator_id)
        self._print_success("Profile Loaded")

        if onboarding_state.onboarding_required:
            profile, onboarding_state = self._run_operator_onboarding(
                identity=identity,
                profile=profile,
            )

        self._print_step("Loading Active Thread")
        if profile.active_thread_id:
            active_thread = self.thread_store.load_thread(
                operator_id=identity.operator_id,
                thread_id=profile.active_thread_id,
            )
        elif onboarding_state.initial_thread_id:
            active_thread = self.thread_store.load_thread(
                operator_id=identity.operator_id,
                thread_id=onboarding_state.initial_thread_id,
            )
        else:
            active_thread = self.thread_store.get_or_create_active_thread(
                operator_id=identity.operator_id,
            )
        self._print_success("Active Thread Loaded")

        self._print_step("Loading Temporal Awareness")
        temporal_context = self.temporal_engine.build_for_operator(profile)
        self._print_success("Temporal Awareness Loaded")

        self.context = BootContext(
            identity=identity,
            profile=profile,
            onboarding_state=onboarding_state,
            active_thread=active_thread,
            temporal_context=temporal_context,
            runtime_state=RuntimeState.IDLE,
        )
        halted_threads = [thread for thread in self.thread_store.list_threads(identity.operator_id)
                          if getattr(thread, 'halt', None) is not None]
        if halted_threads:
            self._halt_latch = dict(halted_threads[0].halt)
            self.context.runtime_state = RuntimeState.HALTED

        self._print_step("Assembling Product Context")
        self.context.assembled_context = self._assemble_context()

        if self.context.assembled_context.runtime.context_ready:
            self._print_success("Product Context Assembled")
        else:
            self._print_blocked(
                "Product Context Assembly incomplete",
                f"Missing sources: {self.context.assembled_context.runtime.missing_sources}",
            )

        self._print_step("Connecting Interpretation Engine")
        self._print_success("Mode Engine Connected")

        self._print_step("Connecting Supervisor Bridge")
        self.supervisor_bridge, self.supervisor_adapter = attach_bridge(
            self,
            self.supervisor_task_id,
        )
        self._start_supervisor_listener()
        self._print_success("Supervisor Bridge Connected")

        self._print_boot_summary(self.context)
        self._connect_external_rp()
        self._connect_capability_rp()
        self._connect_evidence_rp()
        if self.objective_rp_config is not None:
            from integration.objective_action_rp import connect
            connect(self,self.objective_rp_config)
        return self.context

    def _connect_evidence_rp(self):
        from pathlib import Path
        from integration.rp_process import ExternalRPProcess
        from integration.rp_evidence_state import EvidenceStateClient
        config=getattr(self,'evidence_rp_config',None)
        if config is None:return
        try:
            if set(config)!={'repository','grant','ledger'} or any(not Path(p).is_absolute() for p in config.values()):
                raise ValueError('Operator-provisioned absolute evidence RP paths required')
            self._evidence_rp_process=ExternalRPProcess(**config,module='reality_primacy.evidence_state')
            self.evidence_state_client=EvidenceStateClient(lambda request:self._evidence_rp_process.call('inspect',request),self._evidence_rp_process.public_keys)
        except Exception as exc:
            self.evidence_rp_error=str(exc)

    def _connect_capability_rp(self):
        import os, json
        from pathlib import Path
        from integration.rp_process import ExternalRPProcess
        from system_layer.reality import CapabilityRealityClient
        config = getattr(self, 'capability_rp_config', None)
        try:
            if config is None and os.environ.get('MODE_CAPABILITY_RP_CONFIG'):
                config = json.loads(Path(os.environ['MODE_CAPABILITY_RP_CONFIG']).read_text(encoding='utf-8'))
            if config is None:
                return
            if set(config) != {'repository', 'grant', 'ledger'} or any(not Path(p).is_absolute() for p in config.values()):
                raise ValueError('Absolute external capability RP configuration paths required')
            process = ExternalRPProcess(**config, module='reality_primacy.capability_audit')
            self._capability_rp_process = process
            self.capability_reality_client = CapabilityRealityClient(
                lambda request: process.call('evaluate', request), process.public_keys)
            if hasattr(self, 'system_layer'):
                self.system_layer.reality_client = self.capability_reality_client
        except Exception as exc:
            self.capability_rp_error = str(exc)
            print('External capability RP unavailable: ' + str(exc))

    def _connect_external_rp(self):
        import os, json
        from pathlib import Path
        from integration.rp_process import ExternalRPProcess
        try:
            config = self.rp_config
            if config is None and os.environ.get('MODE_RP_CONFIG'):
                config = json.loads(Path(os.environ['MODE_RP_CONFIG']).read_text(encoding='utf-8'))
            if config is None:
                return
            if set(config) != {'repository', 'grant', 'ledger'}:
                raise ValueError('RP configuration requires repository, grant and ledger paths')
            if any(not isinstance(value, str) or not Path(value).is_absolute() for value in config.values()):
                raise ValueError('RP configuration paths must be absolute')
            self._rp_process = ExternalRPProcess(**config)
            self._rp_process.attach(self)
            self.rp_readiness = 'READY'
        except Exception as exc:
            self.rp_readiness = 'UNAVAILABLE: ' + str(exc)
            print(self.rp_readiness)

    def shutdown(self):
        if getattr(self,'_objective_rp_process',None) is not None:
            self._objective_rp_process.close();self._objective_rp_process=None
        if getattr(self,'_evidence_rp_process',None) is not None:
            self._evidence_rp_process.close()
            self._evidence_rp_process=None
        if getattr(self, '_frontend_view', None) is not None:
            self._frontend_view.close()
            self._frontend_view = None
        if getattr(self, '_capability_rp_process', None) is not None:
            self._capability_rp_process.close()
            self._capability_rp_process = None
        if hasattr(self, '_supervisor_lifecycle_lock'):
            self._stop_supervisor_listener()
        if getattr(self, '_rp_process', None) is not None:
            self._rp_process.close()
            self._rp_process = None

    def _select_operator_profile(self) -> Optional[str]:
        if self.operator_id:
            return self.operator_id

        profiles = self.operator_store.list_profiles()

        if not profiles:
            print("\nNo existing operator profiles found.")
            return None

        current_operator_id = self.operator_store.get_current_operator_id()

        print("\nExisting operator profiles found:")
        print("-" * 80)

        for index, profile in enumerate(profiles, start=1):
            marker = "last used" if profile.operator_id == current_operator_id else ""
            status = "complete" if profile.onboarding_complete else "incomplete"

            print(
                f"{index}. {profile.display_name} | "
                f"{profile.timezone or 'NO_TIMEZONE'} | "
                f"{profile.language or 'NO_LANGUAGE'} | "
                f"{status} | {profile.operator_id} {marker}"
            )

        print("\nN. Create new operator profile")

        while True:
            choice = input("\nSelect operator profile number or N:\n> ").strip().lower()

            if choice == "n":
                self.operator_store.clear_current_operator_id()
                return None

            if choice.isdigit():
                selected_index = int(choice)

                if 1 <= selected_index <= len(profiles):
                    selected_profile = profiles[selected_index - 1]

                    confirm = input(
                        f"\nUse profile '{selected_profile.display_name}' "
                        f"({selected_profile.operator_id})? [Y/n]\n> "
                    ).strip().lower()

                    if confirm in {"", "y", "yes"}:
                        return selected_profile.operator_id

                    continue

            print("Invalid selection.")

    def _run_operator_onboarding(
        self,
        identity: OperatorIdentity,
        profile: OperatorProfile,
    ) -> tuple[OperatorProfile, OnboardingState]:
        print("\n" + "-" * 80)
        print("Operator Onboarding Required")
        print("-" * 80)
        print("Mode needs basic operator-managed information before chat starts.")

        preferred_name = self._ask_required("What should Mode call you?")
        timezone_value = self._ask_timezone()
        language = self._ask_required("What language should Mode use? Example: en")

        profile, onboarding_state = self.onboarding_engine.apply_onboarding_answers(
            identity=identity,
            profile=profile,
            preferred_name=preferred_name,
            timezone=timezone_value,
            language=language,
            name=preferred_name,
        )

        self.operator_store.set_current_operator_id(identity.operator_id)

        self._print_success("Operator Onboarding Complete")
        return profile, onboarding_state

    def _ask_required(self, prompt: str) -> str:
        while True:
            value = input(f"\n{prompt}\n> ").strip()
            if value:
                return value
            print("This field is required.")

    def _ask_timezone(self) -> str:
        while True:
            timezone_value = input(
                "\nWhat timezone should Mode use? "
                "Use IANA format. Examples: America/New_York, Europe/London, Africa/Nairobi\n> "
            ).strip()

            if is_valid_timezone(timezone_value):
                return timezone_value

            print("Invalid timezone. Use a valid IANA timezone like America/New_York.")

    def _assemble_context(self) -> AssembledContext:
        if self.context is None:
            raise RuntimeError("Cannot assemble context before boot context exists.")

        if self.context.knowledge_classification is None:
            self.context.knowledge_classification = self.knowledge_classifier.classify("")

        if self.context.knowledge_route is None:
            self.context.knowledge_route = self.knowledge_router.route(
                self.context.knowledge_classification
            )

        if self.context.operator_requirement_evaluation is None:
            self.context.operator_requirement_evaluation = (
                self.operator_requirement_engine.evaluate(
                    operator_profile=self.context.profile,
                    thread_id=self.context.active_thread.thread_id,
                    input_text="",
                    domain=OperatorRequirementDomain.GENERAL,
                )
            )

        available_sources = self._available_context_sources()

        self.context.orchestration_plan = self.context_orchestrator.build_plan(
            operator_id=self.context.identity.operator_id,
            thread_id=self.context.active_thread.thread_id,
            input_text="",
            classification=self.context.knowledge_classification,
            route=self.context.knowledge_route,
            available_sources=available_sources,
        )

        persistent_memories = self.persistent_memory_manager.retrieve_memories(
            operator_id=self.context.identity.operator_id,
        )

        return self.context_assembler.assemble(
            profile=self.context.profile,
            thread=self.context.active_thread,
            temporal_context=self.context.temporal_context,
            runtime_state=self.context.runtime_state.value,
            orchestration_plan=self.context.orchestration_plan,
            operator_requirement_evaluation=self.context.operator_requirement_evaluation,
            persistent_memories=persistent_memories,
            recent_message_limit=20,
        )

    def _build_knowledge_context(self) -> str:
        if self.context is None or self.context.knowledge_classification is None:
            return ""

        classification = self.context.knowledge_classification
        route = self.context.knowledge_route

        secondary_domains = [domain.value for domain in classification.secondary_domains]

        return (
            "KNOWLEDGE ROUTING:\n"
            f"Primary Domain: {classification.primary_domain.value}\n"
            f"Secondary Domains: {secondary_domains}\n"
            f"Confidence: {classification.confidence}\n"
            f"Reason: {classification.reason}\n"
            f"Requires Runtime Context: {route.requires_runtime_context if route else None}\n"
            f"Allows Public Knowledge: {route.allows_public_knowledge if route else None}\n"
            f"Requires External Source: {route.requires_external_source if route else None}\n"
            f"Requires Private Document: {route.requires_private_document if route else None}\n"
            f"Requires System Context: {route.requires_system_context if route else None}\n"
            f"Allows Inference: {route.allows_inference if route else None}\n"
            f"Unsupported Without Source: {route.unsupported_without_source if route else None}\n"
        )

    def _build_operator_requirement_context(self) -> str:
        if self.context is None or self.context.operator_requirement_evaluation is None:
            return ""

        evaluation = self.context.operator_requirement_evaluation

        return (
            "OPERATOR REQUIREMENTS:\n"
            f"Domain: {evaluation.domain.value}\n"
            f"Can Continue: {evaluation.can_continue()}\n"
            f"Missing Required Fields: {evaluation.missing_required_fields()}\n"
            f"Satisfied Required Fields: {evaluation.satisfied_required_fields()}\n"
        )

    def _build_orchestration_context(self) -> str:
        if self.context is None or self.context.orchestration_plan is None:
            return ""

        plan = self.context.orchestration_plan

        required = set(plan.required_sources())
        blocking_missing = [
            source.value
            for source in plan.missing_sources()
            if source in required
        ]

        return (
            "CONTEXT ORCHESTRATION:\n"
            f"Plan ID: {plan.plan_id}\n"
            f"Context Ready: {plan.context_ready()}\n"
            f"Included Sources: {[source.value for source in plan.included_sources()]}\n"
            f"Required Sources: {[source.value for source in plan.required_sources()]}\n"
            f"Blocking Missing Sources: {blocking_missing}\n"
        )

    def _build_engine_input(self, user_input: str) -> str:
        if self.context is None:
            return user_input

        if hasattr(self,'temporal_engine'):
            self.context.temporal_context=self.temporal_engine.build_for_operator(self.context.profile)

        if self.pending_action is not None:
            result = self.pending_action_router.handle(
                self.pending_action,
                user_input,
            )

        
        self.context.knowledge_classification = self.knowledge_classifier.classify(
            user_input
        )

        self.context.knowledge_route = self.knowledge_router.route(
            self.context.knowledge_classification
        )

        requirement_domain = self._resolve_operator_requirement_domain(
            user_input=user_input,
            classification=self.context.knowledge_classification,
        )

        persistent_memories = self.persistent_memory_manager.retrieve_memories(
            operator_id=self.context.profile.operator_id,
            domain=self._map_requirement_domain_to_memory_domain(requirement_domain),
            query=user_input,
        )
        self._retrieved_memory_ids = [m.memory_id for m in persistent_memories]
        session_answers = getattr(self, "session_answers", {}).get(
            (self.context.profile.operator_id, self.context.active_thread.thread_id), {})

        self.context.operator_requirement_evaluation = (
            self.operator_requirement_engine.evaluate(
                operator_profile=self.context.profile,
                thread_id=self.context.active_thread.thread_id,
                input_text=user_input,
                domain=requirement_domain,
                persistent_memories=persistent_memories,
                session_answers=session_answers,
            )
        )

        available_sources = self._available_context_sources()

        self.context.orchestration_plan = self.context_orchestrator.build_plan(
            operator_id=self.context.identity.operator_id,
            thread_id=self.context.active_thread.thread_id,
            input_text=user_input,
            classification=self.context.knowledge_classification,
            route=self.context.knowledge_route,
            available_sources=available_sources,
        )

        persistent_domain = self._map_requirement_domain_to_memory_domain(
            requirement_domain
        )

        self.context.assembled_context = self.context_assembler.assemble(
            profile=self.context.profile,
            thread=self.context.active_thread,
            temporal_context=self.context.temporal_context,
            runtime_state=self.context.runtime_state.value,
            orchestration_plan=self.context.orchestration_plan,
            operator_requirement_evaluation=self.context.operator_requirement_evaluation,
            persistent_memories=persistent_memories,
            session_answers=session_answers,
            recent_message_limit=20,
            provenance_support=self.persistent_memory_manager.provenance_support(self.context.profile.operator_id,user_input),
            provenance_loader=self.persistent_memory_manager.provenance_support,
        )

        self.persistent_memory_manager.store.record_use(self.context.identity.operator_id,{
            'thread_id':self.context.active_thread.thread_id,'query':user_input,'timestamp':utc_now_iso(),
            'retrieved':[{'memory_id':m.memory_id,'version':m.version,'governance':m.governance_decision.get('decision_id')} for m in persistent_memories],
            'injected':[m.memory_id for m in persistent_memories if m.content in getattr(self.context.assembled_context,'persistent_memory_contents',[])],
            'excluded':[m.memory_id for m in persistent_memories if m.content not in getattr(self.context.assembled_context,'persistent_memory_contents',[])]})

        knowledge_domain = (
            self.context.knowledge_classification.primary_domain
        )

        if knowledge_domain == KnowledgeDomain.PUBLIC:
            knowledge_instruction = (
                "You are Mode Bot. You may use stable, widely accepted public "
                "knowledge in addition to the governed runtime context below.\n"
                "Do not fabricate uncertain, disputed, specialized, or "
                "time-sensitive facts.\n"
            )

            evidence_instruction = (
                "If a public fact is uncertain, disputed, specialized, or "
                "time-sensitive, state the limitation rather than guessing.\n"
            )

        elif knowledge_domain == KnowledgeDomain.EXTERNAL_CURRENT:
            knowledge_instruction = (
                "You are Mode Bot. This request requires current or "
                "time-sensitive external information.\n"
                "Do not present information as current unless validated external "
                "evidence is available in the governed runtime context.\n"
            )

            evidence_instruction = (
                "If validated current external evidence is not available, say that "
                "the current fact cannot be confirmed.\n"
            )

        else:
            knowledge_instruction = (
                "You are Mode Bot. Use only the governed runtime context below "
                "when answering.\n"
            )

            evidence_instruction = (
                "If a fact is not present in the assembled context, say you do not "
                "have evidence for it.\n"
            )

        policy_text = (
            knowledge_instruction
            + "Do not promote unsupported inference to fact.\n"
            + evidence_instruction
            + (
                "If required operator information is missing, ask for it before "
                "continuing.\n"
            )
            + (
                "Keep ordinary new information in this thread. Honor an explicit "
                "session-only scope without asking to persist it. Persistent saving "
                "requires the governed memory operation and actual operator consent; "
                "do not imply a write from conversation alone.\n\n"
            )
        )
        from data_governance.context_admission import Admission,AdmittedPrompt
        admission=Admission(self.context.identity.operator_id,self.context.active_thread.thread_id)
        for kind,text in (('SYSTEM_POLICY',policy_text),('ROUTING',self._build_knowledge_context()+'\n'),
                          ('REQUIREMENTS',self._build_operator_requirement_context()+'\n'),
                          ('ORCHESTRATION',self._build_orchestration_context()+'\n')):
            admission.consider(kind,kind+':current',text,source='ModeRuntime:'+kind)
        admission.include(self.context.assembled_context.to_prompt_context())
        from integration.rp_evidence_state import reasoning_context as rp_evidence_context
        external_evidence=rp_evidence_context(self,user_input)
        if external_evidence is not None:admission.include(external_evidence)
        from integration.runtime_self_inspection import reasoning_context as inspection_context
        inspected=inspection_context(self,user_input)
        if inspected is not None:admission.include(inspected)
        from integration.conversation_understanding import prompt_context as meaning_prompt_context
        admission.include(meaning_prompt_context(self, query=user_input))
        from system_layer.runtime import prompt_context as system_prompt_context
        system_context = system_prompt_context(self)
        if system_context is not None:
            admission.include(system_context)
        from knowledge.runtime_context import prompt_context as knowledge_prompt_context, select_conversation_reference
        select_conversation_reference(self,user_input)
        knowledge_context=knowledge_prompt_context(self)
        if knowledge_context is not None:
            admission.include(knowledge_context)
        from memory.vault_context import prompt_context as vault_prompt_context
        vault_context=vault_prompt_context(self)
        if vault_context is not None:
            admission.include(vault_context)
        learning=self._learning_prompt_advisory()
        if isinstance(learning,AdmittedPrompt):admission.include(learning)
        elif learning:admission.consider('LEARNING','unadmitted-advisory',learning,source='Legacy augmentation')
        else:admission.consider('LEARNING','learning:not-selected','',source='LearningMemoryGateway',selected=False)
        # These runtime objects are consumed by dedicated engines, not copied
        # into the conversational prompt. Any future inclusion needs its policy.
        for kind in ('UNDERSTANDING','KNOWLEDGE','SPECIFICATION','TOOL_RESULT','OBSERVATION','RP_RESULT','GOVERNANCE','RETRIEVED'):
            admission.consider(kind,kind+':not-selected','',source='ModeRuntime',selected=False)
        admission.consider('OPERATOR_INPUT','input:current','CURRENT OPERATOR INPUT:\n'+user_input,source='OperatorInput')
        prompt=admission.finish()
        self.context.context_admission={'decisions':prompt.decisions,
            'injected_ids':[d['artifact_id'] for d in prompt.decisions if d['decision']=='ADMITTED'],
            'prompt_hash':__import__('learning.contracts',fromlist=['digest']).digest(str(prompt))}
        return prompt

    def _build_thread_memory_context(self) -> str:
        if self.context is None:
            return "No runtime context available."

        thread = self.context.active_thread

        if thread is None or not getattr(thread, "messages", None):
            return "No thread memory available."

        obsolete_mode_outputs = (
            "GOVERNANCE HALT: response generation blocked.",
            "RESPONSE_GENERATION_FAILURE",
        )

        lines = [
            "Thread memory is conversational history only.",
            "It is not verified knowledge, authoritative evidence, or active policy.",
            "Current governance, routing, and knowledge classification override "
            "conflicting historical Mode outputs.",
            "Historical Mode responses may reflect superseded runtime behavior.",
            "",
        ]

        for message in thread.messages[-20:]:
            role = str(
                getattr(message, "role", "unknown")
            ).strip().lower()

            content = str(
                getattr(message, "content", "")
            ).strip()

            if not content:
                continue

            if role in ("assistant", "mode") and any(
                marker in content
                for marker in obsolete_mode_outputs
            ):
                continue

            if role in ("user", "operator"):
                lines.append(
                    f"OPERATOR MESSAGE:\n{content}"
                )

            elif role in ("assistant", "mode"):
                lines.append(
                    "HISTORICAL MODE OUTPUT "
                    "(non-authoritative; use only for conversational continuity):\n"
                    f"{content}"
                )

            elif role == "system":
                lines.append(
                    "HISTORICAL SYSTEM MESSAGE "
                    "(not current policy unless reaffirmed by the active runtime):\n"
                    f"{content}"
                )

            else:
                lines.append(
                    f"HISTORICAL {role.upper()} MESSAGE:\n{content}"
                )

            lines.append("")

        if len(lines) == 5:
            return "No usable thread memory available."

        return "\n".join(lines).strip()
    
    def _build_persistent_memory_context(self) -> str:
        # Compatibility accessor: never perform an unrelated second retrieval.
        assembled = getattr(self.context, "assembled_context", None)
        return "\n".join(getattr(assembled, "persistent_memory_contents", []))
    
    def run(self) -> None:
        try:
            self._run()
        finally:
            self.shutdown()

    def _run(self) -> None:
        if self.context is None:
            self.boot()

        assert self.context is not None

        while True:
            owns_interaction = False
            try:
                
                prompt_name = (
                    self.context.profile.operator_managed.preferred_name
                    or self.context.profile.operator_managed.name
                    or "Operator"
                )

                view=getattr(self,'_frontend_view',None)
                if view is not None and view.operator_input:
                    try:user_input=view.next_input().strip()
                    except PermissionError as exc:
                        self._observe_runtime_event('operator_input_rejected',{'execution_started':False,'authorization_state':'REJECTED'},runtime_error=str(exc))
                        self._present_operation_result('/input',None,error_type=type(exc).__name__)
                        continue
                else:user_input=input(f"\n{prompt_name} > ").strip()

                self._interaction_lock.acquire()
                owns_interaction = True
                self._observed_transitions = []
                self._retrieved_memory_ids = []
                self._set_state(RuntimeState.IDLE)

                if not user_input:
                    continue

                if user_input.lower() in {"exit", "quit", "q"}:
                    print("\nMode shutting down.")
                    break

                if self.pending_action is None:
                    if user_input.startswith('/runtime-recover '):
                        import json
                        recovery = json.loads(user_input[len('/runtime-recover '):])
                        print(json.dumps(self.recover_halt(recovery['request'], recovery['approval'])))
                        continue
                    if user_input == '/view':
                        from frontend.runtime_view import snapshot
                        print(__import__('json').dumps(snapshot(self), indent=2))
                        continue
                    if user_input == '/view serve':
                        from frontend.server import RuntimeViewServer
                        if getattr(self, '_frontend_view', None) is None:
                            self._frontend_view = RuntimeViewServer(self)
                        print('Private local runtime view: ' + self._frontend_view.url)
                        continue
                    if user_input == '/view interactive':
                        from frontend.server import RuntimeViewServer
                        prior=getattr(self,'_frontend_view',None)
                        if prior is not None:prior.close()
                        self._frontend_view=RuntimeViewServer(self,operator_input=True)
                        print('Private Operator input view: '+self._frontend_view.url)
                        continue
                    if user_input == '/view export':
                        from frontend.runtime_view import export
                        print(__import__('json').dumps(export(self), indent=2))
                        continue
                    if user_input.startswith(('/vault ', '/documents ', '/knowledge ', '/creative ', '/thread ','/onboarding ')):
                        from integration.content_custody import execute as custody_command
                        try:
                            result=custody_command(self,user_input)
                            self._present_operation_result(user_input,result)
                            print(__import__('json').dumps(result,indent=2))
                        except Exception as exc:
                            self._present_operation_result(user_input,None,error_type=type(exc).__name__)
                            print(f'Custody operation blocked: {type(exc).__name__}: {exc}')
                        continue
                    if user_input.startswith('/system '):
                        from system_layer.runtime import execute as system_command
                        try:
                            result=system_command(self,user_input)
                            self._present_operation_result(user_input,result)
                            print(__import__('json').dumps(result, indent=2))
                        except Exception as exc:
                            self._present_operation_result(user_input,None,error_type=type(exc).__name__)
                            print(f'System Layer command blocked: {type(exc).__name__}: {exc}')
                        continue
                    if user_input.startswith('/governance diagnostics'):
                        from data_governance.diagnostics import inspect
                        identity=user_input[len('/governance diagnostics'):].strip() or None
                        print(__import__('json').dumps(inspect(self,identity),indent=2));continue
                    if user_input.startswith('/memory '):
                        from integration.memory_commands import execute as memory_command
                        try:
                            result=memory_command(self,user_input)
                            self._present_operation_result(user_input,result)
                            print(__import__('json').dumps(result,indent=2))
                        except Exception as exc:
                            self._present_operation_result(user_input,None,error_type=type(exc).__name__)
                            print(f'Memory lifecycle blocked: {type(exc).__name__}: {exc}')
                        continue
                    if user_input.startswith('/learning '):
                        from learning.runtime import command
                        try:
                            result=command(self,user_input)
                            self._present_operation_result(user_input,result)
                            print(__import__('json').dumps(result, indent=2))
                        except Exception as exc:
                            self._present_operation_result(user_input,None,error_type=type(exc).__name__)
                            print(f'Learning command blocked: {type(exc).__name__}: {exc}')
                            self._observe_runtime_event('governance_failure',{'error':str(exc),'authorization_state':'REJECTED'})
                        continue
                    build_outcome = self.handle_build_request(user_input)
                    if build_outcome is not None:
                        import json
                        self._record_command_exchange(user_input, json.dumps(build_outcome, ensure_ascii=False))
                        print(json.dumps(build_outcome, indent=2, ensure_ascii=False))
                        continue

                if self.pending_action is None:
                    from integration.conversational_memory import execute as memory_request
                    memory_result=memory_request(self,user_input)
                    if memory_result is not None:
                        self._record_command_exchange(user_input,memory_result['message'])
                        self._present_operation_result('/memory',memory_result)
                        print(memory_result['message'])
                        continue

                if self.pending_action is None and "save" in user_input.lower() and "persistent memory" in user_input.lower():
                    if classify_memory_consent(user_input) == "REJECTED":
                        self._record_command_exchange(user_input, "No persistent memory saved; your statement remains in this thread.")
                        self._observe_runtime_event("memory_refusal", {"authorization_state": "REJECTED", "persistent_saved": False})
                        self._present_operation_result('/memory',{'state':'REJECTED','persistent_saved':False})
                        print("No persistent memory saved; your statement remains in this thread.")
                        continue
                    self.pending_action = create_memory_save_pending_action(
                        memory_text=user_input
                    )
                    self._record_command_exchange(user_input, "Memory proposal pending explicit consent; no persistent save performed.")
                    self._observe_runtime_event("memory_proposal", {"authorization_state": "PENDING", "persistent_saved": False,
                        "operation_id": self.pending_action.action_id,
                        "content_sha256": __import__('hashlib').sha256(user_input.encode('utf-8')).hexdigest()})
                    print(f"Proposed memory (unchanged operator input):\n{user_input}\n"
                          "Save this exact content? Yes = persistent; no = cancel; session-only = no persistent storage.")
                    continue
                
                if self.pending_action is not None:
                    result = self.pending_action_router.handle(
                        self.pending_action,
                        user_input,
                    )

                    if result.get("complete") and result.get("action") == "SAVE_MEMORY":
                        memory_action_id = self.pending_action.action_id
                        operation = self.persistent_memory_manager.propose_create_memory(
                            operator_id=self.context.profile.operator_id,
                            content=result["memory_text"],
                            source_thread_id=self.context.active_thread.thread_id,
                            source_message_id=self.pending_action.action_id,
                            original_operator_statement=result["memory_text"],
                            storage_scope=PersistentMemoryStorageScope(result["storage_scope"]),
                        )

                        if operation.requires_confirmation:
                            operation = self.persistent_memory_manager.confirm_candidate(
                                candidate=operation.candidate,
                                operator_confirmation=result["operator_confirmation"],
                            )

                        self.pending_action = None

                        if operation.session_only_payload:
                            if not hasattr(self, "session_answers"):
                                self.session_answers = {}
                            key = (self.context.profile.operator_id, self.context.active_thread.thread_id)
                            payload = operation.session_only_payload
                            answers=self.session_answers.setdefault(key, {})
                            if payload['content'] not in answers.values():
                                category=payload['data_category']
                                # A category is not an identity: two GENERAL facts
                                # must not silently overwrite one another.
                                slot=category if category not in answers else category+':'+memory_action_id
                                answers[slot]=payload['content']

                        self._observe_runtime_event("memory_result", {"authorization_state": result.get("authorization_state"),
                            "scope": result.get("storage_scope"), "memory_id": operation.record.memory_id if operation.record else None,
                            "operation_id": memory_action_id,
                            "content_sha256": __import__('hashlib').sha256(result['memory_text'].encode('utf-8')).hexdigest(),
                            "receipt_id": operation.receipt.receipt_id if operation.receipt else None,
                            "receipt_status": operation.receipt.status if operation.receipt else None,
                            "receipt_evidence": operation.receipt.evidence_projection() if operation.receipt else None,
                            "authority_source": "data_governance.memory_governance" if operation.record else "pending_action_router",
                            "authority_reference": operation.record.governance_decision['decision_id'] if operation.record else memory_action_id,
                            "record_references": [operation.record.governance_decision['decision_id']] if operation.record else [],
                            "success": operation.success,
                            "persistent_saved": operation.record is not None,
                            "session_only": bool(operation.session_only_payload), "result": operation.message},
                            runtime_error='MEMORY_OPERATION_FAILED' if not operation.success and result.get('authorization_state') == 'APPROVED' else None)
                        print(operation.message)
                        self._record_command_exchange(user_input, operation.message)
                        self._present_operation_result('/memory',operation.to_dict())

                        if operation.record:
                            print(f"Saved Memory ID: {operation.record.memory_id}")

                        continue
                    self._observe_runtime_event("memory_clarification", {"authorization_state": "AMBIGUOUS", "persistent_saved": False,
                        "operation_id": self.pending_action.action_id})
                    print(result.get("message", "No save performed; clarification required."))
                    self._record_command_exchange(user_input, result.get("message", "No save performed; clarification required."))
                    self._present_operation_result('/memory',{'state':'CLARIFICATION_REQUIRED','persistent_saved':False,'message':result.get('message')})
                    continue
                
                self._set_state(RuntimeState.LISTENING)

                self.context.active_thread.add_message(
                    role="operator",
                    content=user_input,
                    metadata={"runtime_state": self.context.runtime_state.value},
                )
                self.thread_store.save_thread(self.context.active_thread)

                runtime_state_start = self.context.runtime_state.value
                self._set_state(RuntimeState.INTERPRETING)

                observation_started = time.monotonic()
                from integration.self_inspection_activation import classify as inspection_scope
                inspection_turn=inspection_scope(user_input) is not None
                from integration.conversation_understanding import prepare as prepare_meaning
                if not inspection_turn:prepare_meaning(self,user_input)
                else:self._prepared_understanding_result=None
                engine_input = self._build_engine_input(user_input)

                print("\nDEBUG ENGINE INPUT")
                print("=" * 80)
                print(engine_input)
                print("=" * 80)

                from integration.objective_action_rp import handles,continue_objective
                if handles(self,user_input):
                    outcome=continue_objective(self,user_input,engine_input)
                    # Bounded continuation returned an explicit stop, not a
                    # clarification question or an objective-completion claim.
                    self._set_state(RuntimeState.IDLE)
                    self.context.active_thread.add_message(role='mode',content=__import__('json').dumps(outcome,ensure_ascii=False),metadata={'route':'objective_rp','action_executed':outcome.get('action_executed',False)})
                    self.thread_store.save_thread(self.context.active_thread)
                    self._present_operation_result('/objective-rp',outcome)
                    print(__import__('json').dumps(outcome,ensure_ascii=False,indent=2))
                    continue
                from data_governance.response_gate import governed_interaction
                from runtime_observation.transformation_provenance import recording, emit
                with recording(self.context.identity.operator_id,self.context.active_thread.thread_id,
                        store=getattr(self,'transformation_store',None)) as provenance:
                    result = governed_interaction(self,
                        OperatorInput(
                            raw_input=user_input,
                            session_id=self.context.active_thread.thread_id,
                            timestamp=datetime.now(timezone.utc).isoformat(),
                            input_source="interactive_mode_bot",
                        ),
                        reasoning_input=engine_input,
                        processor=process_interaction,
                    )
                response_gate=self.context.response_governance

                phase_before = self.context.runtime_state.value
                if result.halt_required:
                    self._set_state(RuntimeState.HALTED)
                elif result.clarification_required:
                    self._set_state(RuntimeState.CLARIFYING)
                else:
                    self._set_state(RuntimeState.COMPLETE)

                with recording(self.context.identity.operator_id,self.context.active_thread.thread_id,
                        interaction=result.interaction_id,store=getattr(self,'transformation_store',None)) as phase_provenance:
                    emit(component='interactive_mode_ai',stage='ModeRuntime.run:post_controller_phase',
                        prior={'runtime_phase':phase_before},event={'kind':'InteractionProcessingResult'},
                        context={'clarification_required':result.clarification_required,'halt_required':result.halt_required,
                                 'publication_gate':{k:response_gate.get(k) for k in ('decision','allowed','reasons')}},
                        rules='halt_required -> HALTED; else clarification_required -> CLARIFYING; else COMPLETE',
                        transformation='select_runtime_phase_from_public_result',result={'runtime_phase':self.context.runtime_state.value},
                        evidence={'trace_path':result.trace_reference},consumers=['RuntimeObservationCollector.collect'])
                response_text = result.response_text or "NO_RESPONSE_TEXT"
                for disclosure in response_gate['disclosures']:
                    print('GOVERNANCE NOTICE: '+disclosure)

                observation = self.runtime_observation_collector.collect(
                    operator_id=self.context.identity.operator_id,
                    thread_id=self.context.active_thread.thread_id,
                    input_text=user_input,
                    response_text=response_text,
                    runtime_state_start=runtime_state_start,
                    runtime_state_end=self.context.runtime_state.value,
                    knowledge_domain=(
                        self.context.knowledge_classification.primary_domain.value
                        if self.context.knowledge_classification
                        else "UNKNOWN"
                    ),
                    orchestration_plan=self.context.orchestration_plan,
                    context_ready=(
                        self.context.assembled_context.runtime.context_ready
                        if self.context.assembled_context
                        else False
                    ),
                    trace_reference=result.trace_reference,
                    runtime_error=getattr(result, "failure_state", None) or ("Controller returned unsuccessful result" if not result.success else None),
                    metadata={
                        **self._observation_metadata(result),
                        "context_admission":getattr(self.context,'context_admission',None),
                        "self_inspection":getattr(self.context,'self_inspection',None),
                        "transformation_recording_errors":provenance['errors']+phase_provenance['errors'],
                        "reasoning_context_admission":getattr(result,'context_admission',[]),
                        "response_governance":getattr(self.context,'response_governance',None),
                        "execution_time": time.monotonic() - observation_started,
                        "pre_execution_state": runtime_state_start,
                        "operator_requirement_evaluation": (
                            self.context.operator_requirement_evaluation.to_dict()
                            if self.context.operator_requirement_evaluation
                            else None
                        ),
                        "interaction_id": result.interaction_id,
                        "reasoning_id": result.reasoning_id,
                        "interpreted_intent": {
                            "selected_mode": getattr(result.interaction_manifest, "selected_mode", None),
                            "selected_posture": getattr(result.interaction_manifest, "selected_posture", None),
                            "halt_required": result.halt_required,
                            "clarification_required": result.clarification_required,
                        },
                        "provider_request_telemetry": (
                            result.provider_request_telemetry
                        ),
                        "telemetry_evidence_references": (
                            result.telemetry_evidence_references
                        ),
                        "telemetry_persistence_errors": (
                            result.telemetry_persistence_errors
                        ),
                    },
                )
                if observation.collection_errors:
                    print(f"Observation incomplete: {observation.collection_errors}")
                self.context.runtime_observation = observation
                with recording(observation.operator_id,observation.thread_id,interaction=result.interaction_id,
                        store=getattr(self,'transformation_store',None),
                        correlation={'observation_id':observation.observation_id,'trace_path':result.trace_reference}) as understanding_provenance:
                    observation.metadata['understanding_provenance_errors']=understanding_provenance['errors']
                    if not inspection_turn:
                        self.context.understanding_result = self._understand_observation(observation)
                from integration.interaction_learning import evaluate as evaluate_learning
                if not inspection_turn:
                    evaluate_learning(self,observation,getattr(self,'_governed_interaction_package',None))
                self._governed_interaction_package=None

                self.context.active_thread.add_message(
                    role="mode",
                    content=response_text,
                    metadata={
                        "runtime_state": self.context.runtime_state.value,
                        "knowledge_domain": (
                            self.context.knowledge_classification.primary_domain.value
                            if self.context.knowledge_classification
                            else None
                        ),
                        "knowledge_reason": (
                            self.context.knowledge_classification.reason
                            if self.context.knowledge_classification
                            else None
                        ),
                        "selected_posture": (
                            result.interaction_manifest.selected_posture
                            if result.interaction_manifest
                            else None
                        ),
                        "ambiguity_score": (
                            result.interaction_manifest.ambiguity_score
                            if result.interaction_manifest
                            else None
                        ),
                        "trace_reference": result.trace_reference,
                        "runtime_observation_id": observation.observation_id,
                        "orchestration_plan_id": (
                            self.context.orchestration_plan.plan_id
                            if self.context.orchestration_plan
                            else None
                        ),
                        "operator_requirements_can_continue": (
                            self.context.operator_requirement_evaluation.can_continue()
                            if self.context.operator_requirement_evaluation
                            else None
                        ),
                    },
                )
                self.thread_store.save_thread(self.context.active_thread)

                print("\n" + "=" * 80)
                print("MODE RESPONSE")
                print("=" * 80)
                print(response_text)
                if (self.context.understanding_result is not None
                        and self.context.understanding_result.state != "NO_RELEVANT_UNDERSTANDING"):
                    print("\n" + self.context.understanding_result.explain())

                print("\nRUNTIME")
                print("-" * 80)
                print(f"State      : {self.context.runtime_state.value}")

                if result.interaction_manifest:
                    print(f"Mode       : {result.interaction_manifest.selected_mode}")
                    print(f"Posture    : {result.interaction_manifest.selected_posture}")
                    print(f"Ambiguity  : {result.interaction_manifest.ambiguity_score}")

                if self.context.assembled_context:
                    print(f"Context    : {self.context.assembled_context.runtime.context_ready}")

                if self.context.knowledge_classification:
                    print(
                        f"Knowledge  : {self.context.knowledge_classification.primary_domain.value}"
                    )
                    print(f"K Reason   : {self.context.knowledge_classification.reason}")

                if self.context.orchestration_plan:
                    print(f"Plan       : {self.context.orchestration_plan.plan_id}")

                if self.context.operator_requirement_evaluation:
                    print(
                        "Requirements: "
                        f"{self.context.operator_requirement_evaluation.can_continue()}"
                    )

                print(f"Observation: {observation.observation_id}")
                print(f"Trace      : {result.trace_reference}")

            except KeyboardInterrupt:
                print("\n\nMode interrupted. Shutting down.")
                break

            except Exception as error:
                if not owns_interaction:
                    self._interaction_lock.acquire()
                    owns_interaction = True
                self._set_state(RuntimeState.ERROR)
                self._observe_runtime_event("runtime_exception", {"error": str(error)}, runtime_error=str(error))
                print(f"\nMode Runtime Error: {error}")
            finally:
                if owns_interaction:
                    self._interaction_lock.release()

    def _observation_metadata(self, result):
        """Capture returned runtime values, never infer retrieval from a plan."""
        assembled = self.context.assembled_context
        plan = self.context.orchestration_plan
        route = self.context.knowledge_route
        loaded = []
        if assembled:
            for attribute, source in (("operator", "OPERATOR_PROFILE"), ("temporal", "TEMPORAL_CONTEXT"), ("thread", "THREAD_MEMORY")):
                if getattr(assembled, attribute, None) is not None: loaded.append(source)
            if getattr(assembled, "persistent_memory_contents", []): loaded.append("PERSISTENT_MEMORY")
            if getattr(assembled, "session_answers", {}): loaded.append("SESSION_ANSWERS")
        telemetry = getattr(result, "provider_request_telemetry", []) or []
        manifest = getattr(result, "interaction_manifest", None)
        authority = getattr(manifest, "downstream_authority_allowed", None)
        return {
            **(route.observation_metadata() if route else {}),
            "runtime_session_id": getattr(self, "_observation_session_id", ""),
            "correlation_id": result.interaction_id,
            "runtime_component": "interactive_mode_ai", "affected_runtime_stage": "interaction_result",
            "acting_identity": self.context.identity.operator_id,
            "actor_roles": [{"identity": self.context.identity.operator_id, "role": "operator"}],
            "participating_components": ["core.mode_controller", "context_assembly", "knowledge.knowledge_router"],
            "executed_components": ["core.mode_controller"],
            "loaded_context_sources": loaded,
            "requested_context_sources": [x.source.value for x in plan.source_selections] if plan else [],
            "missing_context_sources": list(assembled.runtime.missing_sources) if assembled else [],
            "accessed_dependencies": list(getattr(self, "_retrieved_memory_ids", [])),
            "memory_hits": len(getattr(self, "_retrieved_memory_ids", [])),
            "intermediate_states": list(getattr(self, "_observed_transitions", [])),
            "completed_transitions": list(getattr(self, "_observed_transitions", [])),
            "post_execution_state": self.context.runtime_state.value,
            "state_source_references": [result.trace_reference] if result.trace_reference else [],
            "authority_source": "core.mode_controller",
            "authority_decision_source": result.trace_reference,
            "authority_decision": "ALLOW" if authority is True else "DENY" if authority is False else None,
            "completion_claim": {"controller_success": result.success},
            "observed_outcome": {"response_returned": bool(result.response_text), "failure_state": result.failure_state},
            "resource_usage": telemetry,
            "evidence_sources": ["core.mode_controller", "knowledge.knowledge_router", "context_assembly"],
            "source_traces": [result.trace_reference] if result.trace_reference else [],
            "evidence_timestamps": [utc_now_iso()],
            "evidence_ids": list(getattr(result, "telemetry_evidence_references", []) or []),
            "operator_message_count": 1,
            "clarification_count": int(result.clarification_required),
            "required_evidence_fields": ["acting_identity", "observed_outcome", "loaded_context_sources", "validation_results"],
        }

    def _observe_runtime_event(self, name, payload, runtime_error=None):
        # Passive side channel: preserve the governed operation's behavior even if
        # Observation storage fails. Diagnostics are visible to the operator.
        try:
            reference = generate_observation_id()
            source_trace = payload.get('trace_reference')
            authorization = payload.get("authorization_state")
            decision = {"APPROVED": "ALLOW", "REJECTED": "DENY", "PENDING": "DEFER", "AMBIGUOUS": "DEFER"}.get(authorization)
            authority_reference = payload.get('authority_reference')
            record = self.runtime_observation_collector.collect(
                operator_id=self.context.identity.operator_id,
                thread_id=self.context.active_thread.thread_id,
                runtime_state_end=self.context.runtime_state.value,
                trace_reference=source_trace or reference, runtime_error=runtime_error,
                metadata={"runtime_component": "interactive_mode_ai", "affected_runtime_stage": name,
                    "runtime_session_id": getattr(self, "_observation_session_id", ""),
                    "observed_outcome": payload, "evidence_sources": [name],
                    "inline_event_reference": reference,
                    "trace_reference_kind": "SUPPLIED_TRACE" if source_trace else "INLINE_RUNTIME_EVENT",
                    "acting_identity": self.context.identity.operator_id,
                    "authority_decision": decision,
                    "authority_source": payload.get('authority_source') or ("persistent_memory_manager" if name == "memory_lifecycle" else "pending_action_router" if name.startswith("memory_") else "supervisor_bridge" if name.startswith("supervisor_") else None),
                    "authority_scope": payload.get("scope"),
                    "authority_request": payload.get('operation_id'),
                    "authority_decision_source": authority_reference if decision else None,
                    "authorization_receipts": [{"reference": authority_reference, "authorization_state": authorization}] if authorization and authority_reference else [],
                    "source_components": [name],
                    "evidence_ids": payload.get('record_references',[]),
                    "output_artifacts": payload.get('output_artifacts',[]),
                    "produced_receipts": [payload['receipt_id']] if payload.get('receipt_id') else [],
                      "correlation_id": payload.get("operation_id") or payload.get("message_id") or reference,
                    "downstream_execution_references": [payload["trace_reference"]] if payload.get("trace_reference") else [],
                    "evidence_timestamps": [utc_now_iso()], "source_traces": [source_trace] if source_trace else [],
                    "required_evidence_fields": ["observed_outcome"],
                    **({"correlation_id": payload["request"]["request_id"],
                        "evidence_reference": payload.get("receipt_id"),
                        "validation_references": [payload["decision_id"]] if payload.get("decision_id") else [],
                        "validation_results": [{'source':'External Reality Primacy','state':payload.get('rp_state'),'decision_id':payload.get('decision_id')}] if payload.get('decision_id') else [],
                        "produced_receipts": [payload['receipt_id']] if payload.get('receipt_id') else [],
                        "transition_receipts": [payload["response"]["body"]["show_chain"]["structured"]["receipt"]] if payload.get("receipt_id") else [],
                        "attempted_transitions": [{"source_state": payload["request"]["source_state"], "target_state": payload["request"]["target_state"]}],
                        "rejected_transitions": [] if payload.get("accepted") else [payload["request"]["request_id"]]}
                       if name == "reality_primacy_transition" else {})})
            from system_layer.contracts import digest
            persisted=self.runtime_observation_collector.store.load_record(record.operator_id,record.observation_id)
            if record.collection_errors or persisted is None or digest(persisted.to_dict())!=digest(record.to_dict()):
                raise OSError('Runtime event Observation was not persisted and retrieved')
            if hasattr(self,'understanding_engine'):
                try:
                    from integration.interaction_learning import evaluate
                    evaluate(self,record)
                except Exception as exc:
                    self.context.learning_error=f'Interaction evaluation failed: {exc}'
                    print(self.context.learning_error)
            return record
        except Exception as exc:
            print(f"Observation collection failed: {type(exc).__name__}: {exc}")

    def _understand_observation(self, observation):
        """Observe first, then govern meaning. Never grants construction authority."""
        prepared=getattr(self,'_prepared_understanding_result',None)
        preparation=getattr(getattr(self,'context',None),'conversation_understanding',{})
        from understanding.understanding_record import digest as meaning_digest
        if (prepared is not None and preparation.get('input_hash')==meaning_digest(observation.input_text)
                and preparation.get('thread_id')==observation.thread_id):
            result=prepared
            from runtime_observation.transformation_provenance import emit
            emit(component='interactive_mode_ai',stage='ModeRuntime._understand_observation:prepared_result',
                prior={'observation_understanding':'UNAVAILABLE'},event={'kind':'reuse_prepared_result'},
                context={'input_hash_matches':True,'thread_matches':True},
                rules='prepared result and matching input_hash/thread_id -> reuse; do not reevaluate',
                transformation='reuse_prepared_UnderstandingResult',
                result={'state':result.state,'readiness':result.specification_readiness.value},
                correlation={'understanding_request_id':result.request_id})
        else:
            result = self.understanding_engine.process(UnderstandingRequest(
            operator_id=observation.operator_id, thread_id=observation.thread_id,
            current_input=observation.input_text, runtime_observation=observation,
            authority_context=AuthorityContext(observation.operator_id,
                AuthorityLevel.DIRECT_OPERATOR_STATEMENT, "OPERATOR", authenticated=True),
            relevant_context={"knowledge_domain": observation.knowledge_domain, "observation_evidence": observation.to_dict()},
            runtime_metadata={"interpreted_intent": observation.metadata.get("interpreted_intent", {})},
        ))
        # The original observation was already persisted. Append trace references
        # without promoting the response or observation itself to semantic truth.
        observation.metadata["understanding"] = {
            "request_id": result.request_id,
            "understanding_id": result.final_understanding.understanding_id if result.final_understanding else None,
            "transition_id": result.transition.transition_id if result.transition else None,
            "state": result.state, "readiness": result.specification_readiness.value,
            "producer": "understanding.understanding_engine.UnderstandingEngine.process",
            "warnings": list(result.warnings),
            "errors": result.errors, "retry_information": result.retry_information,
        }
        try:
            observation.updated_at = utc_now_iso()
            self.runtime_observation_collector.store.save_record(observation)
        except Exception as exc:
            # Observation's original persisted version and Understanding's source
            # reference remain intact if the reverse-link write fails.
            result.warnings.append(f"Observation reverse-link persistence failed: {type(exc).__name__}: {exc}")
        return result

    def _available_context_sources(self) -> set[ContextSource]:
        return {
            ContextSource.OPERATOR_PROFILE,
            ContextSource.THREAD_MEMORY,
            ContextSource.TEMPORAL_CONTEXT,
            ContextSource.RUNTIME_STATE,
            ContextSource.KNOWLEDGE_ROUTING,
            ContextSource.PERSISTENT_MEMORY,
        }

    def _resolve_operator_requirement_domain(
        self,
        *,
        user_input: str,
        classification: KnowledgeClassification,
    ) -> OperatorRequirementDomain:
        # The classifier's explanation is routing metadata, not an Operator
        # request. Do not turn its mention of system architecture into missing
        # engineering fields for every greeting addressed to Mode.
        text = user_input.lower()

        if any(marker in text for marker in ("health", "weight", "medical", "workout", "fitness")):
            return OperatorRequirementDomain.HEALTH

        import re
        # A file/path token such as organized/assets/ is task data, not a
        # financial subject. Keep genuine standalone financial terms intact.
        financial_text = re.sub(r'\S*[/\\]\S*', ' ', text)
        if re.search(r'\b(?:financial|money|income|budget|debt|assets?)\b', financial_text):
            return OperatorRequirementDomain.FINANCIAL_PLANNING

        if any(marker in text for marker in ("legal", "law", "court", "case", "jurisdiction")):
            return OperatorRequirementDomain.LEGAL_ASSISTANCE

        # Domain requirements follow requested subject/intent, not incidental
        # substrings in a path or technical governance instruction. In
        # particular Learning is also a MODE subsystem, not a human goal.
        education_subject = re.search(
            r'\b(?:education(?:al)?|school|students?|courses?|curriculum|homework|exams?|'
            r'grade[ -]level)\b', financial_text)
        learning_intent = re.search(
            r'\b(?:teach|tutor)\s+(?:me|us|my\s+child)\b|'
            r'\b(?:i|we)\s+(?:(?:want|need)\s+to\s+|am\s+|are\s+)?(?:learn|learning|study|studying)\b|'
            r'\bhelp\s+(?:me|us|my\s+child)\s+(?:to\s+)?(?:learn|study)\b|'
            r'^(?:please\s+)?(?:learn|study)\b|\b(?:my|our)\s+learning\s+(?:goals?|plan)\b',
            financial_text)
        if education_subject or learning_intent:
            return OperatorRequirementDomain.EDUCATION

        if __import__('re').search(r'^(?:please\s+)?(?:help me\s+)?(?:build|implement|construct|design|engineer)\b',text.strip()):
            return OperatorRequirementDomain.ENGINEERING

        if any(marker in text for marker in ("enterprise", "workflow", "organization", "approval chain", "compliance")):
            return OperatorRequirementDomain.ENTERPRISE_WORKFLOW

        return OperatorRequirementDomain.GENERAL

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

    def _present_operation_result(self,text,result,*,error_type=None):
        """Same result as the Operator command surface, scoped to the current view."""
        from copy import deepcopy
        from system_layer.contracts import digest
        value={'contract':'ModeOperationView/1','command':text.partition(' ')[0],
            'operator_id':self.context.identity.operator_id,'thread_id':self.context.active_thread.thread_id,
            'state':'FAILED' if error_type else 'RETURNED','error_type':error_type,
            'result':deepcopy(result),'execution_authority':False}
        value['view_hash']=digest(value)
        self.context.operation_view=value

    def _record_command_exchange(self, text, response):
        """Retain command custody in the same thread as ordinary conversation.

        Thread retention is not Persistent Memory or Vault authorization.
        """
        thread = self.context.active_thread
        thread.add_message(role="operator", content=text, metadata={"route": "command"})
        thread.add_message(role="mode", content=response, metadata={"route": "command"})
        self.thread_store.save_thread(thread)

    def handle_build_request(self, text):
        """Return a structured build outcome, or None for ordinary conversation."""
        if not hasattr(self, "build_runtime"):
            from integration.build_runtime import BuildRuntime
            self.build_runtime = BuildRuntime(self)
        outcome = self.build_runtime.route(text)
        return self._capture_build_outcome(outcome)

    def _capture_build_outcome(self, outcome):
        """Shared governed capture for ordinary and System Layer builds."""
        if outcome is not None and outcome.get('build'):
            from learning.runtime import capture
            try:
                capture(self, outcome)
                print('Learning candidate captured for review; no Learning approval granted.')
            except Exception as exc:
                self.context.learning_error = f'{type(exc).__name__}: {exc}'
                print('Learning capture blocked: ' + self.context.learning_error)
        return outcome

    def _learning_prompt_advisory(self):
        from learning.runtime import prompt_advisory
        # Failure blocks advisory use, never silently substitutes stale learning.
        try:
            return prompt_advisory(self)
        except Exception as exc:
            self.context.learning_error = f'{type(exc).__name__}: {exc}'
            return '\nLearning advisory unavailable: integrity or applicability check failed.\n'

    def require_reality_transition(self, state, request):
        """Register a governed reality dependency; operational states alone prove nothing."""
        from copy import deepcopy
        if not hasattr(self, "_reality_requirements"): self._reality_requirements = {}
        self._reality_requirements[state.value] = deepcopy(request)

    def _set_state(self, state: RuntimeState) -> bool:
        if self.context is not None:
            previous = getattr(getattr(self.context, "runtime_state", None), "value", None)
            stored = getattr(self.context.active_thread, 'halt', None)
            if stored is not None and not getattr(self, '_halt_latch', None):
                self._halt_latch = dict(stored)
            if getattr(self, '_halt_latch', None) and state != RuntimeState.HALTED:
                self.context.runtime_state = RuntimeState.HALTED
                return False
            if state == RuntimeState.HALTED and not getattr(self, '_halt_latch', None):
                from uuid import uuid4
                self._halt_latch = {'halt_id': uuid4().hex,
                    'operator_id': self.context.identity.operator_id,
                    'thread_id': self.context.active_thread.thread_id, 'created_at': utc_now_iso()}
                self.context.runtime_state = RuntimeState.HALTED
                self.context.active_thread.halt = dict(self._halt_latch)
                if hasattr(self, 'thread_store'):
                    self.thread_store.save_thread(self.context.active_thread)
            request = getattr(self, "_reality_requirements", {}).get(state.value)
            if request is not None:
                from copy import deepcopy
                request = deepcopy(request)
                scope = request.get("scope", {})
                client = getattr(self, "reality_acceptance_client", None)
                if (client is None or request.get("source_state") != previous or request.get("target_state") != state.value
                        or scope.get("operator_id") != self.context.identity.operator_id
                        or scope.get("thread_id") != self.context.active_thread.thread_id):
                    outcome = {"accepted": False, "rp_state": None, "request": request,
                               "reason": "Missing external RP client or runtime scope/state mismatch"}
                else:
                    outcome = client.evaluate(request)
                self.context.reality_primacy_result = deepcopy(outcome)
                observation = self._observe_runtime_event("reality_primacy_transition", outcome)
                if observation is not None: self.context.runtime_observation = observation
                engine = getattr(self, "understanding_engine", None)
                if engine is not None: engine.receive_rp_outcome(outcome)
                if observation is not None and engine is not None:
                    try:
                        from integration.interaction_learning import consume_transition
                        consume_transition(self,observation,outcome)
                    except Exception as exc:
                        self.context.learning_error=f'Governed transition Learning blocked: {exc}'
                        print(self.context.learning_error)
                if not outcome["accepted"]:
                    print(outcome["reason"])
                    return False
            self.context.runtime_state = state
            if not hasattr(self, "_observed_transitions"):
                self._observed_transitions = []
            self._observed_transitions.append({"source_state": previous, "target_state": state.value,
                "source_component": "interactive_mode_ai._set_state", "timestamp": utc_now_iso()})
            return True
        return False

    def recover_halt(self, request, approval):
        """Exact Operator-authorized recovery to IDLE; grants no build/RP authority."""
        from system_layer.contracts import authorize
        halt = getattr(self, '_halt_latch', None) or getattr(self.context.active_thread, 'halt', None)
        if (not halt or request != {'halt': halt, 'target_state': 'IDLE'}
                or halt['operator_id'] != self.context.identity.operator_id
                or halt['thread_id'] != self.context.active_thread.thread_id):
            raise PermissionError('Current owner/thread halt must match recovery request')
        authorize(self.context.identity.operator_id, 'RUNTIME_HALT_RECOVERY', request, approval)
        thread = self.context.active_thread
        remaining = []
        if hasattr(self, 'thread_store'):
            remaining = [t for t in self.thread_store.list_threads(self.context.identity.operator_id)
                         if t.halt and t.thread_id != thread.thread_id]
        thread.halt = None
        try:
            if hasattr(self, 'thread_store'): self.thread_store.save_thread(thread)
        except Exception:
            thread.halt = dict(halt)
            self.context.runtime_state = RuntimeState.HALTED
            raise
        self._halt_latch = dict(remaining[0].halt) if remaining else None
        self.context.runtime_state = RuntimeState.HALTED if remaining else RuntimeState.IDLE
        return {'state': self.context.runtime_state.value, 'recovered_halt': halt, 'execution_authority': False}

    def _print_header(self) -> None:
        print("=" * 80)
        print("MODE BOT v0.5")
        print("Governed Interpretation Runtime")
        print("=" * 80)

    def _print_step(self, label: str) -> None:
        print(f"\n{label}...")

    def _print_success(self, label: str) -> None:
        print(f"âœ“ {label}")

    def _print_pending(self, label: str) -> None:
        print(f"âš  {label}")

    def _print_blocked(self, label: str, reason: str) -> None:
        print(f"âœ— {label}")
        print(f"  Reason: {reason}")

    def _print_boot_summary(self, context: BootContext) -> None:
        operator_name = (
            context.profile.operator_managed.preferred_name
            or context.profile.operator_managed.name
            or context.identity.operator_id
        )

        context_ready = (
            context.assembled_context.runtime.context_ready
            if context.assembled_context
            else False
        )

        print("\n" + "-" * 80)
        print("Runtime Capability")
        print("-" * 80)
        print("âœ“ Runtime Initialized")
        print("âœ“ Operator Identity")
        print("âœ“ Operator Profile")
        print("âœ“ Operator Onboarding")
        print("âœ“ Thread Memory")
        print("âœ“ Temporal Awareness")
        print("âœ“ Knowledge Layer")
        print("âœ“ Persistent Memory")
        print("âœ“ Operator Requirement Engine")
        print("âœ“ Context Orchestrator")
        print("âœ“ Product Context Assembly")
        print("âœ“ Runtime Observation")
        print("âœ“ Mode Engine Connected")
        print("-" * 80)
        print(f"Operator    : {operator_name}")
        print(f"Operator ID : {context.identity.operator_id}")
        print(f"Session ID  : {context.identity.session_id}")
        print(f"Thread      : {context.active_thread.thread_id}")
        print(f"Timezone    : {context.temporal_context.timezone}")
        print(f"Date        : {context.temporal_context.current_date}")
        print(f"Time        : {context.temporal_context.current_time}")
        print(f"UTC Offset  : {context.temporal_context.utc_offset}")
        print(f"Context     : {context_ready}")
        print(f"State       : {context.runtime_state.value}")
        print("-" * 80)
        print("\nMode shell is ready.")


def main() -> None:
    runtime = ModeRuntime()
    try:
        runtime.boot()
        runtime.run()
    finally:
        runtime.shutdown()

if __name__ == "__main__":
    main()
