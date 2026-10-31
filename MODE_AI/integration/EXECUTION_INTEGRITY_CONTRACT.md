# Execution integrity contract

Operator decision, 2026-09-11: ambiguity greater than 0.50 requires clarification.
Posture follows clarification_required; the previous 0.65 threshold is not an
independent authority. Conversation may continue to resolve ambiguity. Neither
low ambiguity nor a conversational manifest grants consequential authority.
The structured build envelope supplies separate explicit execution authorization.

Builder reserves .builder_metadata, .builder_evidence and .observations. A
specification-owned build_receipt.json remains an artifact, never a Builder receipt.
Final integrity records bind validated and post-metadata hashes. This is a bounded
return-time check, not protection against subsequent external filesystem writes.

Understanding obligations enter BuildPlan evidence_requirements as source-linked
obligation records. An explicit completion_condition binds a requirement to an
existing Builder predicate. Unsupported prose stays UNPROVEN. Preference is the
existing non-authoritative Understanding kind; it remains in the specification.

Governance and receipt requirements also enter the success checks. The existing
receipt requirement `build_receipt` maps explicitly to `receipt written`.
No receipt is credited until it has been persisted. Mechanism labels such as
EXISTING_SUFFICIENT are not themselves executable validation evidence.

## Normal runtime configuration

Set MODE_RP_CONFIG to an operator-provisioned JSON file containing exactly
`repository`, `grant`, and `ledger` absolute paths. The grant is the existing
external RP verifier grant, bound to operator, thread, request hash and artifact
scope. Boot starts that external process and pins its handshake key. Missing or
unavailable configuration never supplies local RP authority. Builds remain
RP-pending without successful external acceptance. Shutdown closes the process
and its reader. The transport bounds handshake and response waits.

RP's evidence batch keeps its original evaluation epoch (the coordinator requires
an exact batch/decision epoch match). This is distinct from transition acceptance:
external consumption and Mode both check the current clock against the governed
authority interval. Mode also verifies signature, request hash, exact source claim
snapshot/version, scope, transition identity and session replay state. The result
records acceptance_checked_at and authority_valid_until. Expired evidence requires
a new governed preparation; authentication never renews validity.

## Authoritative obligation polarity

The source group establishes obligation class before execution: requirements,
invariants and dependencies are REQUIRED_STATE; prohibited_states are
PROHIBITED_STATE (NEGATIVE); completion_conditions are COMPLETION; evidence
requirements are EVIDENCE; constraints and authority requirements/dependencies
are GOVERNANCE; receipt requirements are RECEIPT. Other classes are POSITIVE.
Each mapped record preserves id, source path, parent id, original record,
authority_class, obligation_class, polarity and unresolved status.
Nested prohibitions are independent checks. A supported file prohibition requires
observed absence; presence fails. Unsupported predicates remain UNPROVEN.
PREFERENCE is descriptive only in the separate Understanding preferences group.
It cannot downgrade a record in any authoritative group.
Builder PASS requires all checks satisfied. External RP may confirm its narrower
claim while Builder remains FAIL/UNPROVEN; this cannot enter Mode COMPLETE.
Observation context readiness is true, false, or null (unestablished). Only an
explicit false readiness is classified as a context assembly issue.

## Durable halt and Observation custody

HALTED is latched in runtime and owner-scoped ThreadMemory. Boot scans the owner's
threads; switching threads or normal input cannot clear it. Recovery requires the
originating thread and an exact RUNTIME_HALT_RECOVERY approval bound to
`{"halt": <current halt record>, "target_state": "IDLE"}`. Recovery grants no build
or RP authority. Unreadable thread state fails closed before clearing the latch.

Builder writes a provisional UNPROVEN receipt before Observation finalization.
The wrapper saves and retrieves the exact Observation before attaching its path
and finalizing success. The persisted event contains the preceding artifact checks;
its own observation_persistence check belongs to the later terminal receipt and
manifest, avoiding a self-referential evidence record. Save/read/partial-write
failure downgrades the result and receipt. Runtime Observation failure blocks
dispatch or downgrades the completed build. Recovery is a new explicitly governed
attempt, never an automatic repeat of execution.

The previously failing clarification fixture was TEST_STALE: it depended on live
historical session context. Tests now isolate that context and directly exercise
0.50 and values above it. The governing runtime threshold was not changed.
