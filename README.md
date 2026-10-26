# PatchCourt — AI Agent Compatibility Guardian

**Catch silent AI agent regressions before they reach production.**

**0.5.1 adds a practical CI loop:** capture an adapter you choose, check its
actual message pair, and export a standalone regression gate for future SDK
candidates. The gate freezes the original input, includes the checker source
and license, and runs with Python's standard library. A broken captured output
correctly produces a red test; a fresh repaired candidate can turn it green.
[Capture-to-CI walkthrough](CAPTURED_BOUNDARIES.md).

```bash
python examples/captured-boundary/capture.py --output outputs/courier-broken.json
python -m patchcourt check-recording outputs/courier-broken.json --output outputs/courier-gate
python -I -S -m unittest discover -s outputs/courier-gate -p test_boundary_contract.py
```

The last two commands intentionally return failure for the broken example.
[Capture a fixed candidate and reuse the same gate](CAPTURED_BOUNDARIES.md).
No API key or SDK install is needed for this example. It is a controlled
application adapter, separate from the real installed-SDK execution evidence.


An agent can execute its tools, then fail on the next request because an SDK adapter silently removed their identifiers. PatchCourt detects the lost semantics, challenges a model-proposed repair, and verifies task recovery with independent controls.

**Development status — competition submission is still pending.** The new workflow supports exact DeepSeek Flash and NVIDIA Nemotron on Nebius, strict response/model validation, documentation retrieval, scoped repair reuse, and a persistent request budget. Real [DeepSeek development runs](evidence/development-050/README.md) passed eight checks, rejected a corrupted repair and recovered inventory value **21**. These runs do not establish Nebius/NVIDIA runtime use. The entrant has confirmed continuing this competition and will supply Nebius access; the earlier handoff's stop instruction is historical.

