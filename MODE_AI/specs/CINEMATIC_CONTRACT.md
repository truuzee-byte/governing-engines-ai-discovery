# Cinematic structured-source contract, version 1

Implementation contract for the existing Understanding → System → Specification owners. This document does not supersede the supplied Cinematic Understanding, Animation, Understanding v1.3, System v1.1, Chain Recognition or Capability authorities.

## Source and state

`CinematicStory/1` is a **structured authored source** in the existing DocumentService. It is not a claim that arbitrary source prose can already be interpreted into a complete story model. Top-level fields are exactly `schema_version`, `source_facts`, `policies`, `world_models`, `world_states`, `entities`, `narratives`, `truth_states`, `scenes`, `beats`, `audiences`. The last eight are typed record lists. Source fact locators start with `fact:` and resolve within the selected document. Document owner, project, version and record hash are separately checked. Historical selections, generated candidates and cross-project sources cannot become active authored authority through this command.

`Fact` preserves `value`, `state`, `source_references`, `evidence`, `grounding`. `UNKNOWN` has a null value; measured zero is an ordinary value. An `ESTABLISHED` authored fact must exactly match every referenced source fact. `INFERRED` is never promoted to established. `CONFLICTED` remains separate. Grounding states are `SUPPORTED`, `REASONABLE_INFERENCE`, `UNKNOWN`, `CONFLICTED`, `UNSUPPORTED`.

Each governed model has identity, scope, authority, source references, schema/version, evidence, assumptions, constraints, dependencies, relationships, temporal scope, optional confidence, validation state, lineage and unresolved questions. `object_type` is the Python class discriminator; serialized nesting names identify the record type. `object_id` is the uniform serialized identity (scene_id/beat_id are foreign keys). Cinematic validation state accepts only `UNVALIDATED` or `PENDING_VALIDATION`; RP verdicts cannot enter as self-issued validation.

World truth is authored fictional state. Character knowledge, beliefs, perspective and audience state are distinct. A world event never automatically makes the audience know it. The explicit exposure helper requires corresponding perceptual/narrative evidence references and authored authority; it does not prove an actual viewer perceived anything.

## Runtime commands

All commands use the normal `/creative` routing in `interactive_mode_ai.py` and `integration/content_custody.py`. The JSON body contains exactly `request` and `approval`. The existing `system_layer.contracts.authorize` checks the authenticated owner, action, `APPROVE`, and digest of the complete request. Generated model text is not an invocation or approval.

| Command suffix after `/creative cinematic ` | Required request fields | Approval action |
|---|---|---|
| `derive` | `reference`, `project_id` | `CINEMATIC_DERIVE` |
| `specify` | same source fields, `candidate_reference`, `selected_ids`; optional `operational_binding` | `CINEMATIC_SPECIFY` |
| `handoff` | `specification_reference`, `target`, `supported_obligations` | `CINEMATIC_HANDOFF` |
| `compare_frames` | `specification_reference`, `requirement_id`, `frame_references` | `CINEMATIC_COMPARE_FRAMES` |
| `compare_audio` | `specification_reference`, `requirement_id`, `audio_reference` | `CINEMATIC_COMPARE_AUDIO` |
| `review_candidate` | source fields, `stage`, `provider_status`, `output_text`, `prior_references` | `CINEMATIC_REVIEW_CANDIDATE` |

Every reference is `{object_id, version, expected_hash}`. Selections name current generated candidate IDs; changed candidate content/source or an ineligible candidate is rejected. A mechanism outside authored freedom requires revised source authority, not merely a selection approval. No command executes Builder, Pipeline, Unreal or a provider.

Derivation stores Understanding, scene/audience, requirements and candidates as separate candidate documents with exact approval and source lineage. Specification stores those references, all domain records, generic Understanding chain/decomposition analyses, and an optional existing CreativeOperationalResolution. Repeated identical stages resolve to their preserved record rather than silently generating replacements. Partial failure leaves earlier stages available but issues no completed downstream stage.

`operational_binding` is `{preparation, bindings}` from the existing CreativePreparation path. It resolves current SystemStore inventory/model receipt bindings through the existing operational validator. Without it, the System assessment is explicitly `UNPROVEN`. Even a structural model match cannot establish operability or execution authorization.

## Derivation and choices

