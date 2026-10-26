# Platform feedback — evidence-led working draft

**Status: required-platform feedback is not complete.** The entrant has chosen to continue the Nebius × NVIDIA event and will provide Nebius access. The supplied development/search credentials do not establish Nebius model execution. No platform defect or regional exclusion is claimed.

## What we have actually observed

The retained [Nebius discovery record](evidence/access-20261025/discovery.json) records an HTTP 200 model-list request and lists NVIDIA Nemotron models. Discovery establishes only that this request completed; it does not establish that inference, tool calling, streaming or structured output worked.

Earlier live development used GLM 5.3 Flash. It showed why the verifier matters: generated expectations and proposed mappings can be wrong, so PatchCourt preserves rejected attempts and verifies every accepted repair. Those observations describe our harness and that development model, not NVIDIA Nemotron or Nebius reliability.

The current [DeepSeek development workflow](evidence/development-050/deepseek-live-01/report.json) passed the actual mapping repair and fixture-tool task: three `deepseek-flash` model requests, one Tavily search and 4,094 reported model tokens. The [repeat attempt](evidence/development-050/deepseek-reuse-01/report.json) also passed, with three model requests and 2,816 tokens. Its scoped knowledge lookup was a **MISS** because the verifier/code identity changed during development. Those runs cannot establish reuse savings. A [separate reasoning run](evidence/development-050/deepseek-reason-01/reasoning.json) used one more model request and one search and evaluated generated declarative cases. Final target experiments will rerun after the code freeze.

Tavily has returned official documentation in real saved requests. In the earlier paired GLM trial, classification accuracy was 14/14 without retrieved documents and 13/14 with them. This is a small descriptive trial with no demonstrated search benefit. A successful DeepSeek/Tavily workflow also does not by itself establish accuracy improvement. The new evaluation freezes 12 developer-authored protocol samples before model calls and retains failed/abstained comparisons; it is not an independent held-out benchmark and no unexecuted score is claimed.

## What the required-platform run will measure

The competition workflow must show the exact NVIDIA model proposing a bounded mapping through Nebius Token Factory, independent repair verification, rejection of a corrupted mapping and a real model/tool conversation. Sanitized request bodies, HTTP results, request IDs when returned, usage, latency and all failed attempts are retained. Hashes protect local integrity; they do not independently authenticate the provider.

The reliability lab separately repeats structured JSON, forced tool calling, streaming and an intentionally invalid-model request. An expected invalid-model error is useful contract evidence, not a defect. A timeout, malformed request, unsupported feature, model behavior or harness bug must be investigated before attributing it to Nebius.

## Proposed feedback structure after execution

For **Nebius Token Factory**, describe the actual path from obtaining legitimate access to the first successful inference, what setup was required, which compatibility features worked in repeated trials and any precisely reproducible obstacles. Recommend changes only when a documented expectation and observed result support them.

For the **exact NVIDIA model**, report its actual repair proposal, rejected attempts if any, verifier results and completed fixture-tool task. Discuss whether the bounded reasoning contribution justified its observed request count and latency. Do not extrapolate a few synthetic cases to universal reliability or production performance.

For **Nebius AI Cloud**, state that it was not used if the project uses Token Factory only. For **Tavily**, name the retrieved official sources, distinguish successful runtime search from accuracy improvement, and report the paired outcome even if it is flat or negative.

Our product recommendation to investigate is an exportable, request-ID-linked example of the complete tool-call lifecycle. It would be valuable for adapter debugging. This is a feature request, not a claim that current documentation is missing or defective. A useful acceptance test would preserve call IDs, multiple calls, nested JSON arguments, tool results and stream completion through a documented end-to-end example.

## Concise feedback-field copy at this checkpoint

> PatchCourt is prepared to evaluate NVIDIA Nemotron on Nebius Token Factory through a bounded repair workflow and repeated protocol probes. We have a successful recorded model-discovery response, but required-platform inference remains unexecuted pending legitimate access. We therefore do not yet claim a Nemotron result or a Nebius defect. Our development-model experiments show that independent verification and retained failed attempts are essential. Final feedback will name the exact model, observed trials, onboarding experience, measured limitations and whether we would build with the platform again, with reasons.

This paragraph is a truthful status disclosure, not a finished feedback-award entry. Replace it with measured findings before submission. The official authenticated feedback section and its character limit remain uninspected. [Official feedback guidance](https://nebiusglobalaihackathon.devpost.com/updates/46205-how-to-build-a-winning-project) asks for actual use, strengths, weaknesses, onboarding and a reasoned reuse decision.
