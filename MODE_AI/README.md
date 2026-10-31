# MODE AI — development source

Publication preparation: October 26, 2026. This directory contains the actual implemented Python research system and tests, with the staged-only privacy and portability changes listed in [PUBLICATION_NOTES.md](PUBLICATION_NOTES.md). It is source for review and bounded reproduction, not a packaged or generally qualified autonomous product.

MODE separates operator input, Understanding, reasoning, Observation, Reality Primacy (RP), consequence analysis, Learning, memory, context admission and governed action execution. The model proposes text and actions; stored evidence and approval remain separate from execution authority. See [ARCHITECTURE.md](ARCHITECTURE.md).

Implemented paths include draft/critique/final reasoning; versioned Understanding; explicit persistent-memory consent; evidence-linked Learning admission and semantic projection; runtime self-inspection; structured builder handoff; and bounded governed directory inspection/file reading. Existence of these implementations does not establish general Learning, autonomous objective pursuit or safe unrestricted execution.

Historical controlled demonstrations established scoped Learning Expression and one bounded synthetic cross-thread-memory case. Those are limited prior results, not a new qualification of this publication copy. Private behavioral traces are deliberately excluded. Current deterministic validation below establishes only the named offline test scope. Broad Learning and Objective Continuity are not demonstrated by these tests; Objective Continuity classification remains F. Pass 3, Frozen60 readiness and the closed Development Program gate are not changed by publication.

## Setup and offline tests

Use Python 3.12+; the publication checks used Python 3.12. Run from this `MODE_AI` directory in a disposable checkout, outside any operational MODE installation:

```sh
python -m venv .venv
# Activate the environment for your shell, then:
python -m pip install -r requirements-test.txt
python -m pytest -c pytest-offline.ini -q
```

Installation is a collaborator step; no packages were installed for publication. Requirements record observed dependency versions, not a complete transitive lock or proof of clean-machine installation. The bounded test set passed **189 tests**; all **452 Python source files** compiled. Tests use synthetic data and temporary files. One test starts two explicitly specified local Python commands. Never run unfamiliar tests with production credentials or operational state available. See [TESTING.md](TESTING.md) for omissions and retained harness failures.

## Local interfaces and charges

Review configuration before starting runtime. Copy `.env.example` to ignored `.env` and supply your own credentials only when you intend to authorize provider use. `data/model_config.json` is the original non-secret sample configuration. It is not an authorization or spending limit.

```sh
python interactive_mode_ai.py
```

The interactive shell initializes local operator/state stores and may send governed context to OpenAI during reasoning. A reasoning turn normally contains draft, critique and final model requests; semantic interpretation can add calls. SDK retries and usage are not uniformly bounded by an application-wide budget. Starting the shell is not a promise of offline operation. No provider calls were made during this publication.

The optional local runtime UI is implemented in `frontend/server.py` and `frontend/runtime_view.py`; inspect `interactive_mode_ai.py` for its current integration. Browser smoke tests additionally require a compatible Node/Playwright distribution and browser installation; none is bundled or installed here. Set `MODE_NODE_RUNTIME` to its root only if using these tests.

Optional supervisor bridge:

```sh
python -m pip install -r requirements-bridge.txt
# Set a fresh local MODE_SUPERVISOR_TOKEN before starting:
python -m supervisor_bridge.app
```

The bridge defaults to loopback and requires a token. Its optional dependencies and HTTP startup were not validated in the publication environment. Repository API scope in this copy is the checkout root. Do not expose this development service publicly or use private runtime data as example content.

## External boundaries

RP is a separate dependency and is not bundled. Governed live actions require the actual compatible verifier, independent evidence, grants, signatures and current scoped Understanding. Missing RP is not replaced with an approving mock. The retained guarded filesystem implementation is Windows-specific: tested engineering scope is 64-bit Windows on local fixed NTFS, with fail-closed handling for unsupported environments. A symbolic-link privilege test remains a historical limitation; do not infer universal containment qualification.

The objective adapter supports governed `INSPECT_DIRECTORY` and `READ_FILE`; it does not implement arbitrary organization/move/write actions. The separate Builder bootstrap can execute approved host-user commands and is **not an OS sandbox**. Kernel cutover preparation is not protected-kernel activation. Review `builder/kernel/CUTOVER_PREPARATION_CONTRACT.md` before using Builder.

## Exclusions and collaboration

Credentials, profiles, conversations, persistent memory, state databases, logs, telemetry, historical artifacts, generated builds and external RP contents are absent. Some retained tests and diagnostic catalogues refer to those missing private artifacts; absence is intentionally visible, not replaced with fabricated evidence. A bare whole-tree test run is not the supported reproduction command.

Read [CONTRIBUTING.md](CONTRIBUTING.md) before proposing changes. The October 26 snapshot was published without an added license, as recorded in [PUBLICATION_NOTES.md](PUBLICATION_NOTES.md).

## MODE commercial source license — corrected final proposal

The [version 1.0 licensing proposal](MODE_SOURCE_LICENSE.md) permits commercial building/modification of the frozen published snapshot once effective and accepted, with credit to DeMarius J. Lawson and Governing Engines. **Exactly 1% of each covered commercial product's total net profit is payable quarterly to Governing Engines LLC; no MODE-contribution or feature-level discount.** Unrelated products/business and independent ownership are excluded. Contact DeMarius J. Lawson before the first payment deadline for private approved instructions; failure to contact does not waive or extend obligations.

**AS IS. NO UPDATES PROMISED.** No future versions/private code/Learning, patches, support, maintenance or continued development is promised. See the [licensing README](LICENSING_README.md), [attribution notice](ATTRIBUTION_NOTICE.md) and [decision/evidence register](licensing/UNRESOLVED_DETAILS.md): 12 resolved; 2 partially resolved solely for title/rights evidence. This remains **NOT EFFECTIVE** pending authorized release and actual acceptance; no automatic activation, merge, deployment or retroactive binding. The discovery research corpus and newer private MODE are not licensed by this proposal.
