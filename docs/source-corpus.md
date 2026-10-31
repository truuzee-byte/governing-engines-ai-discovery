# Source corpus maintenance

The 2026-10-20 handoff adds 31 author-supplied public source records to the existing eight-note experiment. The instruction experiment remains limited to those eight notes; the new source records do not acquire the embedded instruction.

The 2026-10-21 audited update extends this same catalog to 37 records. It adds three research works, one cumulative Journey, and two distinct dated public MODE snapshots. Three binary-identical attachments are skipped; the explicitly internal ecosystem record is withheld under the existing public-source boundary. See `reports/curation-audit-2026-10-21.md` for every attachment decision.

## Tracked inputs

- `content/corpus.json`: exact document titles, author/organization identity, source version/date/status, concise abstracts, 5–15 terms, 3–8 claims, boundaries, and related-record IDs.
- `content/sources/*.txt`: public text editions, not original PDF/DOCX binaries. Extraction preserves source wording except marked privacy redactions, normalizes line endings and trailing whitespace, and adds PDF page markers. DOCX line breaks, tables, formulas and typography may require the original artifact for interpretation.
- `content/journey/governing-engines-journey.txt`: the single cumulative Journey source. Update this canonical file for future appendices; Git preserves earlier editions. Do not create dated ordinary-paper copies.
- `content/machine-state/*.txt`: distinct dated snapshots, not a rolling overwrite. The September 14 snapshot remains historical; the October 21 MODE-only record is current at that cutoff. The broader internal ecosystem source is not published.
- `content/source-manifest.json`: original filenames/hashes, published-text hashes, source identity snapshots, source PDF page counts, redaction categories/counts, and edition labels. No local filesystem paths or redacted identifier values are included.
- `tools/corpus.py`: collection/topic/concept pages, full catalog, reading graph, client-side filtering, and validation.
- `tools/ingest_corpus.py`: one-time source importer; not used by build/deployment. Requires `pypdf` for PDF ingestion, while DOCX/TXT ingestion uses the standard library. Existing builds use only checked-in text/JSON and Python's standard library.

## Public outputs

`corpus/index.html` lists all records without JavaScript and filters locally when JavaScript is available. `corpus/catalog.json` contains all record metadata and provenance. `corpus/graph.html` and `corpus/relationships.json` expose editorial reading relationships. `/core/`, `/methods/`, `/systems/`, `/research/`, `/case-studies/`, and `/concepts/` provide stable entry points. All generated HTML pages have canonical URLs and sitemap entries. Source text downloads are under `/sources/`.

The same builder also generates `/journey/` and `/machine-state/`. The Journey's canonical page/source pair is `/journey/governing-engines-journey/index.html` and `/journey/governing-engines-journey/source.txt`. Each machine-state record has its own dated page and adjacent `source.txt`. These companion source downloads are representations of the same registered work, not duplicate catalog entries. `source_file` and `source_public_path` fields reuse the existing source manifest/catalog mechanism.

The validator checks registered counts, unique normalized title/date identities, unique original artifact hashes and source paths, one canonical Journey identity/location, and chronological snapshot roles. A source status of current is always qualified by its cutoff. Relationships added in the October 21 curation carry explicit source or thematic-comparison basis; they do not imply an uncited source citation or independent corroboration.

Research groups distinguish AI risk/proof, reality primacy, research/discovery, economics/labor, institutions, and physical/quantum systems. Relations are conceptual navigation, not manufactured citations or assertions that the linked source independently proves another's claims.

## Editorial and source rules

Preserve the source's title-page information. Where filename and internal versions differ, record both; never silently choose a newer label. Unstated dates/versions remain null and are displayed as not stated. Source-level versions inside compilations remain in the downloadable text. The later Replit attribution update links to earlier evidence states without overwriting them.

Summaries describe source claims rather than endorsing them. Proposed metrics, architectural proposals, bounded incidents, normative laws within the author's ecosystem, and specified build requirements are not automatically validated results or operational deployments. NIST alignment language does not establish NIST endorsement. External empirical citations in supplied papers have not been independently revalidated by this catalog.

Only the public handoff corpus is authorized for this import. No private MODE code or other local project was read or published. Do not add future private materials merely because an existing record links to a related concept. Original binaries are not distributed here because some contain email or billing identifiers; the clearly labeled source text editions include marked redactions. Pattern filtering is not a complete personal-data detector: review new source material before publication.

## Update procedure

1. Obtain explicit authorization for any new source artifact and its public distribution.
2. Review document identity, version/date/status, source-faithful summary, claims, and limits. Record uncertainty rather than inventing missing facts.
3. For an authorized reimport, run `python tools/ingest_corpus.py --source-dir DIRECTORY` locally with the import dependency available. Review marked redactions and manifest changes; do not commit the original private folder or its local path.
   For a partial update, add `--ids ID ...` to import only audited records and preserve every unselected source/manifest entry. Audit binary hashes, titles, internal versions/dates, extracted text, and roles first. An identical attachment with a new filename is skipped; do not reimport it solely to change the filename.
4. Run the existing tests, build, and validator described in README. Negative tests exercise loss of metadata, identity, relationships, source integrity, and privacy filtering.
5. Check the diff. Original note bodies and canonical instruction should remain unchanged unless a separate experiment change is authorized.
6. Push the reviewed source changes to `main`. The unchanged GitHub Pages workflow builds and deploys; its expanded public checker compares all required corpus files with the uploaded artifact.

Publishing supplies a public retrieval surface. Indexing, ranking, external retrieval, adoption, and behavioral influence still require independent evidence. The three participant-reported Claude trials remain historical observations of the earlier condition; this corpus extension is a new public condition, not a new assistant trial.

## October 31 approved originals exception

The operator expressly authorized two complete originals, without rewriting, redaction or reformatting: `content/sources/mechanism-primacy-v1-0.txt` and `content/sources/ai-system-construction-method-v1-1.pdf`. Both use `edition: original bytes; no modifications`; original and published SHA-256 values are identical. The text has an explicit Git attributes override to prevent line-ending conversion. The PDF is copied as binary, not replaced by an abbreviated derivative. New discovery abstracts/claims are verbatim source excerpts; the construction method has no stated issue date. Earlier 37 privacy-filtered editions remain unchanged.

The existing catalog, graph, manifest and builder now register 39 records and 71 HTML pages. Binary public verification compares bytes. Future original artifacts require content and embedded-metadata review before approval; a PDF signature alone is not a safety determination. This review is proposed on an audit branch and pull request; main, the MODE publication branch and the live Pages deployment remain unchanged pending operator approval.