For each meaningful beat, its required information and the explicitly associated audience obligations become a CinematicRequirement. Evidence requirements, hidden information, transitions, causal/emotional intent, physical constraints, continuity, acceptable classes and freedom remain explicit. Missing perception evidence, contradictory world constraints or unresolved state changes prevent eligible selection.

Mechanism alternatives are class-level structural proposals. CAMERA, BLOCKING, PERFORMANCE, EDITING, LIGHTING, SOUND, MUSIC, ENVIRONMENT, ANIMATION and DIALOGUE each preserve their parameter dimensions. Numeric lens, position and timing values are not fabricated. Candidates are checked for scope, authority, allowed class, information leakage, missing information, prohibited interpretations and declared physical/continuity impacts. `ELIGIBLE` means eligible for exact-content **intent selection**; it does not mean feasible, rendered, operational or reality-confirmed. Feasibility remains `UNPROVEN` without appropriate evidence.

Selected alternatives produce a purpose-bound ShotRequirement. Shot count here is one package per beat requirement with selected mechanisms; it is not an automatic artistic edit optimizer. Continuity compares authored prior state with proposed next state and preserves missing dimensions/conflicts. Explicit grounded authorized changes are separate from unexplained changes. It does not simulate physical motion.

## Specification and handoff

`ExecutionSpecification` is the lossless cinematic domain payload. It does not replace canonical engineering BuildSpec or BuildPlan. `CinematicExecutorHandoff/1` includes the full specification, hash, source/Understanding/stage references, obligations, unsupported items, field map, and source-to-shot lineage. Targets are `BUILDER`, `CODEX`, `PIPELINE`, `UNREAL_ADAPTER`; this is contract export, not installed execution adapters.

The six dispositions are `REQUIRED`, `AUTHORIZED`, `OPTIONAL`, `PROHIBITED`, `UNRESOLVED`, `IMPLEMENTATION_CHOICE`. Fact-level paths, mechanism IDs, prohibited reveals and allowed parameter classes are indexed. An unresolved concrete parameter may be chosen only under the corresponding class's explicit implementation freedom; this is not permission to alter an unknown world fact.

Executor-declared supported obligations cannot prove capability. Unsupported obligations or unresolved derivation yield `UNPROVEN`. The existing Understanding `governed_handoff` verifies custody; a blocked `specification_handoff` is preserved as an unresolved readiness condition in the candidate draft. Current Understanding hashes are checked again during export/comparison. Otherwise the export is `SPECIFICATION_PREPARED`, still with `execution_authority=False`, `capability_proven=False`, and `external_rp_required=True`. RP and existing consequential execution gates remain downstream owners.

## Evidence comparison

The existing hash-checked frame/PCM inspectors supply measurements. `BLACK_FRAME`, `NONBLACK_FRAME`, and `NONSILENT_PCM` are narrow supported measurement predicates. Required character/action visibility against an all-black frame yields `MISMATCH`; a nonblack image alone yields `UNRESOLVED` because it cannot establish identity/action. Unsupported semantic predicates remain unresolved. Empty requirements, missing or unreadable measurements never match by default.

`MATCH`, `MISMATCH`, `UNRESOLVED` are local comparisons, **not RP verdicts**. Claim state remains `PENDING_VALIDATION`. Runtime frame and PCM comparisons preserve specification→requirement→selected evidence→measurement→comparison→Observation hashes. Existing `/creative inspect_audio` remains compatible. No cinematic visibility classifier, playback/synchronization validator or RP cinematic validator is claimed.

## Provider boundary

No provider is invoked. Optional candidate review admits only bounded structured envelopes with exact source/prior-stage hashes in SCENE → AUDIENCE → REQUIREMENTS → MECHANISMS → SPECIFICATION order. Completed envelopes remain candidates requiring grounding. Incomplete, malformed and oversized outputs are recorded as rejected; no retry or silent replacement occurs. Provider-stage review does not automatically feed generated text into canonical source.

The existing ReasoningAgent additionally rejects explicit non-`completed` response status even when text is nonempty, preserving error telemetry and raising instead of publishing a truncated result. Legacy adapters omitting status retain their prior output contract. This is not live provider qualification.

## Inspectable example

[Synthetic full command chain](../artifacts/cinematic_infrastructure_20260925/DETERMINISTIC_CHAIN.json) includes complete source, requests, generated requirements/candidates, specification, handoff and command-observation payloads. It uses the real command/service/store code with a synthetic runtime context; it does not establish fresh `ModeRuntime.boot()` or free-text cinematic behavior.
