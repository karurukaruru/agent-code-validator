# PatchCourt — AI Agent Compatibility Guardian

**Catch silent AI agent regressions before they reach production.**

An agent can execute its tools, then fail on the next request because an SDK adapter silently removed their identifiers. PatchCourt compares message semantics, reproduces failures, verifies scoped repairs, and exports evidence that developers can inspect.

**Live development build; not submission-ready.** Version 0.3.1 has real GLM 5.3 Flash inference, a model-proposed bounded repair, eight independent checks and a real fixture-tool conversation recovering value 21. Failed attempts are preserved. A five-arm exploratory evaluation and 95-second narrated live demonstration have executed. NVIDIA/Nemotron inference was never run; further NVIDIA calls were stopped at the user's request. See [current evidence and limits](GLM_DEVELOPMENT.md) and the [original-prompt gap audit](REQUIREMENTS_GAP_AUDIT.md).

[Download the build and live video](release/README.md) · [Inspect the live workbench](evidence/live-browser/desktop.png)

## Live GLM development workflow

Set `GLM_API_KEY` locally, then run:

```bash
python -m patchcourt live --output outputs/a-new-run
python -m patchcourt live-demo --port 8780
```

The model ID is locked to **`glm-5.3-flash`**, not FlashX, with no fallback. The live workflow executes declarative field mappings and fixed local inventory/price tools; it does not execute arbitrary model Python or establish Nebius/NVIDIA competition eligibility. Thirteen actual Chrome checks passed, including desktop/mobile layouts and request authorization. The 95-second video has English narration, burned-in English captions and a Chinese subtitle file. All attempts are in `evidence/glm-live`.

With `TAVILY_API_KEY` also configured, `python -m patchcourt benchmark --provider glm --output outputs/a-new-evaluation` runs the bounded five-arm development comparison (three model calls, one search). It freezes the corpus before inference, withholds labels, preserves errors and measures paired outcomes. This exploratory run found **no Tavily improvement**. See [evaluation scope and results](BENCHMARK.md).

## Run the demonstration

Python 3.10+; these commands require no extra packages or API keys:

```bash
python -m patchcourt demo --output outputs/patchcourt
python -m patchcourt serve outputs/patchcourt --port 8765
```

Open <http://127.0.0.1:8765>. The first case shows missing calls, a reviewed repair, and deterministic inventory-task recovery to **21**. The second shows CrewAI/Gemini image loss. The viewer displays provenance and limits beside results. Alternatively open exported `index.html` and select `report.json` with **Open evidence**.

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

Nemotron is wired for source inspection, protocol hypotheses, declarative tests, explanations and repair proposals. Its cases are evaluated by deterministic contracts; model-generated Python and repairs never execute. Tavily retrieves allowlisted official documentation for a paired comparison. **Neither model contribution nor Tavily benefit is live verified. No platform defect is claimed.**

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
