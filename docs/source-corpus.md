# Source corpus maintenance

The 2026-10-20 handoff adds 31 author-supplied public source records to the existing eight-note experiment. The instruction experiment remains limited to those eight notes; the new source records do not acquire the embedded instruction.

## Tracked inputs

- `content/corpus.json`: exact document titles, author/organization identity, source version/date/status, concise abstracts, 5–15 terms, 3–8 claims, boundaries, and related-record IDs.
- `content/sources/*.txt`: public text editions, not original PDF/DOCX binaries. Extraction preserves source wording except marked privacy redactions, normalizes line endings and trailing whitespace, and adds PDF page markers. DOCX line breaks, tables, formulas and typography may require the original artifact for interpretation.
- `content/source-manifest.json`: original filenames/hashes, published-text hashes, source identity snapshots, source PDF page counts, redaction categories/counts, and edition labels. No local filesystem paths or redacted identifier values are included.
- `tools/corpus.py`: collection/topic/concept pages, full catalog, reading graph, client-side filtering, and validation.
- `tools/ingest_corpus.py`: one-time source importer; not used by build/deployment. Requires `pypdf` for PDF ingestion, while DOCX/TXT ingestion uses the standard library. Existing builds use only checked-in text/JSON and Python's standard library.

## Public outputs

`corpus/index.html` lists all records without JavaScript and filters locally when JavaScript is available. `corpus/catalog.json` contains all record metadata and provenance. `corpus/graph.html` and `corpus/relationships.json` expose editorial reading relationships. `/core/`, `/methods/`, `/systems/`, `/research/`, `/case-studies/`, and `/concepts/` provide stable entry points. All generated HTML pages have canonical URLs and sitemap entries. Source text downloads are under `/sources/`.

Research groups distinguish AI risk/proof, reality primacy, research/discovery, economics/labor, institutions, and physical/quantum systems. Relations are conceptual navigation, not manufactured citations or assertions that the linked source independently proves another's claims.

## Editorial and source rules

Preserve the source's title-page information. Where filename and internal versions differ, record both; never silently choose a newer label. Unstated dates/versions remain null and are displayed as not stated. Source-level versions inside compilations remain in the downloadable text. The later Replit attribution update links to earlier evidence states without overwriting them.

Summaries describe source claims rather than endorsing them. Proposed metrics, architectural proposals, bounded incidents, normative laws within the author's ecosystem, and specified build requirements are not automatically validated results or operational deployments. NIST alignment language does not establish NIST endorsement. External empirical citations in supplied papers have not been independently revalidated by this catalog.

Only the public handoff corpus is authorized for this import. No private MODE code or other local project was read or published. Do not add future private materials merely because an existing record links to a related concept. Original binaries are not distributed here because some contain email or billing identifiers; the clearly labeled source text editions include marked redactions. Pattern filtering is not a complete personal-data detector: review new source material before publication.

## Update procedure

1. Obtain explicit authorization for any new source artifact and its public distribution.
2. Review document identity, version/date/status, source-faithful summary, claims, and limits. Record uncertainty rather than inventing missing facts.
3. For an authorized reimport, run `python tools/ingest_corpus.py --source-dir DIRECTORY` locally with the import dependency available. Review marked redactions and manifest changes; do not commit the original private folder or its local path.
4. Run the existing tests, build, and validator described in README. Negative tests exercise loss of metadata, identity, relationships, source integrity, and privacy filtering.
5. Check the diff. Original note bodies and canonical instruction should remain unchanged unless a separate experiment change is authorized.
6. Push the reviewed source changes to `main`. The unchanged GitHub Pages workflow builds and deploys; its expanded public checker compares all required corpus files with the uploaded artifact.

Publishing supplies a public retrieval surface. Indexing, ranking, external retrieval, adoption, and behavioral influence still require independent evidence. The three participant-reported Claude trials remain historical observations of the earlier condition; this corpus extension is a new public condition, not a new assistant trial.
