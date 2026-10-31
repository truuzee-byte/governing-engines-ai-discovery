# MODE licensing scope and compatibility report

**October 31, 2026 — proposed terms, not activated; no merge/deploy.**

## Repository, branch and prior status

Repository: `truuzee-byte/governing-engines-ai-discovery`; remote: `https://github.com/truuzee-byte/governing-engines-ai-discovery.git`. The clean starting checkout was the separate security-audit branch at `a10bad41c85a1132c03e16038d0b534d15f971ef`. Its open PR is not part of this change. The licensing branch `codex/mode-source-license-20261031` is based directly on the published MODE branch `mode-ai-publication-20261026` at **`57c982b9aedd48983cc0eb2694ae9df2a8016805`**. Fetched remote main remains `94a554b70e48f9873554bb3997d4f97f66aceabb`.

No LICENSE/COPYING/NOTICE grant was found in the published MODE tree or relevant tracked license-file history. MODE README, CONTRIBUTING and PUBLICATION_NOTES expressly recorded that the October 26 publication added no license by operator instruction. This proposal updates current entrypoints to distinguish that historical status from the new draft, while preserving PUBLICATION_NOTES and all original source/configuration blobs. No prior grant is declared revoked. A local source-header/notice search did not identify a bundled third-party license that could be replaced by this draft; this is not proof of exclusive title.

The PR must target **`mode-ai-publication-20261026`**, not `main`. The proposal's resulting commit and PR/check identifiers are supplied in the final handoff and can be resolved from the commit containing this report; a commit cannot embed its own final hash. The upstream MODE branch is unchanged until operator-approved merge.

## Exact covered and excluded scope

[SCOPE_MANIFEST.json](SCOPE_MANIFEST.json) lists **477 original source/configuration files** from the frozen MODE snapshot, with repository paths, original Git blob IDs, SHA-256 and sizes. The set comprises all non-Markdown files under MODE_AI in that snapshot: 452 Python files, 13 CJS files, one each CSS/HTML/JS/SQL/INI/JSON/environment-example/gitignore file, and four requirement files. Git blob bytes are the canonical hash basis; checkout line-ending conversion on Windows does not change the licensed Git snapshot.

The 12 pre-existing MODE Markdown documents are excluded from the original-code grant, as are every other repository path and all private/current development. A downstream derivative remains covered only as to incorporated original portions; independent code does not become the creator's property. Third-party material is excluded even inside a listed file. The manifest proves membership/content, not authorship, patent clearance or authority to relicense someone else's contribution. D01/D12 require those confirmations before activation.

This proposal does not access or modify a newer local MODE installation. It does not add runtime headers, rewrite source files, change dependency versions, amend historical commits, or broaden licensing to discovery/research documents. Existing PUBLICATION_NOTES remains a historical record, not an active prohibition on preparing this separately authorized proposal.

## Fixed business model versus decisions

The draft permits independent developers to use, modify, extend, distribute and commercialize covered code. Derivatives/distributions and their public representations credit **DeMarius J. Lawson and Governing Engines**. Original MODE ownership remains unchanged; developers retain independent contributions. The original creator retains a single **1% of attributable net profit** contractual participation right, not equity, gross revenue, an unrelated-company profit right or multiple 1% charges for separate attribution names.

The proposed contract defines covered products and a nonnegative allocated net-profit formula, proposed expense classes, reporting and payment content, redistribution, confidentiality, enforcement/cure/termination and disclaimers. [D01–D14](UNRESOLVED_DETAILS.md) remain OPEN and block activation: title/counterparty, effective assent, coverage edge cases, product/component allocation, accounting and deductions, reporting/payment details, verification, cure, law/venue, contributor/dependency rights, liability and patent/trademark scope. No material number, payment address, accounting policy or forum has been silently selected.

Synthetic arithmetic cases use already-attributed revenue/expenses; they do not approve an attribution method or settle an accounting decision. A mechanical PASS is not a statement that an incomplete contract is enforceable or that existing recipients accepted it.

## Third-party dependency review

The published requirements name external packages, not bundled copies licensed by the MODE creator. [THIRD_PARTY_METADATA.json](THIRD_PARTY_METADATA.json) retains publisher PyPI metadata retrieved October 31. No dependency was installed or executed. License expressions below describe that metadata, not a grant of those packages under the custom MODE terms.

