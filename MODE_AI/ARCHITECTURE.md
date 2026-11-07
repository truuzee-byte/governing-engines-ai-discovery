# Architecture and interfaces

October 26, 2026 — source-level map, not capability certification.

| Responsibility | Actual implementation |
|---|---|
| Interactive runtime | `interactive_mode_ai.py`, `core/mode_controller.py` |
| Model stages and telemetry | `agents/reasoning_agent.py`, `runtime_economics/` |
| Versioned meaning and declarations | `understanding/`, `understanding/declaration_delta.py` |
| Observation and read-only inspection | `runtime_observation/`, `integration/runtime_self_inspection.py` |
| Admission and publication gates | `data_governance/`, `integration/conversation_understanding.py` |
| Learning and causal prerequisites | `learning/service.py`, `learning/canonical.py`, `outcome_analysis/`, `integration/interaction_learning.py` |
| Durable learning/memory | `learning/store.py`, `persistent_memory/learning_gateway.py`, `memory/`, `persistent_memory/` |
| Context and relevance | `context_assembly/`, `context_orchestration/`, `integration/conversation_understanding.py` |
| Governed action continuation | `integration/objective_action_rp.py`, `integration/rp_process.py` |
| Bounded native reads | `supervisor_bridge/repository_reader.py::WindowsDirectoryBinding`, `RepositoryReader` |
| Specification and Builder | `specs/`, `builder/`, `integration/build_runtime.py` |
| Supervisor and UI | `supervisor_bridge/`, `frontend/` |

The governed Learning path requires complete Observation/Understanding/RP lineage, supported outcome/causal analysis, eligibility and governance before durability; see `learning/CONTRACT.md`. A candidate is not an admitted lesson. Later use passes through relevance/admissibility checks and bounded learned projection into existing prompt context. This is not self-modification or execution authorization.

The objective-action path binds a model proposal to operator authorization, workspace containment, read-only status, objective binding and execution readiness. It requires fresh RP decisions and guarded execution; inspection findings and completion evidence remain separate. Continuation has bounded budgets, supported-operation checks and repetition guards. These mechanisms do not prove indefinite autonomous objective pursuit.

Runtime-inspection sources include private fixed historical catalogues that are intentionally unavailable in this source distribution. Unknown evidence must remain unavailable; source definitions are not runtime proof. Optional media/story/cinematic modules are included as implementation, not a claim of qualified production behavior.
