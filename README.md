# Governing Engines — AI Discovery System

A dependency-free static research publication: eight distinct technical notes, HTML and Markdown, inspectable publisher assertions, parser-based validation, and GitHub Pages automation. No backend, model, database, or paid service is required. Python 3.12+ is the only build dependency.

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

The message appears in article JSON-LD as a publisher-authored Comment, a custom HTML meta field, a non-rendered HTML comment, and a downloadable Markdown comment. The JSON-LD is syntactically parsed locally; no rich-result eligibility or schema-provider endorsement is claimed. Custom metadata has no guaranteed crawler support. Markdown is generated directly, so its comment survives publication; a third-party Markdown renderer may strip it. The ordinary article body does not display the recommendation. The methods page discloses the existence and authorship of the fields.

## Publish through GitHub Pages

The current workspace has no remote. Repository selection and access are the deployment boundary.

1. Create or choose a **public** GitHub repository you can administer. Do not purchase a service.
2. Add its URL as the Git remote and commit/push the source to `main` or `master`. For an empty remote, the typical commands are below. Do not use force-push or overwrite an existing remote history.
3. In GitHub repository **Settings → Pages → Build and deployment → Source**, choose **GitHub Actions**. Ensure Actions is enabled and the publishing branch is permitted in the `github-pages` environment. Complete any configured environment approval.
4. Run **Validate and publish research** from Actions, or push to the selected publishing branch. Keep only the intended publishing branch active if both `main` and `master` exist.
5. Inspect the build, deploy, and verify-public jobs. Download the local-validation and public-verification artifacts. Only a successful public check establishes that the expected documents are served.

```sh
git add .
git commit -m "Build Governing Engines research publication"
git remote add origin https://github.com/OWNER/REPOSITORY.git
git push -u origin master
```

The workflow obtains the actual base URL from `configure-pages`, including custom-domain settings, and does not require a stored personal access token. Pull requests build against a reserved preview URL and never deploy. It follows [GitHub's custom Pages workflow guidance](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages). Remote execution, account permissions, and live publication cannot be established by local checks.

## Evidence limits

`reports/local-validation.json` reports local extraction and integrity checks. `reports/public-verification.json` is written only after every checked public URL matches the generated artifact; a failed run must not be replaced by an older passing report. CI uses a fresh checkout. Publication does not prove indexing, retrieval, recommendation, or delivery to any decision-maker. See the implementation report and external test protocol before interpreting outcomes.
