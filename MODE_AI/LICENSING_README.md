# MODE licensing proposal

**October 31, 2026: operator review draft. No merge, activation or existing-recipient assent is asserted.**

Developers are intended to be able to use, modify, extend and commercialize covered MODE code, while crediting **DeMarius J. Lawson and Governing Engines** and paying exactly **1% of attributable net profit** on covered commercial products/services. Developers keep their independently created contributions; original MODE ownership remains unchanged. This is a custom source-available business license, not a replacement conventional open-source license and not company equity.

- [Custom MODE Source License](MODE_SOURCE_LICENSE.md): contractual definitions, grant, attribution, 1% calculation, reporting, redistribution, enforcement and disclaimers.
- [Attribution notice](ATTRIBUTION_NOTICE.md): distribution/public-representation credit and draft copyright-owner field.
- [Exact scope manifest](licensing/SCOPE_MANIFEST.json): immutable snapshot file list and hashes; no floating private-code coverage.
- [Scope and compatibility report](licensing/SCOPE_AND_COMPATIBILITY.md): prior notices, dependencies, scope exclusions and earlier-copy limits.
- [Unresolved-detail register](licensing/UNRESOLVED_DETAILS.md) and [unapproved activation schedule](licensing/ACTIVATION_SCHEDULE.json): material decisions requiring operator approval.
- [Validation results](licensing/VALIDATION_RESULTS.json): performed mechanical checks; not a legal-enforceability opinion or runtime qualification.

The proposal targets **`mode-ai-publication-20261026`**, not `main` and not the separate publication/security-audit PR. It changes licensing documentation and adds review/validation artifacts only. No functional MODE code, research corpus, private implementation or historical commit is altered.

The exact pre-license snapshot is `57c982b9aedd48983cc0eb2694ae9df2a8016805`. Existing October 26 statements that no license had been added were true of that publication and are preserved as historical facts. This new draft does not retroactively bind existing users or revoke valid earlier/platform grants.

## Review and activation

Review the fixed business terms first, then resolve D01–D14. Confirm ownership/licensing authority and third-party exclusions; select the accounting, allocation, reporting, payment and enforcement details explicitly. Retain the 1% rate and both attribution names. Approve a final license and an effective, accepted agreement using the resolved schedule. Merging a PR or toggling a JSON status is not by itself proof of acceptance, title or legal enforceability. No active license is claimed while activation blockers remain.

The operator should obtain legal/accounting review of the custom agreement and completed schedule before offering it for acceptance. The draft is complete for substantive review, but unresolved material choices prevent describing it as an executed or commercially effective license.

## Reproduce mechanical validation

From the repository root, using Python 3.12+:

```sh
python MODE_AI/licensing/validate_licensing.py
python -m unittest discover -s tests -v
python tools/publication.py build --base-url https://truuzee-byte.github.io/governing-engines-ai-discovery
python tools/publication.py validate --base-url https://truuzee-byte.github.io/governing-engines-ai-discovery
```

The licensing validator is separate from MODE runtime and does not install packages, call providers, alter operational state or activate terms. The existing publication workflow runs publication tests/build on the PR and skips deployment.
