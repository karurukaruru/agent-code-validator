# Testing and verification

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

Four skipped tests are existing symlink/directory-link checks: this Windows environment did not permit creating those links. See the `-rs` output for exact test names. Linux/Python 3.10 CI is configured but not executed locally.
