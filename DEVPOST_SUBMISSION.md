# Devpost submission draft — not submitted

Track: **Coding and Agentic Engineering**. Project: **PatchCourt — AI Agent Compatibility Guardian**. Tagline: **Catch silent AI agent regressions before they reach production.**

## Inspiration

The tools ran. The agent still broke. An SDK adapter can silently remove tool-call identifiers or image observations, leaving an application that compiles and passes simple tests unable to finish its task.

## What it does

PatchCourt compares supported message semantics, reproduces known SDK defects, independently checks bounded repairs and exports inspectable evidence. In the live development workflow, GLM inspects a faulty historical adapter, proposes a declarative field mapping, faces eight independent checks and an intentionally corrupted repair control, then completes a real conversation using two local fixture tools. The original conversion loses calls; the verified mapping preserves them and the task returns 21.

## How we built it

We extended Agent Code Validator's read-only inspection and original review parser with semantic comparison, source snapshots, real NVIDIA SDK reproduction, scoped ASM evidence, a loopback workbench and bounded provider clients. Actual development inference uses glm-5.3-flash. Tavily retrieves allowlisted official documentation for a paired classification experiment. A 95-second narrated video records real execution.

**Required competition runtime use is not yet demonstrated:** there has been Nebius model discovery, but no NVIDIA/Nemotron inference. GLM experiments do not substitute for that requirement. The user stopped further NVIDIA calls.

## Accomplishments and learning

The installed NVIDIA SDK reproduction loses both calls before repair and passes independent checks after repair. A separate source-function harness reproduces CrewAI image loss. The live model path preserves rejected attempts and incorrect generated expectations. A complete 70-row development comparison is published. In one paired trial GLM matched 14/14 expected labels without retrieved documents and 13/14 with them; we do not claim a search benefit. The lesson is that neither plausible model output nor an added search API is evidence of improvement without execution.

## Current limits and remaining work

The live repair is a bounded mapping, not arbitrary Python patch execution. Tools are local fixtures. Generic repository upgrade environments, broad framework instrumentation, safe source-patch execution and complete installed CrewAI coverage remain engineering gaps. Genuine Nebius experiments/feedback, required-platform runtime use, a public YouTube link, entrant eligibility and authenticated form completion remain outstanding.

## Submission fields

- Repository: https://github.com/karurukaruru/agent-code-validator/tree/patchcourt/award-build-20261024
- Built with: Python, Agent Code Validator, ASM evidence conventions, LangChain NVIDIA SDK (local reproduction), GLM 5.3 Flash (live development), Tavily (live official-document retrieval).
- Demonstration: local release/patchcourt-glm-live-demo.mp4; public YouTube URL pending.
- Competition-period changes: COMPETITION_CHANGELOG.md and commit history; pre-existing ACV work is disclosed.
- Feedback award: no invented Nebius findings; current draft is not yet award-ready platform feedback.
- Final submission: requires entrant/account details and final approval. Nothing has been submitted.
