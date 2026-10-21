# Repository curation and publication audit — October 21, 2026

This is a curation record, not a new research or MODE qualification experiment. The attachment audit was completed before importing public sources. The pass adds six distinct records, skips three exact duplicates, and withholds one explicitly internal record. It reuses the existing catalog, source manifest, builder, graph, tests and Pages workflow.

## Repository state before changes

- Repository: `truuzee-byte/governing-engines-ai-discovery`, branch `main`.
- Clean starting commit: `42c4586d404809dd05c358b531d3755d4c419f94`.
- Existing public corpus: 31 source records, 61 HTML pages, five source collections, six research groups and seven concept entry points.
- Existing sources: `content/sources/*.txt`, registered by `content/source-manifest.json` with original/published hashes and identity metadata.
- Existing generated surfaces: corpus/index, JSON catalog, relationship graph/JSON, canonical document pages, sitemap and robots.txt.
- No canonical Journey directory/record, standalone Passenger/Walk/Follow-the-Harm record, or dated MODE machine-state record existed. References to a work inside other papers were not mistaken for an already registered copy.
- Original eight-note instruction experiment, historical reports, external-discovery protocol and participant reports were present and are preserved.
- Baseline tests: **16 passed**. Baseline build and validator: **61 pages, eight original technical notes**, passed.

The audit inspected corpus identities, source hashes, titles/versions/dates, source text, manifests, generated page inventory, relationship structure, README/policy documentation, tests and workflow. Exact original-binary hashes identify the three duplicates below; a newer filename timestamp does not establish a newer document edition. No unknown material was deleted or renamed.

## Attachment-by-attachment decisions

The [machine-readable decision log](curation-decisions-2026-10-21.json) preserves every supplied filename, original SHA-256, normalized extracted-text hash, PDF page count where applicable, matched ID/path, action, final path and rationale. It is an audit report, not a second publication index.

| Attachment | Match found / existing path | Action | Final canonical record | Reason |
| --- | --- | --- | --- | --- |
| 1. `The_Passenger_v1.2(20261021-032533).docx` | No canonical equivalent | ADD | `/research/the-passenger/index.html` | New September 2026 v1.2 exploratory/comparative/non-ontological research work; existing Before You Name the Machine cites it but did not contain its canonical source record. |
| 2. `A_Walk_Through_Humanity_Substantive_Research_Edition_v3.0(20261021-032533).pdf` | No canonical equivalent | ADD | `/research/a-walk-through-humanity/index.html` | New v3.0 research work; title, internal September date, evidence categories and scope preserved. |
| 3. `The_America_They_Built_White_Paper_v1.0(20261021-032533).docx` | Exact binary match: `content/sources/the-america-they-built.txt` and existing original hash | SKIP | Existing `/research/the-america-they-built/index.html` | Same v1.0 August 2026 work, not a revision. Existing source and metadata unchanged. |
| 4. `Follow_the_Harm_Meta_Proof_Power_and_Custody_v1.1(20261021-032533).pdf` | Referenced in Danger Zones; no standalone canonical record | ADD | `/research/follow-the-harm/index.html` | New source record for the August 27 v1.1 evidence-constrained investigative analysis. No independent legal/factual adjudication is implied. |
| 5. `GE_Journey_Full_Through_October_21_2026(1).pdf` | No canonical Journey/lineage location | ADD | `/journey/governing-engines-journey/index.html` | Establish one stable cumulative location; retain base v1.1/August 26 and Appendix F v1.0/October 21 rather than silently replacing dates. |
| 6. `What_Is_Intelligence_v1_2_Evidence_Pass(20261021-032533).docx` | Exact binary match: `content/sources/what-is-intelligence.txt` | SKIP | Existing `/research/what-is-intelligence/index.html` | Filename-v1.2/title-page-v1.1 discrepancy already recorded. Same binary, title and September content; no duplicate added. |
| 7. `The_Cost_of_the_Outcome_v1.1(20261021-032533).pdf` | Exact binary match: `content/sources/the-cost-of-the-outcome.txt` | SKIP | Existing `/research/the-cost-of-the-outcome/index.html` | Same v1.1 September 2 PDF, 12 pages and original hash. Existing source and record unchanged. |
| 8. `MODE_Last_Verified_Machine_State_Traceability_Record_v1.0(20261021-032641).docx` | Related MODE specification exists; no matching snapshot | PRESERVE AS HISTORICAL | `/machine-state/mode-machine-state-2026-09-14/index.html` | Added as a distinct September 14 v1.0 historical snapshot. It is not replaced by October evidence or labeled live/current. |
| 9. `MODE_Public_Machine_State_MODE_Only(1).docx` | No newer public MODE snapshot in audited repository | ADD | `/machine-state/mode-machine-state-2026-10-21/index.html` | Distinct v3.1 October 21 public MODE-only cutoff. Current only at that cutoff, not an indefinitely current live-state assertion. |
| 10. `Governing_Engines_Ecosystem_Machine_State_October_21_2026_v1.0(1).docx` | No matching public record; explicit internal classification | SKIP / WITHHOLD | None | Source labels itself Internal Verified State & Traceability Record and an internal source-of-truth layer for narrower public derivatives. Existing public-source policy does not permit publishing it merely because it was attached. No internal body or broader-system data is imported. |

