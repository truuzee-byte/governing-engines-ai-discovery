# Governed raw-story interpretation, version 1

This implementation contract follows the supplied Story Interpretation request,
Cinematic Understanding, Animation §§29–48, Understanding v1.3 §§8–10,
System v1.1 and System Chain Recognition. It does not replace those authorities.

## Intake and command

Use the existing DocumentService to admit the operator's prose as a current
CANON, AUTHORITATIVE or SPECIFICATION document. Then use the normal command:

```text
/creative cinematic interpret {"request": ..., "approval": ...}
```

`request` contains `reference`, `project_id`, and `story_selection`.
Every reference is exactly `{object_id, version, expected_hash}`.
`story_selection` is exactly:

```json
{
  "story_scope": "operator-selected story scope",
  "scene_scope": "",
  "sources": [
    {"reference": {"object_id": "story", "version": 1, "expected_hash": "PIN"},
     "start": 0, "end": 100}
  ],
  "operator_constraints": []
}
```

Ranges are half-open Unicode code-point offsets in the exact stored text.
The first source must match `reference`. Up to 16 different current source
records and 100,000 selected characters are accepted; at most 512 segmented
units. Existing per-document and persisted-stage bounds also apply. Binary
PDF/DOCX extraction is not performed by this interpreter. Use the existing
governed text-extraction path, preserving its source custody, before selection.

Authorization uses the existing exact-content `CINEMATIC_INTERPRET` action.
No approval is fabricated. The interpreter derives participants, state and
beats from the prose; callers do not supply those domain structures. Operator
constraints remain intact and block readiness until their enforcement is
established. This does not grant mechanism selection or execution authority.

`derive` and `specify` also accept this same optional `story_selection`, so the
existing cinematic source/candidate/selection path can retain raw-story custody.
All source versions are rechecked during specification export. A changed
secondary source blocks export just as a changed primary source does.

## Source and interpretation contracts

`StorySource` retains source/document identity, record version and hash,
content hash, original authority, project, story/scene scopes, source type,
text/range and operator constraints. `content_hash` uses the existing custody
store's canonical-JSON digest of the text string; it is not mislabeled as a
raw UTF-8 file hash. `record_hash` binds the full custody record.

`StoryClaim` retains a stable ID, category, subject, predicate, value,
epistemic state, exact span references and the extraction/derivation rule.
Each span identifies the source and exact original text range.

States are ESTABLISHED, INFERRED, UNKNOWN, CONFLICTED and PROPOSED.
ESTABLISHED means asserted in the selected authored story, not confirmed by
external Reality Primacy. UNKNOWN has no asserted value. PROPOSED records are
kept only in `creative_proposals`. They cannot enter canonical cinematic Facts.

`StoryInterpretation` contains sources, spans, claims, reference resolutions,
events, relationships, scene units, stages, unresolved items, conflicts and
separate proposals. `canonical_view()` supplies the field-oriented index for
world/entity/character/knowledge/belief/scene/beat/audience/continuity consumers.
It indexes those same records; it is not a second store or authority system.

Reference states: RESOLVED, PROBABLE, AMBIGUOUS, UNRESOLVED, CONFLICTED.
Names and explicit aliases can resolve. A role mention remains an entity
without an invented personal identity. Pronouns remain separate unresolved
references with candidates, even when one candidate is probable.

## Stages and supported interpretation

SOURCE → SOURCE_SEGMENTATION → ENTITY_REFERENCE_RESOLUTION → FACT_EXTRACTION
→ EVENT_EXTRACTION → STATE_CONSTRUCTION → CAUSAL_TEMPORAL_SPATIAL
→ CHARACTER_KNOWLEDGE_BELIEF → SCENE_BOUNDARY → BEAT_DERIVATION
→ AUDIENCE_STATE → NARRATIVE_SCENE_PURPOSE → GOVERNED_STORY_INTERPRETATION.

Every stage is inspectable and is stored as a GENERATED_CANDIDATE document on
the runtime path. The complete sidecar retains original claims and spans.

The deterministic clause grammar supports explicit subject/action/object
statements, selected physical and emotional predicates, goals, knowledge and
belief, source aliases, possession, relationship/authority actions, relative
space, simple explicit connective clauses, temporal markers and authored
audience statements. Explicit scene headings establish boundaries. Blank lines
do not. Uncertain location/time boundaries remain gaps.

Meaningful event transitions become beats; static description does not become
a beat solely because it is a sentence. Entry and exit maps retain initial
facts and intervening state. Knowledge and possession persist across explicit
scene boundaries within a source. Different source documents are not treated
as a sequential timeline.

CAUSES, ENABLES, TRIGGERS, CONTRIBUTES_TO, FOLLOWS, CORRELATED_WITH and
UNKNOWN_CAUSE remain distinct. An explicit nominal causal assertion does not
prove that either endpoint event occurred. Narrative ordering without an
explicit temporal signal is UNKNOWN_ORDER. BEFORE, AFTER, OVERLAP,
SIMULTANEOUS and explicit HOLD durations are retained. No coordinates,
time of day, weather or exact timing are supplied by convention.

Character perception does not automatically establish character knowledge.
Character belief does not become world truth. Character/world knowledge does
not become audience knowledge. An off-screen marker does not automatically
authorize concealment: narration or sound may still inform an audience.
On-screen markers create presentation obligations, not evidence of a render.
Audience `may_infer` is separate from knowledge.

Purpose derived from a transition category remains INFERRED. Silence does not
become sadness; political authority is not converted to an emotional label.
Explicit source disagreements retain both claims and an Operator adjudication
requirement. Conflict detection is bounded to supported dimensions and exact
proposition normalization, not general semantic contradiction discovery.

Unsupported or conditional complex clauses remain explicit coverage gaps.
The parser does not promise unrestricted prose understanding, general coreference,
figurative interpretation, reliable unmarked scene discovery or full transfer
recipient updates. It cannot choose values just because a downstream field exists.

## Admission and cinematic handoff

Admission deterministically replays the interpreter against its source records
and compares the complete interpretation. A candidate with a real span but an
invented claim value cannot pass this boundary. The adapter then uses the
existing strict `CinematicStory/1` parser and typed cinematic contracts.

The only purpose-gate extension permits INFERRED purpose while preserving
`INFERRED_PURPOSE_REQUIRES_REVIEW`. It does not promote purpose to canon or
allow eligible mechanism selection. Conflicted purpose or no supported beat
produces an inspectable UNRESOLVED result without a specification.

The runtime calls the existing UnderstandingEngine, governed handoff, chain
recognition, decomposition and specification-readiness mechanisms before
cinematic derivation. Mechanism classes are alternatives; implementation
freedom is empty. An unselected ExecutionSpecification is an UNPROVEN draft.
No executor, provider, Kernel or RP implementation is added.

The stored specification and exported handoff carry `story_lineage` with the
complete StoryInterpretation, field-oriented canonical index and fact-to-span
mapping. Observation records custody references and hashes, not story text.

## Verification and limits

See [story implementation report](../MODE_STORY_INTERPRETATION_IMPLEMENTATION_REPORT.md)
and `tests/test_story_interpretation.py`. Synthetic tests exercise the actual
command/store/Understanding/specification owners. They do not establish fresh
live-provider runtime boot, general natural-language competence, production
cinematic requalification, perceptual effectiveness or successful construction.
