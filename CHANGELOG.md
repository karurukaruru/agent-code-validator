# Changelog

All notable changes to Agent Code Validator are documented here.

## [0.4.0] - 2026-10-25

- Added `upgrade-run`: read-only discovery, explicit wheel-only preparation of two real SDK releases, shared dependency pins, complete environment revalidation, independent workers and original-input contract gates.
- Added a reproducible four-scenario installed-SDK matrix and Windows/Ubuntu CI job. Both unmodified releases losing tool calls remains NEEDS_REVIEW; reviewed patch recovery is separately verified.
- Hardened stream container/index/finish validation and tool-call identity checks, preserving legitimate fragmented calls and usage-only tails.
- Added an upgrade evidence overview, actual environment/worker provenance, mobile browser checks, a Windows offline launcher and current package-resource verification.
- Added an installed CrewAI formatter reproduction with real BaseLLM and Google SDK types; scope and recorded outcomes are in the current development review.
- No new model inference, paid API experiment, remote publication or competition submission is claimed.

## [0.3.2] - 2026-10-25

- Added optional `check --input` contract checks to detect equal-but-broken traces; `verify` now rejects missing/blank run IDs and non-object records. Five regression tests added; final local suite: 186 passed, four permission skips.
- Added `boundary-run`: separate clean processes for reviewed serializer variants, source and installed-SDK backends, captured boundaries, original-input checks, explicit unhealthy-baseline verdicts and dashboard evidence. Eight real local scenarios and ten browser checks passed; no provider calls.
- Clarified generated-test contract labels and normal-behavior controls; reasoning now rejects a wrong GLM response model or ambiguous completion choices.
- Scoped offline readiness messages to the current execution instead of asserting absent credentials, video or public releases.
- Added opt-in verified plan reuse, scoped by adapter source, environment and verification code; all checks and task execution rerun. Corrupt/invalid cached plans stop before API calls and unsuccessful tasks never enter knowledge.
- Recorded one actual GLM pair: three first-run requests and two repeat-run requests, 2,898 total tokens, both tasks pass. This is exact-repeat evidence, not a general savings estimate. No remote CI is claimed for this version.
- Prepared a portable development handoff with Chinese completion criteria, history, evidence and video source assets.

## [0.3.1] - 2026-10-25

- Added exact GLM 5.3 Flash routing, bounded model-proposed adapter mappings, independent controls and live fixture-tool recovery.
- Added a loopback workbench with capability/origin checks and a real narrated 95-second demonstration.
- Added an explicitly opted-in five-arm GLM development evaluation, original ACV review adapter, paired Tavily retrieval and scoped knowledge revalidation. Failed runs and negative retrieval results remain published.
- Fixed provider ordinal projection, structured final-answer handling, stale workbench state, oversized video captions and stale package-version reporting.
- Preserved offline behavior and documented remaining original-mission/competition gaps.

## [0.2.0] - 2026-08-23

### Added

- A read-only `acv agent` review mode that investigates a project incrementally.
- Bounded `list_files`, `read_file`, and `search_code` tools with strict project-root isolation.
- Native model Tool Calling with a validated JSON-action fallback.
- Evidence-aware agent reports with severity, category, confidence, location, evidence, impact, and suggested fixes.
- Detailed findings in the terminal as well as in the saved Markdown report.
- Chinese and English report prose through `report_language` or the `--language` option.
- Provider presets and example configurations for Volcengine Ark Coding Plan and Agent Plan.
- Local fake-provider and HTTP integration tests that require no real API key.

### Changed

- Kept `acv review` as the v0.1-compatible snapshot-review mode.
- Removed explicit response-token limit parameters from LLM requests. Agent steps and tool output remain bounded.
- Expanded ignored dependency, cache, build, and environment directories.
- Renamed the Windows launcher from the Chinese filename to `Start-ACV.cmd`.
- Updated the package version to `0.2.0`.

### Security

- Rejects absolute paths, `..` traversal, symbolic links, ignored paths, and Windows Junction/Reparse Point escapes.
- Validates model actions and final file citations against evidence actually observed by the agent.
- Keeps API keys and generated reports out of version control.

## [0.1.0] - 2026-08-22

- Initial release with local project scanning, a single-request snapshot review, terminal output, and Markdown report generation.
