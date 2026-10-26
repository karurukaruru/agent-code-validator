# Testing and verification — 0.5.0

Local full suite: **333 passed, 4 skipped** on CPython 3.12.13 / pytest 8.4.2,
recorded in `evidence/tests/pytest-050.txt`. The four skips require Windows
symlink privileges. The initial run had two legacy local HTTP integration tests
fail with proxy HTTP 502; bypassing the system proxy for localhost with
`NO_PROXY=127.0.0.1,localhost,::1` made both pass, and the full recorded run uses
that environment setting. This does not bypass or mock a real model service.

The current installed SDK matrix is **4/4 expected outcomes** at
`evidence/upgrade-run-050/real-sdk/matrix.json`, with zero provider requests.
Wheel isolation passed in `evidence/tests/wheel-verification-050.json`.
The judge export passed **22 Chrome checks** at desktop and mobile widths in
`evidence/judge-browser-050`; replay performs no inference requests. English
137-second development-video decode/visual evidence is in
`evidence/video-development-050`.

New synthetic tests cover exact model identity, assistant/finish/refusal checks,
reasoning metadata isolation, persisted failures, shared cross-process budgets,
scoped plan reuse, fixed evaluation arms, and false-positive submission gates.
Real DeepSeek HTTP records are separately frozen under `evidence/development-050`.
NVIDIA/Nebius model inference remains pending access. New remote CI has not yet
been recorded at this local checkpoint.

## Historical verification

# Testing and verification — 0.4.0

Current local suite: **222 passed, 4 skipped**, CPython 3.12.13 / pytest 8.4.2.
Raw output: `evidence/tests/pytest-040.txt`. Added protocol and upgrade tests cover
malformed streams, ambiguous identities, unchanged broken outputs, environment
tampering, stale pins/runtime, dependency drift, credential isolation, sensitive
argument omission, worker failures and preserved evidence.

The actual installed SDK matrix has **4/4 expected outcomes** in
`evidence/upgrade-run/real-sdk/matrix.json`. Installed CrewAI formatting and its
reviewed repair pass eight controls in `evidence/crewai-sdk`. Chrome checks pass
**41/41** with desktop/mobile screenshots in `evidence/upgrade-run/browser`.
Wheel isolation, packaged constraints and CLI verification are recorded in
`evidence/tests/wheel-verification-040.json`. No new model/provider call occurred.
The new Windows/Ubuntu installed-SDK CI job is configured, not remotely verified.

```bash
python -m pytest -ra
python scripts/verify_sdk_upgrade.py --environment-dir outputs/sdk-envs --prepare --output outputs/sdk-matrix
node tests/browser_upgrade_check.cjs
python -m build --wheel --no-isolation
python scripts/verify_wheel.py
```

Browser QA uses saved evidence by default and an installed Chrome/Edge with
Node 22+. Full limitations and current gates: [development review](DEVELOPMENT_REVIEW_ZH.md).

## Historical 0.3.2 and 0.3.1 verification

**Latest local build (0.3.2): 186 passed, 4 skipped**, recorded in `evidence/tests/pytest-final-032.txt`. Thirteen new boundary tests cover real child processes, unhealthy baselines, custom input, missing/changed SDKs, credential isolation, deadlines, output limits and preserved evidence. Eight actual source/installed-SDK matrix cases and ten Chrome viewer checks are in `evidence/boundary-run`. The rebuilt wheel executes its packaged boundary workers (`evidence/tests/wheel-verification-final-032.json`). Separate real GLM reuse evidence remains in `evidence/glm-reuse`. There is no 0.3.2 remote CI claim; the records below concern 0.3.1.

Current local release suite: **161 passed, 4 skipped** on Python 3.13.14 / pytest 8.4.2, recorded in evidence/tests/pytest-glm-release.txt. Skips are existing Windows symlink/directory-link permission checks. The two original ACV loopback integration tests pass when loopback access is permitted. Synthetic tests are not provider evidence.

