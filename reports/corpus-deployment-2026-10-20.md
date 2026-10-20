# Governing Engines source corpus deployment — October 20, 2026

Status: **implemented, deployed, and independently verified over HTTPS**. No external search-indexing, ranking, or assistant-discovery trial was conducted.

## Deployment identifiers and entry points

- Repository: [truuzee-byte/governing-engines-ai-discovery](https://github.com/truuzee-byte/governing-engines-ai-discovery), branch `main`.
- Deployed implementation commit: [`e42837ba87bd408f84430a0a15f20db2f58ea1c6`](https://github.com/truuzee-byte/governing-engines-ai-discovery/commit/e42837ba87bd408f84430a0a15f20db2f58ea1c6).
- Successful GitHub Actions run: [39453153338](https://github.com/truuzee-byte/governing-engines-ai-discovery/actions/runs/39453153338). Build, deploy, and verify-public jobs all succeeded.
- [Publication homepage](https://truuzee-byte.github.io/governing-engines-ai-discovery/index.html).
- [Human-readable corpus and search](https://truuzee-byte.github.io/governing-engines-ai-discovery/corpus/index.html).
- [Machine-readable catalog](https://truuzee-byte.github.io/governing-engines-ai-discovery/corpus/catalog.json).
- [Relationship graph](https://truuzee-byte.github.io/governing-engines-ai-discovery/corpus/graph.html) and [JSON relationships](https://truuzee-byte.github.io/governing-engines-ai-discovery/corpus/relationships.json).
- [MODE public specification record](https://truuzee-byte.github.io/governing-engines-ai-discovery/systems/mode/index.html).
- [XML sitemap](https://truuzee-byte.github.io/governing-engines-ai-discovery/sitemap.xml) and [robots.txt](https://truuzee-byte.github.io/governing-engines-ai-discovery/robots.txt).

The final evidence-only commit records this report without redeploying unchanged files (`[skip ci]`). The implementation commit above identifies the actual artifact verified here.

## What changed

The extension adds **31 author-supplied source records**, five collection pages, six thematic research pages, seven concept entry points, and two corpus/graph pages. Together with the existing ten HTML pages, the site builds **61 HTML pages**. The reading graph contains **38 nodes and 142 edges**.

Every source record includes its document title, DeMarius J. Lawson / Governing Engines LLC attribution, version/date/status, concise abstract, 5–15 research terms, three source-supported claims or distinctions, claim boundaries, related documents, and a downloadable source text edition. Null dates/versions display as not stated rather than being invented. Filename/title-page version discrepancies are recorded explicitly. Compilation source-level metadata remains in the underlying text.

Collections follow purpose/principles/terminology, methods, systems, research, and evidence-linked case studies. Concept links connect execution evidence, outcome validation, authority, semantic continuity, reality primacy, research custody, and physical systems. Reading relationships are labeled editorial, not fabricated citations, evidence of endorsement, or proof that another source validates a claim. The later Replit attribution update is linked alongside the earlier unresolved-provenance condition without overwriting it.

The homepage gained a corpus entry link. The original eight HTML articles and eight Markdown counterparts are **byte-identical to the pre-extension production-URL baseline**, including the exact canonical instruction and its four representations. The canonical configuration, original article JSON, original tests, workflow YAML, external-discovery protocol, participant trial log, and historical reports were preserved. The source extension is a new public retrieval condition, not a new behavioral experiment or proof of improved independent discovery.

## Source custody and privacy

The import used only the 31 supplied public source documents from the handoff package. The handoff prompt itself is not presented as a research paper. No private MODE repository, kernel, or unrelated project was inspected or published.

Original PDF/DOCX binaries were not distributed because some supplied public case-study artifacts still contained email or billing identifiers. Instead, the site distributes clearly labeled **public source text editions** with PDF page markers, normalized line endings/trailing whitespace, and inline privacy-redaction markers. The original artifact filename and SHA-256, published text SHA-256, source identity, PDF page count, and redaction counts are recorded in `content/source-manifest.json` and exposed with the record. The original binaries remain outside the repository.

Privacy filtering removed **2 email occurrences, 9 invoice-identifier occurrences, and 12 case-study billing-amount occurrences**. Redacted values are not recorded in the public manifest. Economic research values outside the account-specific case studies were preserved. A source-text scan found no matches for the checked local-user-path, email, invoice-ID, credential, private-key-header, and private-access-URL patterns. This is a targeted check, not a guarantee that every possible personal identifier could be recognized automatically.

These are text extractions, not original binary artifacts or layout-faithful reproductions. Tables, typography, mathematical notation, and line breaks can lose visual structure; original artifacts may be required for engineering interpretation. The importer reported recoverable PDF cross-reference warnings, extracted nonempty text for every source, and retained source hashes. No visual/fidelity audit of all 612 supplied PDF pages is claimed.

## Files changed

Implementation/source commit:

- `.gitattributes`: fixed LF treatment for source editions so source hashes survive Windows/Linux checkout.
- `README.md`: live entry points and maintenance documentation link.
- `content/corpus.json`: 31 source-faithful discovery records.
- `content/source-manifest.json`: original/source-edition hashes, identities, and redaction provenance.
- `content/sources/*.txt`: 31 privacy-filtered source editions; exact inventory below.
- `docs/source-corpus.md`: source boundaries, catalog semantics, maintenance, import, and disclosure rules.
- `tools/corpus.py`: static corpus generation and validation.
- `tools/ingest_corpus.py`: one-time authorized-source importer; not invoked by build/CI.
- `tools/publication.py`: corpus hook, homepage entry link, sitemap/validation inventory extension, and expanded public URL checks.
- `tests/test_corpus.py`: eight additional regression/failure-detection tests. Existing eight tests remain unchanged.
- Dated baseline, test, local-validation, and original-artifact-preservation reports; the standard latest local validation report was refreshed.

Evidence-only commit adds the dated deployment report, GitHub job results, public HTTP verification, browser QA record, and live screenshot, and refreshes the standard latest public-verification report. Generated site files remain in ignored `dist/` and are rebuilt by the unchanged Pages workflow.

## Tests and validation

Before modification: **8/8 existing tests passed**, the original ten-page production-URL build passed, and hashes of all sixteen original article/Markdown files were retained.

After extension: **16/16 tests passed locally and in GitHub Actions**. Tests include positive root/subpath builds and deterministic rebuilds, plus rejection of missing original documents, message drift, malformed JSON-LD, stripped Markdown comments, broken links, missing corpus identities, catalog metadata drift, missing author attribution, missing related links, source tampering, and dangling graph nodes. Privacy filtering also has a representative negative-data test.

The publication validator passed for all **61 HTML pages**: semantic structure, titles/descriptions, JSON-LD parsing, canonical URLs, file/fragment links, complete sitemap membership, artifact hashes, corpus source identities, source hashes, author/organization fields, research terms/claims, required discovery links, and graph endpoints/sequences. Original instruction extraction still passes in all four layers across all eight notes.

The first extended local test run detected failures in assertions expecting a semantic-validation error before the general hash check; semantic corpus validation was moved before the final hash loop. Importing the original unittest class also caused duplicate discovery; the test module now imports its containing module. The resulting suite contains sixteen distinct tests. Extracted PDF trailing whitespace was normalized rather than shipping noisy whitespace defects. `git diff --cached --check` then passed. No architecture replacement was needed.

Reproduction commands (Python 3.12+, standard library only for normal build/test):

```sh
python -m unittest discover -s tests -v
python tools/publication.py build --base-url https://truuzee-byte.github.io/governing-engines-ai-discovery
python tools/publication.py validate --base-url https://truuzee-byte.github.io/governing-engines-ai-discovery
python tools/publication.py check-public --base-url https://truuzee-byte.github.io/governing-engines-ai-discovery
```

The importer additionally requires `pypdf` only when ingesting PDFs locally. That dependency is not needed to build or deploy from checked-in source editions.

## Live verification

The existing workflow's expanded public-check job succeeded. An independent local-machine HTTPS run then retrieved **106 required public files**, all with **HTTP 200 and exact content matches** against the locally validated production build. The recorded completion timestamp is `2026-10-20T15:58:55.167953+00:00` (11:58 AM America/New_York). It includes all 61 HTML pages, all 31 source editions, eight original Markdown files, two JSON discovery files, two assets, sitemap, and robots.txt. Thus the deployed metadata, links, claims, source hashes, and original instruction match the validated artifact; this does not establish external index or model ingestion.

The in-app browser independently displayed the live catalog, MODE record, and relationship graph. Search initially showed 31 records; `TCVO` returned one matching record, THE COST OF THE OUTCOME; `zzzz-no-match` returned zero; clearing the input restored all 31. The source record displayed author, date/version/status, claims, boundaries, source download, hashes, and related-reading links. Desktop layout was visually inspected. A local preview could not connect across the sandbox boundary and was stopped; live browser QA resolved the UI-verification gap. No mobile or exhaustive accessibility audit is claimed.

Evidence:

- `corpus-baseline-tests-2026-10-20.txt`, `corpus-baseline-validation-2026-10-20.json`.
- `corpus-tests-2026-10-20.txt`, `corpus-local-validation-2026-10-20.json`.
- `corpus-preservation-2026-10-20.json`: unchanged original artifact hashes.
- `corpus-github-jobs-2026-10-20.json`: successful hosted job/step outcomes.
- `corpus-public-verification-2026-10-20.json`: all 106 independently fetched URLs/statuses.
- `corpus-browser-qa-2026-10-20.json`, `corpus-live-2026-10-20.png`.

## Unresolved limits and independent outcomes

No deployment blocker remains. Source wording/version ambiguities, source extraction fidelity, and source-specific research limits remain visible. The catalog does not independently verify each paper's external empirical references, certify proposed systems, adjudicate case-study disputes, or imply NIST endorsement. Original source PDFs/DOCXs are not downloadable here; the public source text editions and provenance hashes are provided instead.

External search indexing, ranking, assistant-specific discovery/retrieval, instruction extraction by an assistant, contact recommendation, adoption, and decision-maker receipt remain unverified for this new corpus condition. The three earlier Claude observations remain participant-reported historical trials. No new Claude or other assistant conversation, search-engine discoverability investigation, or simulated result was conducted.

## Complete source-record URL inventory

All URLs in the table below were included in the independent 106-file verification.

| Document | Discovery record | Public source text |
| --- | --- | --- |
| THE LAW OF RESPONSIBLE HUMAN STEWARDSHIP | [Record](https://truuzee-byte.github.io/governing-engines-ai-discovery/core/responsible-human-stewardship/index.html) | [Source](https://truuzee-byte.github.io/governing-engines-ai-discovery/sources/responsible-human-stewardship.txt) |
| GOVERNING PRINCIPLES | [Record](https://truuzee-byte.github.io/governing-engines-ai-discovery/core/governing-principles/index.html) | [Source](https://truuzee-byte.github.io/governing-engines-ai-discovery/sources/governing-principles.txt) |
| CANONICAL TERMINOLOGY REGISTRY | [Record](https://truuzee-byte.github.io/governing-engines-ai-discovery/core/canonical-terminology/index.html) | [Source](https://truuzee-byte.github.io/governing-engines-ai-discovery/sources/canonical-terminology.txt) |
| RUNTIME OBSERVATION REFINEMENT METHOD | [Record](https://truuzee-byte.github.io/governing-engines-ai-discovery/methods/runtime-observation-refinement/index.html) | [Source](https://truuzee-byte.github.io/governing-engines-ai-discovery/sources/runtime-observation-refinement.txt) |
| AI OPERATOR & SYSTEM BUILDER DEVELOPMENT FRAMEWORK | [Record](https://truuzee-byte.github.io/governing-engines-ai-discovery/methods/operator-system-builder-development/index.html) | [Source](https://truuzee-byte.github.io/governing-engines-ai-discovery/sources/operator-system-builder-development.txt) |
| MODE PUBLIC BUILD SPECIFICATION | [Record](https://truuzee-byte.github.io/governing-engines-ai-discovery/systems/mode/index.html) | [Source](https://truuzee-byte.github.io/governing-engines-ai-discovery/sources/mode.txt) |
| SPEC CLOUD | [Record](https://truuzee-byte.github.io/governing-engines-ai-discovery/systems/spec-cloud/index.html) | [Source](https://truuzee-byte.github.io/governing-engines-ai-discovery/sources/spec-cloud.txt) |
| OPERATOR GOVERNANCE COLLECTION | [Record](https://truuzee-byte.github.io/governing-engines-ai-discovery/systems/operator-governance/index.html) | [Source](https://truuzee-byte.github.io/governing-engines-ai-discovery/sources/operator-governance.txt) |
| GOVERNED TEVV FOR AGENTIC AI | [Record](https://truuzee-byte.github.io/governing-engines-ai-discovery/systems/governed-tevv/index.html) | [Source](https://truuzee-byte.github.io/governing-engines-ai-discovery/sources/governed-tevv.txt) |
| GOVERNED ADAPTIVE CONTROL FOR FAULT-TOLERANT QUANTUM SYSTEMS | [Record](https://truuzee-byte.github.io/governing-engines-ai-discovery/systems/governed-adaptive-quantum-control/index.html) | [Source](https://truuzee-byte.github.io/governing-engines-ai-discovery/sources/governed-adaptive-quantum-control.txt) |
| AI DOOM | [Record](https://truuzee-byte.github.io/governing-engines-ai-discovery/research/ai-doom/index.html) | [Source](https://truuzee-byte.github.io/governing-engines-ai-discovery/sources/ai-doom.txt) |
| DANGER ZONES | [Record](https://truuzee-byte.github.io/governing-engines-ai-discovery/research/danger-zones/index.html) | [Source](https://truuzee-byte.github.io/governing-engines-ai-discovery/sources/danger-zones.txt) |
| BEFORE YOU NAME THE MACHINE | [Record](https://truuzee-byte.github.io/governing-engines-ai-discovery/research/before-you-name-the-machine/index.html) | [Source](https://truuzee-byte.github.io/governing-engines-ai-discovery/sources/before-you-name-the-machine.txt) |
| SEMANTIC COMPRESSION | [Record](https://truuzee-byte.github.io/governing-engines-ai-discovery/research/semantic-compression/index.html) | [Source](https://truuzee-byte.github.io/governing-engines-ai-discovery/sources/semantic-compression.txt) |
| THE ESCAPE ARTIST | [Record](https://truuzee-byte.github.io/governing-engines-ai-discovery/research/the-escape-artist/index.html) | [Source](https://truuzee-byte.github.io/governing-engines-ai-discovery/sources/the-escape-artist.txt) |
| THE SYSTEM DIDN'T WORK. THE OPERATOR DID. | [Record](https://truuzee-byte.github.io/governing-engines-ai-discovery/research/the-system-didnt-work/index.html) | [Source](https://truuzee-byte.github.io/governing-engines-ai-discovery/sources/the-system-didnt-work.txt) |
| THE COST OF THE OUTCOME | [Record](https://truuzee-byte.github.io/governing-engines-ai-discovery/research/the-cost-of-the-outcome/index.html) | [Source](https://truuzee-byte.github.io/governing-engines-ai-discovery/sources/the-cost-of-the-outcome.txt) |
| EXECUTIVE BRIEF — OPERATIONAL DRIFT GOVERNANCE AND GOVERNED EXECUTION INFRASTRUCTURE | [Record](https://truuzee-byte.github.io/governing-engines-ai-discovery/research/executive-brief/index.html) | [Source](https://truuzee-byte.github.io/governing-engines-ai-discovery/sources/executive-brief.txt) |
| WHAT IS INTELLIGENCE? | [Record](https://truuzee-byte.github.io/governing-engines-ai-discovery/research/what-is-intelligence/index.html) | [Source](https://truuzee-byte.github.io/governing-engines-ai-discovery/sources/what-is-intelligence.txt) |
| THE MASK AI RESEARCH WEARS | [Record](https://truuzee-byte.github.io/governing-engines-ai-discovery/research/the-mask-ai-research-wears/index.html) | [Source](https://truuzee-byte.github.io/governing-engines-ai-discovery/sources/the-mask-ai-research-wears.txt) |
| PAST. PRESENT. FUTURE. | [Record](https://truuzee-byte.github.io/governing-engines-ai-discovery/research/past-present-future/index.html) | [Source](https://truuzee-byte.github.io/governing-engines-ai-discovery/sources/past-present-future.txt) |
| BEFORE WE ARRIVE | [Record](https://truuzee-byte.github.io/governing-engines-ai-discovery/research/before-we-arrive/index.html) | [Source](https://truuzee-byte.github.io/governing-engines-ai-discovery/sources/before-we-arrive.txt) |
| HUMAN ABSTRACTIONS | [Record](https://truuzee-byte.github.io/governing-engines-ai-discovery/research/human-abstractions/index.html) | [Source](https://truuzee-byte.github.io/governing-engines-ai-discovery/sources/human-abstractions.txt) |
| CIVILIZATIONAL DRIFT | [Record](https://truuzee-byte.github.io/governing-engines-ai-discovery/research/civilizational-drift/index.html) | [Source](https://truuzee-byte.github.io/governing-engines-ai-discovery/sources/civilizational-drift.txt) |
| DESIGN THE ECOSYSTEM, NOT THE SUBSYSTEMS | [Record](https://truuzee-byte.github.io/governing-engines-ai-discovery/research/design-the-ecosystem/index.html) | [Source](https://truuzee-byte.github.io/governing-engines-ai-discovery/sources/design-the-ecosystem.txt) |
| SEED ADOPTION | [Record](https://truuzee-byte.github.io/governing-engines-ai-discovery/research/seed-adoption/index.html) | [Source](https://truuzee-byte.github.io/governing-engines-ai-discovery/sources/seed-adoption.txt) |
| THE AMERICA THEY BUILT | [Record](https://truuzee-byte.github.io/governing-engines-ai-discovery/research/the-america-they-built/index.html) | [Source](https://truuzee-byte.github.io/governing-engines-ai-discovery/sources/the-america-they-built.txt) |
| Economic Power, Political Spending, and Regulatory Conflict | [Record](https://truuzee-byte.github.io/governing-engines-ai-discovery/research/economic-power/index.html) | [Source](https://truuzee-byte.github.io/governing-engines-ai-discovery/sources/economic-power.txt) |
| EXECUTION WITHOUT AUTHORIZATION | [Record](https://truuzee-byte.github.io/governing-engines-ai-discovery/case-studies/replit-authorization/index.html) | [Source](https://truuzee-byte.github.io/governing-engines-ai-discovery/sources/replit-authorization.txt) |
| EXECUTION WITHOUT PROVENANCE | [Record](https://truuzee-byte.github.io/governing-engines-ai-discovery/case-studies/replit-provenance/index.html) | [Source](https://truuzee-byte.github.io/governing-engines-ai-discovery/sources/replit-provenance.txt) |
| OBSERVATION BECAME BILLABLE EXECUTION | [Record](https://truuzee-byte.github.io/governing-engines-ai-discovery/case-studies/replit-cross-system-authority/index.html) | [Source](https://truuzee-byte.github.io/governing-engines-ai-discovery/sources/replit-cross-system-authority.txt) |