[Verified 0.5.0 CI](https://github.com/karurukaruru/agent-code-validator/actions/runs/40260807511): 337 tests on Python 3.10/3.13; installed-SDK controls on Ubuntu/Windows. [Free current development judge package](release/patchcourt-judge-demo-0.5.1-development.zip) and [137-second English recorded replay](release/patchcourt-development-replay-0.5.0.mp4) have passed anonymous download checks.

[Judge instructions](JUDGE_TESTING.md) · [Submission checklist](SUBMISSION_CHECKLIST.md) · [SDK upgrade evidence](UPGRADE_RUN.md) · [Current development review](RELEASE_REVIEW_051_ZH.md)

## Run a model-proposed repair

Keep credentials in an ignored local env file, using `DEEPSEEK_API_KEY`, `TAVILY_API_KEY`, and, when available, `NEBIUS_API_KEY` / `NEBIUS_MODEL`. The parser loads only named variables; it never evaluates shell code. Do not publish this file.

```bash
python -m patchcourt --env-file .env.local live --provider deepseek --tavily --knowledge-dir outputs/repair-knowledge --output outputs/new-live-run
python -m patchcourt --env-file .env.local live-demo --provider deepseek --tavily --knowledge-dir outputs/repair-knowledge --port 8780
```

DeepSeek is locked to the explicitly authorized `deepseek-flash`, with no provider fallback. For the competition, use `--provider nebius --model nvidia/<accessible-nemotron-model-id>` after checking the account's actual catalog. API errors and rejected proposals remain evidence. The verifier executes declarative field mappings and fixed local inventory/price tools; it does not execute arbitrary model Python.

For release experiments, the wrapper reserves a shared budget **before** each HTTP attempt, including failures, and refuses to overwrite prior results:

```bash
python scripts/run_release_experiments.py live --provider deepseek --env-file .env.local --budget outputs/release-budget.json --tavily --knowledge-dir outputs/repair-knowledge --output outputs/release-live
```

Its default shared ledger permits 30 model attempts and 10 basic searches. Plain CLI commands do not use that ledger automatically. The [new evaluation](patchcourt/release_evaluation.py) freezes 12 developer-authored cases before inference and preserves all five paired arms; it is a small exploratory experiment, not an independent blind benchmark. Historical GLM runs and video remain in [GLM_DEVELOPMENT.md](GLM_DEVELOPMENT.md).

## Run the demonstration

Python 3.10+; these commands require no extra packages or API keys:

```bash
python -m patchcourt demo --output outputs/patchcourt
python -m patchcourt serve outputs/patchcourt --port 8765
```

Open <http://127.0.0.1:8765>. The first case shows missing calls, a reviewed repair, and deterministic inventory-task recovery to **21**. The second shows CrewAI/Gemini image loss. The viewer displays provenance and limits beside results. Alternatively open exported `index.html` and select `report.json` with **Open evidence**.

On Windows, double-click **Start-PatchCourt.cmd** to create a fresh offline demo
and open the local viewer. No API key is required.

Red **FAIL** is the historical defect's compatibility verdict. The demo command succeeds when it reproduces expected failures and controls; repair verification has its own result. The bundled demo uses audited source functions with inert SDK types. The stronger, separately executed installed-SDK result is [here](evidence/full-sdk/README.md).

## Use in a project

```bash
python -m pip install -e .
patchcourt --help
patchcourt inspect ./my-agent --dependency langchain-nvidia-ai-endpoints --from-version 1.4.2 --to-version 1.4.3
patchcourt check baseline-messages.json candidate-messages.json --output outputs/upgrade
patchcourt verify outputs/upgrade
```

`inspect` reuses ACV's bounded read-only tools and returns candidate boundaries, never a defect based on version alone. `check` compares JSON message arrays: **exit 0 PASS**, **1 FAIL**, **2 INCONCLUSIVE/NEEDS_REVIEW/input error**. [Example traces](examples/upgrade) and `patchcourt.recorder.BoundaryRecorder` provide an explicit recording interface. Project code is not automatically imported.

Supported: OpenAI-style and normalized LangChain calls, IDs, nested arguments, tool-result linkage, roles, text, image references/detail, and single-choice streaming reconstruction. Unknown semantic fields abstain. The Gemini historical case has a dedicated harness; generic Gemini trace coverage is not claimed.

To execute a controlled real SDK upgrade instead of supplying traces:

```bash
patchcourt upgrade-run ./my-agent --from-version 1.4.3 --to-version 1.5.0 --environment-dir outputs/sdk-environments --prepare --output outputs/sdk-upgrade
```

`--prepare` opts into official wheel downloads; later runs reuse verified
environments without installation. Only the two reviewed releases are supported.
The default tool fixture is broken in both, so **NEEDS_REVIEW / exit 2 is the
expected observation**. See [the four-scenario check and limits](UPGRADE_RUN.md).

## Evidence and knowledge

- Two credited upstream defects: [LangChain NVIDIA #387](https://github.com/langchain-ai/langchain-nvidia/issues/387), [CrewAI #8434](https://github.com/crewAIInc/crewAI/issues/8434).
- Hash-pinned source, reviewed repair diffs, negative controls, counterexample minimization, JSON/Markdown reports and exported regression tests.
- Real installed NVIDIA SDK reproduction, with exact dependencies, clean child environment and independent assertions.
- ASM-derived version/source/environment-scoped observations. Reuse retrieves prior evidence and still reruns verification.
- Static evidence viewer and GitHub Actions integration; no public remote-code execution.

These are historical known defects, not new discoveries. Read [reproduction scope](REPRODUCTION_GUIDE.md), [benchmark limits](BENCHMARK.md) and [security](SECURITY.md).

## Nebius Reliability Lab

Configure `NEBIUS_API_KEY`, an accessible `NEBIUS_MODEL`, and `TAVILY_API_KEY` locally. No secrets belong in source or the viewer.

```bash
python -m patchcourt lab --trials 3 --output outputs/lab-run-1
python -m patchcourt feedback outputs/lab-run-1 --output outputs/feedback
python -m patchcourt reason patchcourt/semantic.py outputs/patchcourt/minimal-counterexample.json --tavily --output outputs/reasoning.json
```

The lab discovers models through `https://api.tokenfactory.nebius.com/v1`, schedules repeated schema/tool/stream/error probes, preserves every trial, and records usage/latency without inventing cost. Use a new output directory for each lab run. Missing credentials produce BLOCKED records.

The feedback command turns recorded HTTP trials into counts, uncertainty, concrete reproductions, developer impact, recommendations and acceptance tests. Mocked/blocked runs cannot produce platform findings. Expected invalid-model errors remain positive contract evidence, not false bug reports. Drafts require technical review and the actual Devpost field remains unverified.

Nemotron is wired for source inspection, protocol hypotheses, declarative tests, explanations and repair proposals. Its cases are evaluated by deterministic contracts; model-generated Python and repairs never execute. Tavily retrieves allowlisted official documentation for a paired comparison. **DeepSeek contribution is recorded in the development evidence. Actual Nebius/NVIDIA execution and any Tavily benefit remain unverified. No platform defect is claimed.**

## Test and package

```bash
python -m pip install -r requirements.txt
python -m pytest
python -m patchcourt benchmark --output outputs/benchmark
python -m unittest discover -s outputs/patchcourt -p test_regression.py
python -m pip wheel --no-deps . --wheel-dir dist
```

Without pytest: `python -m unittest tests.test_patchcourt_core tests.test_patchcourt_adversarial tests.test_patchcourt_lab`.

Original `acv agent` and `acv review` remain available; [original instructions](docs/ACV_README.md) are retained. See [architecture](ARCHITECTURE.md), [testing](TESTING.md), [competition changes](COMPETITION_CHANGELOG.md), [Devpost draft](DEVPOST_SUBMISSION.md) and [demo script](DEMO_SCRIPT.md). MIT license; upstream source and ASM attribution are retained. No award or final submission is claimed.