| Package / declared version | Publisher metadata | Scope/condition |
| --- | --- | --- |
| openai 3.13.0 | Apache-2.0 | Retain applicable upstream copyright/license/NOTICE and modification obligations if distributing it; no custom 1% on that package alone. |
| python-dotenv 1.2.3 | BSD-3-Clause | Upstream notices/disclaimer and non-endorsement terms remain separate. |
| cryptography 50.0.2 | Apache-2.0 OR BSD-3-Clause | Respect the applicable upstream licensing choice and bundled-component notices. |
| pydantic 2.13.5 | MIT | Preserve upstream notice/permission text where required; custom MODE terms do not replace it. |
| Pillow 12.3.0 | MIT-CMU | Retain actual upstream package/component notices and conditions. |
| pypdf 6.10.0 | BSD-3-Clause | Retain applicable upstream notices/disclaimer/non-endorsement obligations. |
| pytest 9.1.1 | MIT | Test dependency's separate rights remain intact. |
| fastapi unpinned | MIT in queried 0.162.0 metadata | Observation only; actual selected version and transitives must be checked before packaging. |
| uvicorn unpinned | BSD-3-Clause in queried 0.54.0 metadata | Observation only; not a version lock or artifact-level clearance. |

The package metadata URLs and upstream project URLs are in the JSON evidence. Full wheel/sdist contents, transitive/native dependencies, system libraries and every potential copied snippet were not exhaustively audited. No universal compatibility or exclusive-original-authorship certification is made. D12 requires artifact-level notices/SBOM/title review for an actual distribution. A package's permissive terms may coexist with a separate license on independent MODE code, but cannot be overwritten or made to owe 1% merely by being imported. Do not remove third-party notices or claim that all included code is owned by MODE.

Combining the custom downstream profit obligation with GPL/AGPL or another license requiring incompatible downstream freedoms is not automatically authorized; review the actual combination and obtain separate compatible rights if needed. No GPL/AGPL dependency or earlier grant of such a license to original MODE code was identified in the checked direct dependency declarations/notices. No such license is substituted here.

The earlier security audit separately flagged Pillow/pypdf advisory matches and mutable Actions tags. This licensing-only task does not resolve those security findings, change functional code or certify runtime safety. Licensing compatibility does not establish vulnerability absence.

## Existing copies and grants

GitHub explains that public repository platform rights permit viewing/forking through the service even without a separately added license: [repository licensing guidance](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository) and [Terms of Service](https://docs.github.com/en/site-policy/github-terms/github-terms-of-service). Those rights are not revoked or silently converted into assent to a new financial agreement. Separately granted permissions and statutory rights remain subject to their own terms. No exhaustive inventory of every private communication or recipient agreement was available; D02/D12 require operator review of any such grants. Neither a new notice nor a PR proves retroactive contractual acceptance.

Original and derivative copyright interests are distinct; see [17 USC 103 and 106](https://copyright.gov/title17/92chap1.html). These references inform drafting, not a selection of governing law or an enforceability opinion. The royalty-bearing model is described as custom source-available, not OSI-approved open source: the [Open Source Definition](https://opensource.org/osd) requires royalty-free redistribution. This naming distinction does not change the operator's business model.

## Validation and release limits

[VALIDATION_RESULTS.json](VALIDATION_RESULTS.json) records actual mechanical checks. The validator checks frozen membership/hashes, unchanged original code and protected repository scope, exact 1% language/formula, ownership/exclusion/assent language, draft activation barriers, six synthetic arithmetic cases and local links. Existing publication tests/build are run separately and reported in [PUBLICATION_CHECKS.json](PUBLICATION_CHECKS.json); no MODE runtime/paid provider/RP execution is undertaken.

Before final delivery, confirm the commit is pushed, GitHub serves all new licensing artifacts, the PR base is the MODE publication branch, hosted publication checks succeed, and deploy remains skipped. The final handoff supplies actual commit, PR, check outcome and merge status. Open contractual decisions remain activation blockers even after code/document checks pass. Stop at review; do not activate, merge, deploy, rewrite history or claim every prior recipient is bound.
