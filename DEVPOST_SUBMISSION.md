# PatchCourt — Devpost submission copy

**Editorial status: reviewable English draft, not submitted.** The product description below is supported by local evidence. Required-platform execution, final public delivery links and the authenticated form remain gates in [SUBMISSION_CHECKLIST.md](SUBMISSION_CHECKLIST.md). Keep this notice until those gates pass.

**Project name:** PatchCourt — AI Agent Compatibility Guardian

**Tagline:** Catch silent AI agent regressions before they reach production.

**Track:** Coding and Agentic Engineering

## Inspiration

The tools ran. The agent still broke.

An SDK upgrade can preserve valid Python while silently removing the tool-call IDs, arguments or images that the next model request needs. A green installation check cannot explain why an agent suddenly stops finishing its job. We built PatchCourt to make that hidden contract visible and to make a proposed repair earn trust through execution.

## What it does

PatchCourt compares the meaning of messages at an agent/SDK boundary. It reports preserved behavior, lost behavior and cases that need review, with exact differences developers can inspect. It reproduces two credited historical defects: NVIDIA LangChain tool-call loss and CrewAI/Gemini image loss.

Its repair workflow asks a model for a bounded field mapping, checks that mapping independently, deliberately corrupts it to verify rejection, and runs an actual model conversation with two local fixture tools. The recorded development run restores the tool calls and completes an inventory task with value **21**. The result is a complete evidence trail: source hashes, request records, controls, failed attempts and regression exports.

Controlled upgrade runs also compare two real installed NVIDIA SDK releases with shared dependency pins. When both releases have the same defect, PatchCourt returns **NEEDS_REVIEW** rather than treating equality as compatibility.

## How we built it

The core is Python, a conservative semantic comparator and a local browser workbench. Version-scoped ASM observations retain source and environment context and require fresh verification before reuse. Model-generated Python is never executed. A declarative repair can change only the fields allowed by the reviewed mapping contract.

GLM 5.3 Flash supplied the earlier recorded development workflow. The current development iteration also completed a real **DeepSeek Flash** repair and tool conversation, with **Tavily** official-document retrieval: three model requests, one search, eight independent checks, rejection of a corrupted repair and the checked result 21. A separate retrieval-backed reasoning run produced declarative cases that were actually evaluated. These are preliminary development runs before the final 0.5.0 freeze, retained under `evidence/development-050`.

The intended competition workflow uses an NVIDIA Nemotron model served by **Nebius Token Factory** for repair reasoning and the real tool conversation. At this draft checkpoint, model discovery has succeeded but that required inference is still awaiting authorized Nebius access. Neither a GLM nor a DeepSeek call satisfies this requirement.

Tavily retrieves allowlisted official documentation. Its contribution is evaluated with and without retrieval on the same frozen cases. The earlier GLM experiment found no improvement; we publish that outcome instead of claiming that adding search automatically makes the tool better.

## Challenges and accomplishments

The difficult part was deciding what could count as evidence. A model's plausible answer is not a repair. Matching two broken releases is not a pass. Preserving image bytes is not proof of a successful vision task. A local API discovery response is not required-platform inference.

We executed installed-SDK reproductions, real two-version comparisons, eight independent repair checks, a corruption control and a real development-model fixture-tool conversation. The exported viewer keeps provenance and limits next to the result, so reviewers can distinguish the reproducible defect from the scope of the demonstration.

## What we learned and what comes next

Compatibility is a semantic contract, not a package version or an HTTP success code. Useful model assistance needs an independent verifier and retained failures. The next scope is broader reviewed SDK coverage and integration with real application boundaries. Arbitrary repository instrumentation, automatic production patching and a general vision-task guarantee are outside this build.

## Built With

Python; Agent Code Validator; ASM evidence conventions; LangChain NVIDIA AI Endpoints; CrewAI; Google GenAI types; local HTML/CSS/JavaScript workbench; DeepSeek Flash and GLM 5.3 Flash development evidence; Tavily official-document retrieval. Add **Nebius Token Factory** and the exact NVIDIA Nemotron model only with their final executed evidence and roles.

## Delivery fields and disclosures

- **Current published source candidate:** https://github.com/karurukaruru/agent-code-validator/tree/patchcourt/award-build-20261024 . The final local revision still needs publication and anonymous verification.
- **Working demo or test-build URL:** not yet verified for the final release. Local loopback URLs are not public submission URLs.
- **YouTube:** no public final competition-video URL is recorded. The genuine 95-second GLM development cut remains an intermediate artifact.
- **Testing instructions:** [JUDGE_TESTING.md](JUDGE_TESTING.md).
- **Platform feedback:** [MOST_VALUABLE_FEEDBACK.md](MOST_VALUABLE_FEEDBACK.md); final copy must describe actual required-platform use.
- **Pre-existing work:** Agent Code Validator v0.2.0 predates the event. Significant competition-period additions and retained upstream components are disclosed in [COMPETITION_CHANGELOG.md](COMPETITION_CHANGELOG.md). Known upstream defects are credited; they are not claimed as new discoveries.
- **Scope:** bounded declarative repairs, reviewed SDK serializers and local fixture tools. No arbitrary model-code execution or production repair guarantee.

The authenticated Devpost form is not visible through the public session. Its exact fields and limits must be reviewed by the entrant; this document does not assert that registration, personal eligibility or submission has completed.