The ecosystem source's own record date says October 21 UTC / October 20 America/New_York; it is not silently redated or mislabeled as a public MODE-only record. Its filename/hash and internal-boundary decision are retained in the audit log without distributing its internal contents. Future publication or derivation needs explicit operator authorization identifying the material and a public-safety review.

## Dedicated Journey home and source roles

Canonical tracked Journey source: `content/journey/governing-engines-journey.txt`.

Canonical page: `/journey/governing-engines-journey/index.html`.

Canonical public source: `/journey/governing-engines-journey/source.txt`.

`content/journey/README.md` explains that the document is cumulative: future appended editions update this same source/record/path while Git retains history. There is one Journey catalog identity, no dated paper copies, and no second Journey source in the general research directory. The adjacent public text is a representation of that same registered work, not another catalog document.

Historical MODE source: `content/machine-state/mode-2026-09-14.txt`.

October public MODE source: `content/machine-state/mode-2026-10-21.txt`.

Both have dated discovery pages and adjacent `source.txt` downloads. `content/machine-state/README.md` documents chronology, scoped current-at-cutoff labeling, and the withheld internal ecosystem boundary. No historical machine-state file was overwritten; the September record is newly preserved in this repository as historical evidence. The Journey remains a lineage account, not a substitute for either snapshot.

## Catalog, graph and implementation changes

The existing corpus grows from **31 to 37 records** and from **61 to 69 HTML pages**. Six new document pages and two role-specific collection pages account for the eight additional pages. The existing JSON catalog exposes record roles, snapshot dates/positions, Journey coverage, source paths and relationship bases. Its original edition date remains October 20; `updated_on` records October 21, and new discovery records have their own publication date. Source document dates remain separately preserved.

No separate index or deployment mechanism was introduced. The existing source manifest adds six original/published hash entries and retains all earlier 31 entries exactly. The builder now supports dedicated source paths and registered counts rather than a fixed 31-document assertion. The existing public checker follows those same registered source paths. The Pages workflow YAML is unchanged.

New reading edges carry a source or explicitly labeled thematic-comparison basis. Before You Name the Machine gains its explicit Passenger reference, and Danger Zones gains its explicit Follow the Harm companion. Journey/snapshot links preserve author lineage and chronology without implying independent corroboration. The arbitrary graph-density threshold was replaced by checks that the declared relationships actually exist; no filler links were added to increase density.

Public text editions preserve extracted source wording with marked privacy filtering and whitespace normalization. The new September snapshot had one machine-local trace path redacted. Public HTTPS citations are preserved. A redaction-regression test confirms that Windows paths are filtered without accidentally removing HTTPS links. The original binaries are not distributed, matching the repository's established source-edition practice; source hashes identify them. Extraction is not a layout-faithful reproduction of PDF/DOCX tables or mathematical notation.

## Files added, updated and deliberately skipped

Added public sources:

- `content/sources/the-passenger.txt`
- `content/sources/a-walk-through-humanity.txt`
- `content/sources/follow-the-harm.txt`
- `content/journey/governing-engines-journey.txt` and its README
- `content/machine-state/mode-2026-09-14.txt`
- `content/machine-state/mode-2026-10-21.txt` and the machine-state README

Updated implementation/documentation:

- `.gitattributes`: LF hashing rules for dedicated Journey/machine-state source files.
- `content/corpus.json`: six new identities, two evidence-grounded back-links, registered count and update date.
- `content/source-manifest.json`: six appended provenance/identity entries; existing entries unchanged.
- `tools/corpus.py`: role-specific collections, unique identities/source paths, Journey location, chronological snapshot validation, count rendering, dated metadata, and relationship-basis display.
- `tools/ingest_corpus.py`: selective `--ids` import preserving unselected sources/manifests and machine-local-path filtering.
- `tools/publication.py`: registered homepage count and shared source-path use in public verification.
- `tests/test_corpus.py`: updated inventory expectations and seven new curation tests.
- README and `docs/source-corpus.md`: current counts, canonical Journey, chronological evidence, policy and maintenance links.
- Standard latest local-validation report and the dated curation evidence reports.

No copy of attachments 3, 6 or 7 was added. All 31 existing public source editions and their provenance entries are unchanged. The internal ecosystem attachment was not copied into any published or tracked source directory. Earlier reports, external observation records, original technical-note content, canonical instruction, and original test module are unchanged. Unknown/unrelated material was left in place.

## Tests and validation results

