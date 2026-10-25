# Nebius feedback — current evidence status

**Not ready for the feedback award field.** The user has no Nebius or Tavily credentials. No authenticated experiments, model calls or onboarding attempts occurred. This is a local access prerequisite, not a platform defect or evidence of regional exclusion.

The lab implements discovery and repeated schema, tool-call, stream and invalid-model probes. It preserves exact endpoint/model/parameters, timestamps, sanitized responses/errors, request IDs, counts, usage and latency. Current trials are BLOCKED, not positive or negative API observations. Use `python -m patchcourt lab --trials 3 --output outputs/lab-new-run` after legitimate access is available. Each run needs a new directory.

Then run `python -m patchcourt feedback outputs/lab-new-run --output outputs/feedback`. This exports the detailed review draft, a concise field draft and raw-count summary. The renderer excludes mocked/blocked trials, preserves expected-error controls, reports descriptive small-sample uncertainty and refuses to turn a mere failed probe into a confirmed platform bug. The current blocked output is retained under `evidence/feedback-draft`.

For each actual finding, collect: specific title; full environment; minimal script; documented expected behavior; observed response and repeated counts; alternative explanations; developer impact; feasible recommendation; acceptance test. Then convert it into a scoped regression fixture and ASM observation. Model variability, unsupported features, malformed requests and harness defects must be distinguished from platform bugs. Positive findings need the same evidence as negative ones.

Four probe types are implemented. Context boundaries, idempotency, sustained throughput, multiple-model comparisons and complex live workflows remain unmeasured.

## Concise official-field draft — truthful current status

“PatchCourt implements a repeatable protocol reliability lab for Nebius Token Factory, but authorized API access is not yet available. We have not run authenticated trials and cannot claim NVIDIA Nemotron runtime use or evidence-backed platform findings. Prepared probes cover tool-call identity, structured JSON, streaming and structured errors. Actual feedback will include sanitized reproductions and repeated outcomes.”

This is a status disclosure, not award-quality feedback. Do not submit as though the required live-use gate passed. Exact authenticated Devpost fields/limits remain uninspected; a Markdown file alone does not complete the official section.
