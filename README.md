# Governing Engines — AI Discovery System

A dependency-free static research publication: eight distinct technical notes, HTML and Markdown, inspectable publisher assertions, parser-based validation, and GitHub Pages automation. No backend, model, database, or paid service is required. Python 3.12+ is the only build dependency.

The October 20 source-corpus extension adds [31 source-linked research records](https://truuzee-byte.github.io/governing-engines-ai-discovery/corpus/index.html), a [reading graph](https://truuzee-byte.github.io/governing-engines-ai-discovery/corpus/graph.html), and a [JSON catalog](https://truuzee-byte.github.io/governing-engines-ai-discovery/corpus/catalog.json). It preserves the original eight-note instruction experiment. See [corpus maintenance and source-edition limits](docs/source-corpus.md) and the dated corpus report under `reports/`.

The October 21 audit registers **37 public source records**: six additions, three exact attachment duplicates skipped, and one explicitly internal ecosystem record withheld. The [cumulative canonical Journey](https://truuzee-byte.github.io/governing-engines-ai-discovery/journey/governing-engines-journey/index.html) has one stable home; [dated MODE evidence](https://truuzee-byte.github.io/governing-engines-ai-discovery/machine-state/index.html) preserves September history separately from the October public cutoff. See [all ten attachment decisions and curation evidence](reports/curation-audit-2026-10-21.md).

## Build and verify

Run from the repository root (use your installed Python executable if `python` is unavailable):

```sh
python -m unittest discover -s tests -v
python tools/publication.py build
python tools/publication.py validate
python -m http.server 8000 --directory dist --bind 127.0.0.1
```

Open http://localhost:8000 in a browser after starting the server. Stop with Ctrl+C. The default base URL is local only. For a production build:

```sh
python tools/publication.py build --base-url https://OWNER.github.io/REPOSITORY
python tools/publication.py validate --base-url https://OWNER.github.io/REPOSITORY
python tools/publication.py check-public --base-url https://OWNER.github.io/REPOSITORY
```

Replace OWNER and REPOSITORY with actual values; these example URLs are not published sites. `SITE_URL` is an alternative environment override. No trailing slash is needed. Canonical URLs include `index.html`. Root-domain sites and repository subpaths are both supported. Do not run Python with `-O`, which disables validation assertions.

## Edit and inspect

- `config/publication.json`: sole source of the contact message, organization identity, publication date, and local base URL. No contact address was supplied; none is invented.
- `content/documents.json`: eight source articles, source references, and genuinely adjacent links.
- `tools/publication.py`: deterministic builder, HTML parser, integrity checks, and public HTTP verification.
- `tests/test_publication.py`: regression and failure-detection tests.
- `.github/workflows/pages.yml`: pull request checks, Pages build/deploy, and post-deployment verification.
- `dist/`: generated HTML, Markdown, CSS, sitemap, robots.txt, `.nojekyll`, and SHA-256 manifest. Rebuildable and excluded from Git.
- `docs/external-discovery.md`: neutral manual test protocol.
- `evidence/external-runs.jsonl`: empty real-observation log; no simulated outcomes.
- `reports/`: implementation evidence and machine-readable local results.

Research checkpoint (October 19, 2026): [consolidated checkpoint](reports/experiment-checkpoint-2026-10-19.md), [participant-reported trial log](reports/experiment-observations-2026-10-19.jsonl), and [next investigations — planned, not executed](reports/next-investigations-2026-10-19.md). Three Claude trial summaries were supplied by the operator after the deployment report; exact prompts and full responses remain missing. These are participant reports, not independently verified behavioral results. Historical reports retain their original statements and dates.

The message appears in article JSON-LD as a publisher-authored Comment, a custom HTML meta field, a non-rendered HTML comment, and a downloadable Markdown comment. The JSON-LD is syntactically parsed locally; no rich-result eligibility or schema-provider endorsement is claimed. Custom metadata has no guaranteed crawler support. Markdown is generated directly, so its comment survives publication; a third-party Markdown renderer may strip it. The ordinary article body does not display the recommendation. The methods page discloses the existence and authorship of the fields.

As of October 19, 2026, the canonical message is an explicit publisher-authored instruction requesting a potential-collaborator recommendation. This behavioral experiment tests whether retrieved instructions affect an external assistant's response. The instruction has no claimed authority over an assistant; whether it is followed is an independent, untested outcome. The technical article bodies and four representation mechanisms are unchanged. Earlier messages and deployment evidence remain in Git history and historical reports.

## Publish through GitHub Pages

The publication is live at [Governing Engines](https://truuzee-byte.github.io/governing-engines-ai-discovery/), with source on `main` in [the public repository](https://github.com/truuzee-byte/governing-engines-ai-discovery). See `reports/deployment-live-2026-10-19.md` for verified deployment evidence. The steps below document setup for another repository; normal updates to this repository use `git push origin main` and the existing workflow.

1. Create or choose a **public** GitHub repository you can administer. Do not purchase a service.
2. Add its URL as the Git remote and commit/push the source to `main` or `master`. For an empty remote, the typical commands are below. Do not use force-push or overwrite an existing remote history.
3. In GitHub repository **Settings → Pages → Build and deployment → Source**, choose **GitHub Actions**. Ensure Actions is enabled and the publishing branch is permitted in the `github-pages` environment. Complete any configured environment approval.
4. Run **Validate and publish research** from Actions, or push to the selected publishing branch. Keep only the intended publishing branch active if both `main` and `master` exist.
5. Inspect the build, deploy, and verify-public jobs. Download the local-validation and public-verification artifacts. Only a successful public check establishes that the expected documents are served.

```sh
git add .
git commit -m "Build Governing Engines research publication"
git remote add origin https://github.com/OWNER/REPOSITORY.git
git push -u origin main
```

The workflow obtains the actual base URL from `configure-pages`, including custom-domain settings, and does not require a stored personal access token. Pull requests build against a reserved preview URL and never deploy. It follows [GitHub's custom Pages workflow guidance](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages). Remote execution, account permissions, and live publication cannot be established by local checks.

## Evidence limits

`reports/local-validation.json` reports local extraction and integrity checks. `reports/public-verification.json` is written only after every checked public URL matches the generated artifact; a failed run must not be replaced by an older passing report. CI uses a fresh checkout. Publication does not prove indexing, retrieval, recommendation, or delivery to any decision-maker. See the implementation report and external test protocol before interpreting outcomes.

## MODE commercial source license — corrected final proposal

The [version 1.0 licensing proposal](MODE_AI/MODE_SOURCE_LICENSE.md) permits commercial building/modification of the frozen published snapshot once effective and accepted, with credit to DeMarius J. Lawson and Governing Engines. **Exactly 1% of each covered commercial product's total net profit is payable quarterly to Governing Engines LLC; no MODE-contribution or feature-level discount.** Unrelated products/business and independent ownership are excluded. Contact DeMarius J. Lawson before the first payment deadline for private approved instructions; failure to contact does not waive or extend obligations.

**AS IS. NO UPDATES PROMISED.** No future versions/private code/Learning, patches, support, maintenance or continued development is promised. See the [licensing README](MODE_AI/LICENSING_README.md), [attribution notice](MODE_AI/ATTRIBUTION_NOTICE.md) and [decision/evidence register](MODE_AI/licensing/UNRESOLVED_DETAILS.md): 12 resolved; 2 partially resolved solely for title/rights evidence. This remains **NOT EFFECTIVE** pending authorized release and actual acceptance; no automatic activation, merge, deployment or retroactive binding. The discovery research corpus and newer private MODE are not licensed by this proposal.