- Baseline: **16 tests passed**; **61-page build and validator passed**.
- Updated suite: **23 tests passed**. The suite retains all prior tests and adds duplicate canonical-title rejection, unique stable Journey paths, chronology, invalid-current-snapshot rejection, internal-source exclusion, selective-import preservation, and local-path/HTTPS redaction behavior.
- Updated build and validator: **69 pages**, **eight original technical notes**, **37 corpus records**; passed.
- No duplicate IDs, normalized canonical title/date identities, original-binary hashes, source paths or public-source paths were detected.
- All generated internal file/fragment links, canonical URLs, sitemap entries, catalog metadata, source hashes and graph endpoints/sequences passed validation.
- Original eight HTML articles and eight Markdown counterparts remain **byte-identical** to the pre-curation production-URL baseline, including all four instruction layers.
- Targeted privacy-pattern scan of the six additions passed. The scan is bounded to checked patterns, not a guarantee of universal personal-data detection.
- These are publication-repository checks. The MODE counts/results quoted by the supplied snapshots are author-reported source content; no MODE runtime qualification was performed here.

Evidence files: `curation-baseline-tests-2026-10-21.txt`, `curation-baseline-validation-2026-10-21.json`, `curation-tests-2026-10-21.txt`, `curation-local-validation-2026-10-21.json`, `curation-preservation-2026-10-21.json`, and `curation-decisions-2026-10-21.json`.

Reproduction:

```sh
python -m unittest discover -s tests -v
python tools/publication.py build --base-url https://truuzee-byte.github.io/governing-engines-ai-discovery
python tools/publication.py validate --base-url https://truuzee-byte.github.io/governing-engines-ai-discovery
python tools/publication.py check-public --base-url https://truuzee-byte.github.io/governing-engines-ai-discovery
```

## Commit, push and live verification custody

This report is authored for the **single coherent publication/update commit** containing it. Its exact SHA is supplied in the final operator handoff and can be obtained from `git log -- reports/curation-audit-2026-10-21.md`; a commit cannot embed its own final hash. No history rewrite, force-push, or second evidence commit is part of this pass.

The pre-push audit/local checks above are completed facts. Push, hosted deployment, and post-deployment HTTP results are only confirmed after this commit is created and sent to GitHub; their exact SHA/run URL/results are provided in the final operator handoff. The unchanged workflow retains hosted verification under its `local-validation` and `public-verification` artifacts. The expanded checker covers **120 required public files** for this edition. Local post-push evidence may be retained under ignored `.local-evidence/curation-2026-10-21/` rather than changing committed files after the one requested commit.

To inspect the exact final Git diff and statistics, use `git show --stat` on that commit. The intended scope is six source additions, role-specific documentation and metadata, targeted generator/importer/validator/test adjustments, and this audit evidence. No earlier source was replaced or deleted.

## New public URLs to verify after deployment

| Role | Canonical record | Source edition |
| --- | --- | --- |
| The Passenger | [Record](https://truuzee-byte.github.io/governing-engines-ai-discovery/research/the-passenger/index.html) | [Source](https://truuzee-byte.github.io/governing-engines-ai-discovery/sources/the-passenger.txt) |
| A Walk Through Humanity | [Record](https://truuzee-byte.github.io/governing-engines-ai-discovery/research/a-walk-through-humanity/index.html) | [Source](https://truuzee-byte.github.io/governing-engines-ai-discovery/sources/a-walk-through-humanity.txt) |
| Follow the Harm | [Record](https://truuzee-byte.github.io/governing-engines-ai-discovery/research/follow-the-harm/index.html) | [Source](https://truuzee-byte.github.io/governing-engines-ai-discovery/sources/follow-the-harm.txt) |
| Cumulative Journey | [Record](https://truuzee-byte.github.io/governing-engines-ai-discovery/journey/governing-engines-journey/index.html) | [Source](https://truuzee-byte.github.io/governing-engines-ai-discovery/journey/governing-engines-journey/source.txt) |
| Historical September MODE | [Record](https://truuzee-byte.github.io/governing-engines-ai-discovery/machine-state/mode-machine-state-2026-09-14/index.html) | [Source](https://truuzee-byte.github.io/governing-engines-ai-discovery/machine-state/mode-machine-state-2026-09-14/source.txt) |
| October public MODE | [Record](https://truuzee-byte.github.io/governing-engines-ai-discovery/machine-state/mode-machine-state-2026-10-21/index.html) | [Source](https://truuzee-byte.github.io/governing-engines-ai-discovery/machine-state/mode-machine-state-2026-10-21/source.txt) |

Collection entry points: [Journey](https://truuzee-byte.github.io/governing-engines-ai-discovery/journey/index.html), [machine-state chronology](https://truuzee-byte.github.io/governing-engines-ai-discovery/machine-state/index.html), and [corpus](https://truuzee-byte.github.io/governing-engines-ai-discovery/corpus/index.html). Existing canonical URLs for the three skipped duplicates are retained, not republished as new documents.

## Unresolved issues

The internal ecosystem record remains withheld; explicit authorization and an approved public-safe representation are needed before it can enter this public repository. No raw private architecture or internal evidence details are published by this audit. The Journey's base/appendix version distinctions and What Is Intelligence's pre-existing filename/title-page version discrepancy remain explicitly visible rather than being silently reconciled.

No new search-indexing, external-assistant, MODE execution, legal/factual adjudication, or discovery experiment was conducted. Publishing and HTTP verification do not establish indexing, retrieval, adoption, endorsement or independent verification of the attached papers' research/behavioral claims.
