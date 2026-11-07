# Source-bound DocumentModel view

Document System v2.0 section 4 governs the structured view exposed by
`/documents model` and MODEL_JSON export. The canonical source remains the exact
versioned DocumentService/CustodyStore record. DocumentModel is a derived view,
not an independently approved source or a replacement for source bytes.

Identity/version, owner permissions, declared authority, lifecycle, pool, source
and derivation lineage, validation references and custody approval are retained.
Missing claims, citations, figure interpretation and rendered proof remain unknown.
Latest-version status is evaluated when retrieving the view; its model hash binds
that view, while version_id continues to bind the immutable source record.

DOCX paragraphs use XML-part locators. Tables retain cell-to-paragraph references
and explicit merge attributes. Section properties preserve XML names/attributes;
they are not interpreted as semantic sections. PDF pages retain page-to-segment
references. Neither mechanism proves visual reading order, pagination fidelity,
layout, or rendered output. MODEL_JSON is serialization, not rendering.

`/documents passage` retrieves one exact segment ID from a pinned source version.
New versions do not substitute their text for a historical passage; missing IDs
are unavailable, not proof that the requested matter was never specified.

The existing intake, authority reconciliation, derivation, version history,
exact structured doc-to-spec and receipts remain canonical. General prose-to-spec,
full layout/finalization and protected parser/render execution are not implied by
the structured view.

`/documents restore` requires exact DOCUMENT_RESTORE approval, a pinned source
version, the current expected hash and a reason. It appends the original content
as a new version with restoration lineage. It never replaces older rows, rewinds
version numbers or changes DocumentAuthority selection. Validation remains
UNPROVEN; prior evidence references are retained as references, not renewed proof.
