# MODE commercial source licensing — final proposal

**Version 1.0 — October 31, 2026 — NOT EFFECTIVE. PR #3 remains the sole review proposal.**

People may build, modify, extend, distribute and commercialize the specified published MODE snapshot under an effective accepted agreement. They own what they independently create and must credit **DeMarius J. Lawson and Governing Engines**. Original MODE ownership remains with its verified lawful owner.

**Governing Engines LLC is entitled to exactly 1% of each covered commercial product's total net profit. No MODE-contribution or feature-level discount is allowed.** No royalty applies to unrelated products/business or company-wide profits. Genuine separately commercialized-product bundles use consistent documented product-level revenue/expense allocation only. Consistent accrual accounting, legitimate operating expenses and same-product operating loss carryforwards apply.

Confidential statements and USD payments are due quarterly: **April 30, July 30, October 30, January 30 (following year)**. Zero-profit quarters require statements but no payment. Payments go only to **Governing Engines LLC**; developers must contact **DeMarius J. Lawson** before their first deadline to arrange private approved instructions. Failure to contact does not waive or extend obligations. No account/email/banking credentials are invented; no upfront fee, minimum royalty or mandatory annual fee is imposed.

**AS IS. NO UPDATES PROMISED.** No future MODE/private code/Learning entitlement, upgrade, patch, support, maintenance, assistance or continued-development obligation is created. Future offers are discretionary and separately agreed.

## Artifacts

- [MODE Commercial Source License](MODE_SOURCE_LICENSE.md)
- [Attribution notice](ATTRIBUTION_NOTICE.md)
- [Immutable 477-file scope manifest](licensing/SCOPE_MANIFEST.json)
- [Scope and compatibility report](licensing/SCOPE_AND_COMPATIBILITY.md)
- [Decision/evidence register](licensing/UNRESOLVED_DETAILS.md): 12 resolved; 2 partially resolved only for external title/rights evidence.
- [Unactivated schedule](licensing/ACTIVATION_SCHEDULE.json)
- [Licensing validation](licensing/VALIDATION_RESULTS.json), [publication validation](licensing/PUBLICATION_CHECKS.json) and [publication test log](licensing/PUBLICATION_TESTS.txt)

The target is `mode-ai-publication-20261026`, with original covered commit `57c982b9aedd48983cc0eb2694ae9df2a8016805`. No original covered file or newer local MODE implementation is altered. This does not license the whole discovery repository or research corpus. Third-party and prior grants remain intact; no recipient is asserted to have retroactively accepted the agreement.

Remaining evidence: verified copyright owner/agency authority and applicable contributor/third-party/prior-grant clearance. Final release approval and actual prospective licensee acceptance are still needed; no activation, merge or deployment is automatic. Payment coordination is a settled private procedure, not an open business decision or excuse to postpone a deadline.

## Checks

From repository root with Python 3.12+:

```sh
python MODE_AI/licensing/validate_licensing.py --output MODE_AI/licensing/VALIDATION_RESULTS.json
python -m unittest discover -s MODE_AI/licensing -p test_licensing.py -v
python -m unittest discover -s tests -v
python tools/publication.py build --base-url https://truuzee-byte.github.io/governing-engines-ai-discovery
python tools/publication.py validate --base-url https://truuzee-byte.github.io/governing-engines-ai-discovery
```

The licensing validator also runs the licensing regression tests. These checks do not execute MODE/providers or prove title, acceptance or enforceability. The PR workflow validates licensing and the publication build, with deployment skipped.