New coverage checks exact GLM routing/no FlashX fallback, credential redaction, mapping mutations, malformed plans, preserved failed proposals, live task identity/answer validation, unexpected provider metadata, duplicate calls, report integrity, evaluation label withholding, pre-request protocol freezing, failed-arm preservation, citation validation and mandatory knowledge revalidation.

Actual HTTP experiments are separately in evidence/glm-live and evidence/glm-evaluation. Browser checks: 13 live workbench checks in evidence/live-browser plus 14 earlier offline viewer checks in evidence/browser. Video: complete decode and six-frame visual inspection in evidence/live-video. Package: scripts/verify_wheel.py and evidence/tests/wheel-verification-glm.json. Configured-value and token-marker scan: scripts/release_check.py and evidence/tests/secret-scan-glm.json.

Run `python -m pytest -ra` after installing requirements and pytest 8.4.2. New 0.3.1 commit `37aba3524acd109fd588e495e48a49fe1afecc38` passed **165/165 tests on Ubuntu Python 3.10 and 3.13**, including the four Windows skips. Both jobs also passed the demo, exported regression and offline benchmark steps. [Actual run](https://github.com/karurukaruru/agent-code-validator/actions/runs/40163644009); job evidence is in `evidence/tests/github-actions-glm.json`. The historical section below concerns the prior build.

## Historical 0.3.0 verification


On October 25, 2026, the final complete suite ran with Python 3.13.14 and pytest 8.4.2: **143 passed, 4 skipped**. Raw output: `evidence/tests/pytest-final.txt`. Earlier 107-test and 136-test runs remain in `pytest-full.txt` and `pytest-release.txt`. Initial sandbox execution failed two original ACV loopback HTTP integration tests; rerunning with loopback access passed. These are explicit fake-provider tests, not real API evidence.

Commands:

```bash
python -m pip install -r requirements.txt
python -m pytest
python -m unittest tests.test_patchcourt_core tests.test_patchcourt_adversarial tests.test_patchcourt_lab
python -m patchcourt demo --output outputs/patchcourt
python -m unittest discover -s outputs/patchcourt -p test_regression.py
python -m patchcourt benchmark --output outputs/benchmark
```

Coverage includes existing ACV behavior, controlled semantic mutations, independently authored holdouts, stream assembly/truncation, invalid baselines, secret redaction, knowledge integrity/version changes, repair mutation checks, CLI exit codes, report export and mocked HTTP/schema/Tavily behavior. See independent review for actual bugs found and fixed.

The actual installed NVIDIA SDK reproduction is independently runnable as described in `evidence/full-sdk/README.md`. CrewAI is source-boundary-only. No real provider inference or latency/cost study is claimed. Static JS syntax, DOM-safe rendering and 14 real Chrome checks passed at desktop and 390px widths; see `evidence/browser/qa-results.json` and `docs/JUDGE_REVIEW.md`.

The wheel built successfully and its CLI, both fixture sources and dashboard executed from an isolated extraction outside the source import path (`scripts/verify_wheel.py`, result in `evidence/tests/wheel-verification.json`). A separate local wheel installation succeeded. Static test-build packaging uses an explicit file allowlist (`scripts/package_demo.py`). Secret scanning found no configured credentials or recognized token/private-key markers; this is a scoped check, not a privacy guarantee.

Four skipped tests are existing symlink/directory-link checks: this Windows environment did not permit creating those links. See the `-rs` output for exact test names. Remote Ubuntu CI subsequently passed **all 147 tests** on both Python 3.10 and Python 3.13, including those link tests. Demo, exported regression and benchmark steps also passed. [Verified CI run](https://github.com/karurukaruru/agent-code-validator/actions/runs/40155739894), implementation commit `462fde1dbce1eb46b5f00df5e68cf7aa6bf2d368`; machine-readable status in `evidence/tests/github-actions.json`.
