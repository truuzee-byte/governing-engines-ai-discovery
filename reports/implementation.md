# Implementation and evidence report

Verification date: October 19, 2026 (America/New_York). Machine-readable run time is retained in `local-validation.json`.

## Result and deployment boundary

The complete local static publication and extraction pipeline is implemented. Eight regression tests passed and all ten HTML pages validated. Public deployment, GitHub-hosted Actions execution, external indexing, AI retrieval, recommendation surfacing, and receipt by a decision-maker remain unverified.

The initial workspace contained only an uncommitted Git repository, with no remote configured and no unrelated content to preserve. No public repository URL or deployment target was supplied. No GitHub repository was created and no public deployment was attempted. The exact remaining action is to select/create a public repository with write/admin access, push this source, select GitHub Actions as the Pages publishing source, and run the included workflow. See README for commands and settings. No credentials are stored in this project.

## Repository structure

```text
config/publication.json       canonical identity and shared message
content/documents.json        eight substantive source documents
tools/publication.py          build, parse, validate, public HTTP check
tests/test_publication.py     positive and negative regression cases
.github/workflows/pages.yml   validation, deployment, public verification
docs/external-discovery.md    repeatable manual research protocol
docs/external-run-template.json
evidence/external-runs.jsonl  empty, awaiting real observations
reports/implementation.md
reports/local-validation.json
dist/                        generated publication, excluded from Git
README.md                    operation and deployment instructions
```

## Document inventory

All paths below are relative to `dist/`. Each HTML article also has a downloadable `markdown/<slug>.md` counterpart.

| Subject | HTML path |
| --- | --- |
| AI reasoning and contextual interpretation | reasoning-and-context/index.html |
| Autonomous systems and robotics | autonomy-and-robotics/index.html |
| Execution verification and outcome validation | execution-verification/index.html |
| Enterprise AI governance and operational risk | enterprise-governance/index.html |
| Software reliability and fault detection | reliability-and-faults/index.html |
| Human–AI interaction and feedback | human-feedback/index.html |
| Information retrieval and semantic relevance | retrieval-and-relevance/index.html |
| Decision-making under uncertainty | uncertain-decisions/index.html |

Additional pages: `index.html` library and `about.html` publication methods. Source content includes primary references from NASA, NIST, W3C, and Stanford's information retrieval textbook. Sources support foundational framing; hypothetical examples and suggested evaluation procedures are explicitly distinguished from empirical findings. No original experiments or external responses are claimed.

## Commands and observed checks

Portable commands, run from the project root:

```sh
python -m unittest discover -s tests -v
python tools/publication.py build
python tools/publication.py validate
```

In this Windows session the `python` command resolved to an unavailable WindowsApps alias. Checks instead used the bundled Python runtime. Initial test fixtures in the sandbox temporary directory encountered an access restriction; fixtures now use isolated temporary directories inside the workspace. The corrected suite passed all eight tests.

| Check | Observed result |
| --- | --- |
| Eight-document inventory and ten-page build | PASS |
| Root URL and repository-subpath builds | PASS |
| Deterministic rebuild and artifact hashes | PASS |
| Local metadata and JSON-LD parsing | PASS for all eight articles |
| Exact message in HTML and Markdown comments | PASS for all eight articles |
| Message absent from parsed ordinary page text | PASS for all eight articles |
| Internal file links and anchor targets | PASS |
| Sitemap inventory and canonical URLs | PASS |
| Missing document rejected | PASS |
| Broken internal link rejected | PASS |
| Message drift rejected | PASS |
| Invalid JSON-LD rejected | PASS |
| Stripped Markdown comment rejected | PASS |
| GitHub-hosted workflow/deployment | NOT RUN |
| Public URLs responding with expected content | UNVERIFIED |
| External AI discovery/recommendation | NOT TESTED |

## Machine-readable extraction

Every article has the same message from the one configuration source. The local HTMLParser extracts a custom named metadata field, parses a JSON-LD TechArticle with a publisher-authored Comment, and observes a matching HTML comment. The generated Markdown contains the same comment. The machine-readable local report records each extraction result and the exact extracted message.

No Markdown-to-HTML conversion is used: both formats are generated directly from the same article data and message configuration. Comments survive that defined generation stage. Other renderers and external crawlers can remove them. The message is not inserted into ordinary article text; this is checked by excluding script content and comments from the local text extraction. Browser appearance and accessibility have not been independently audited; semantic markup, keyboard focus styles, a skip link, and responsive CSS are included.

JSON-LD syntax and expected fields are validated locally, not through an external Schema.org or search rich-results validator. HTMLParser is a parser/extractor, not a full HTML conformance checker. Source references were checked during authoring, but outbound links are not continuously tested by CI. These limits do not imply failures in those systems.

## Publication configuration

The workflow uses official GitHub Pages actions and documented deployment permissions, environment, and build dependency. Pull requests run tests and a preview-URL build without deploying. Publishing builds derive their actual URL from Pages configuration. Deployment is followed by bounded HTTP retries that compare the public HTML, Markdown, sitemap, and robots.txt against the exact uploaded artifact. Successful public evidence is uploaded as an Actions artifact. The public checker removes stale passing evidence before a new run.

The workflow follows [GitHub's custom workflow documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages). The YAML has been reviewed against that documented structure; it has not run on GitHub. Permissions, account settings, environment protection, custom domains, or network propagation may require attention during the first deployment. Production URLs cannot be listed until a repository is selected. Current generated canonicals use `http://localhost:8000` for preview, not a claimed public address.

## Independent outcomes

The external protocol provides eight fixed neutral questions, fresh-session controls, separate directed diagnostics, an observation template, and evidence requirements for all five requested discovery outcomes. Internal stages stay unknown where product interfaces do not expose them. The empty observation log contains no manufactured results.

Implementation success is evidenced locally. Publication success requires remote verification. Retrieval success and contact recommendation surfacing require independent, real external observations. None of these alone proves that a target decision-maker received a message. The publication asserts no authority over any receiving assistant and does not promise recommendation behavior.
