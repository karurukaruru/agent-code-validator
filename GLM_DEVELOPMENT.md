# Live development evidence — 0.3.1, October 25, 2026

PatchCourt is now a tested live developer prototype. It demonstrates a real model proposal, independent verification, a deliberately corrupted repair being rejected, and a real GLM tool conversation recovering the expected fixture result. This is narrower than completion of the original mission and does not establish Nebius/NVIDIA competition eligibility.

## Executed evidence

- Exact model: `glm-5.3-flash` through BigModel's official API. No FlashX, no fallback, and no NVIDIA inference. Local credentials are read only by the Python process.
- Six exploratory workflow runs: four failed during development, then two passed. Prompts/harness changed between attempts, so this is not a model success-rate benchmark. Every attempt is retained in `evidence/glm-live`.
- Successful recorded run: three requests, 2,480 reported tokens, eight independent controls, corrupted-ID mutation rejected, both actual fixture tools executed, final inventory value 21.
- Separate generated-test experiment: five model cases; two expected labels disagreed with the independent comparator and the result was `NEEDS_REVIEW`. That disagreement is preserved.
- Five-arm evaluation: 70 rows executed, 14 cases per arm, three GLM requests and one official-document Tavily search. C matched 14/14 labels; D with documentation matched 13/14. One trial cannot establish a causal search effect or general model accuracy.
- Total GLM usage through this release's experiments: **31,734 reported tokens** (17,019 access/reasoning/workflows/recording + 14,715 evaluation). Dollar cost remains unknown. Two Tavily basic searches consumed two reported credits in total.
- 95-second actual browser demonstration: local English synthesized narration, burned-in English captions, separate English/Chinese SRT; entire API execution retained. Only eight seconds of idle opening footage were removed. Six frames were inspected, subtitle overlap corrected, and the complete video decoded successfully.
- Live workbench: 13 real Chrome checks passed; desktop/mobile overflow, actual task result, verifier results, request capability/origin checks, no exposed environment endpoint, and no browser errors.

## Run locally

Install `release/agent_code_validator-0.3.1-py3-none-any.whl` with Python 3.10+ and pip. Set `GLM_API_KEY` in the current process; do not put it in source files or command arguments. Then:

```bash
patchcourt live-demo --port 8780
patchcourt live --output outputs/a-new-run
patchcourt verify outputs/a-new-run
patchcourt benchmark --provider glm --output outputs/a-new-evaluation
```

Open `http://127.0.0.1:8780` for the workbench. The server permits three deliberate fixed-workflow runs per launch. The benchmark also requires `TAVILY_API_KEY`. It makes at most three inference requests (8,192 output-token cap each) and one search. Default `benchmark` stays offline and never silently spends credits.

## Scope and remaining work

The repair is a model-selected declarative field mapping over an audited historical adapter function with inert SDK message types. Independent execution validates eight controls. It is not arbitrary Python patch generation or a production inventory service. Broken adapter output is rejected locally before an invalid provider request is submitted. The separate installed NVIDIA SDK reproduction remains valid but does not perform NVIDIA inference.

Automatic baseline/candidate package environments, broad framework instrumentation, arbitrary-source repair isolation, a complete installed CrewAI reproduction, broader reliability research and task-specific Tavily improvements remain engineering work. The GLM comparison does not fulfill the requested Nemotron comparison. See `REQUIREMENTS_GAP_AUDIT.md` for the complete accounting.

Competition-specific runtime use and Nebius feedback remain unproven under the user's instruction to stop NVIDIA calls. The public YouTube upload, entrant information, authenticated Devpost fields and final submission are still outstanding. Another API key alone would not complete all these engineering and submission requirements.

The evaluation recorded an existing environment-label bug (`patchcourt: 0.3.0` despite running 0.3.1 sources). The reporter now reads the actual package version. Raw historical evaluation records are deliberately unchanged; this metadata defect does not change their recorded model inputs, responses or classifications.
