# Devpost submission draft — blocked from final submission

Track: **Coding and Agentic Engineering**. Project: **PatchCourt — AI Agent Compatibility Guardian**. Tagline: **Catch silent AI agent regressions before they reach production.**

## Inspiration

Agent failures can hide inside message conversions. Tools may execute correctly while the next provider request loses their identifiers or an image observation. Compilation and ordinary unit tests can miss the resulting task failure.

## What it does

PatchCourt compares supported message semantics, records explicit conversion boundaries, reproduces known SDK defects, verifies reviewed repairs and exports evidence. Developers see the lost information, its deterministic task impact, and the scope of verification. Version-specific ASM observations help later checks reuse prior evidence without skipping current tests.

## How we built it

We extended Agent Code Validator's bounded read-only inspection with a Python compatibility pipeline, deterministic contracts, source snapshots, real NVIDIA SDK reproduction, structured reports and a static interface. Agent Software Map contributes evidence/revalidation conventions. Nebius Token Factory and NVIDIA Nemotron are integrated for declarative hypothesis/test generation; Tavily supplies official-document context to a paired experiment. **These provider integrations are implemented but have not been used live; current eligibility is unproven.**

## Accomplishments and learning

We executed historical tool-call loss in real NVIDIA SDK 1.4.3 and verified a repaired copy with five controls. A separate source-boundary harness reproduces CrewAI image loss. Independent review exposed misleading success paths involving unknown stream fields, contradictory representations and incomplete patch verification; those were fixed. The main lesson is to preserve evidence scope and abstain when semantics are unknown.

## What remains

Actual NVIDIA inference through Nebius, repeated platform findings, a demonstrated Tavily benefit, model-generated test execution, broader sandboxed repair, live task replay, public YouTube video and authenticated form completion. A downloadable offline test build is already public.

## Fields and release checklist

| Field/gate | Current state |
|---|---|
| Track/title/English description | Draft above |
| Built With | Python; ACV; ASM; NVIDIA SDK; provider integrations must be described honestly as not yet live |
| Public source URL | [Published development branch](https://github.com/karurukaruru/agent-code-validator/tree/patchcourt/award-build-20261024) |
| Working demo/test-build URL | [Download offline test build](https://raw.githubusercontent.com/karurukaruru/agent-code-validator/462fde1dbce1eb46b5f00df5e68cf7aa6bf2d368/release/patchcourt-demo-0.3.0.zip); anonymous download/hash verified |
| Public YouTube, under 3 minutes | 112-second offline MP4 and English subtitles created; YouTube upload and live-enabled replacement remain pending |
| NVIDIA model and Nebius usage | BLOCKED, no credentials |
| Feedback section | BLOCKED, no actual experiments; use MOST_VALUABLE_FEEDBACK.md only after evidence exists |
| Significant changes | COMPETITION_CHANGELOG.md |
| License/setup/testing | Included |
| Entrant eligibility/registration | User verification required |
| Exact authenticated fields/limits | Not visible in logged-out form |
| Final submit | Requires user approval; not performed |

Deadline: October 31, 2026, 01:00 Asia/Shanghai. Keep judge access through the published judging period. [Rules and source audit](COMPETITION_AUDIT.md). Feedback and Tavily are both Bonus categories; do not assume both can stack. No award is guaranteed or claimed.
