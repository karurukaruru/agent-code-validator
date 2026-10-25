# Original-prompt gap audit — October 25, 2026

**0.4.0 update:** controlled discovery → real release environments → recorded
boundaries → input contracts now runs for reviewed NVIDIA releases 1.4.3/1.5.0.
The older fixed-implementation runner remains separate. See [UPGRADE_RUN.md](UPGRADE_RUN.md)
and [current executed evidence](DEVELOPMENT_REVIEW_ZH.md). This closes that bounded
engineering gap, not arbitrary dependency/framework support or competition readiness.

This audit supersedes the earlier conversational estimate of 85% complete. That estimate was not based on weighted acceptance criteria and overstated readiness against the full original prompt. A working, tested offline release is not completion of the requested end-to-end system. Passing tests cover implemented behavior; they do not prove missing capabilities exist.

| Requirement | Actual current scope | Remaining work | Needs user input now? |
|---|---|---|---|
| Upgrade Sentinel | Read-only discovery connected to actual installed 1.4.3/1.5.0 release environments, fixed shared pins, revalidated inventory and independently captured boundaries | Broader reviewed version/framework coverage and knowledge-based scheduling; no arbitrary application execution | No for the implemented controlled path |
| Boundary recording | Explicit recorder plus automatic capture of reviewed source and installed-SDK serializer boundaries; eight execution scenarios recorded | Broader framework instrumentation covering outbound requests, returned data and streaming in an actual workflow | No, implementation remains; live verification later needs API |
| Nemotron reasoning | Fixed-endpoint client and declarative proposals, mock-tested | Actual inference, assess generated cases and useful repair contribution | Nebius Token Factory access |
| Automated repair | Two reviewed patches plus actual GLM-generated declarative mapping, eight independent controls and preserved failed attempts | General candidate source patches and isolated execution; current bounded plan path is implemented and live-tested | Arbitrary execution needs a functioning isolation backend |
| Task replay | Actual GLM fixture-tool loop: original adapter fails locally, verified mapping preserves calls, task returns 21 | Broader applications and separately installed before/after environments; requested Nebius runtime | Implementation plus authorized Nebius runtime |
| ASM | Scoped evidence plus verified repair-plan reuse; one real GLM pair used 3 requests initially and 2 on reuse, with all checks and tasks repeated | Multiple independent workflows and repeated measurements; single exact-repeat pair does not establish general savings | Implementation and actual observations |
| CrewAI reproduction | Pinned source harness plus complete installed dependency environment; real BaseLLM and google.genai formatter reproduction/repair, eight controls | Constructor/client and live vision behavior remain outside the verified formatter scope | No API required for implemented serializer scope |
| Reliability Lab | Model discovery; four schema/tool/stream/error probes; request latency/usage; feedback draft generator | Broader justified experiments, model differences, context/output limits, retry/idempotency semantics, cost/throughput measurement, actual findings | Implementation plus Nebius access; no finding guaranteed |
| Tavily | Two historical real basic searches; paired GLM experiment executed, 14/14 without documents versus 13/14 with documents | Improve task-specific research and demonstrate usefulness; current result does not establish benefit | Engineering and newly configured credentials for future live experiments |
| Five-arm evaluation | Real GLM development path executes all 70 rows: comparator, original ACV review adapter, GLM, GLM+Tavily, exact scoped reuse | Requested Nemotron arms, new independent holdouts, repeated trials; original ACV review has an explicit conservative label adapter and is not identical to classification | Engineering plus authorized Nebius runtime |
| Security | Fixed trusted snapshots, bounded processes/requests, redaction and security tests | OS-level isolation with resource/network/filesystem controls before executing generated or unfamiliar code | No Docker/Podman executable found on PATH; WSL executable alone does not establish a working isolation backend |
| Demo | Real 95-second GLM workflow recording with English narration, English/Chinese captions and reviewed frames | Competition runtime footage if required and public YouTube publication | Account access/authorization for publication |
| Submission | Public source/test build, English drafts, successful CI | Authentic model usage/feedback, actual private form, entrant information and final submission | Account access and final approval |

## Award-focused order

1. Establish legitimate Nebius Token Factory access and NVIDIA Nemotron runtime use. Official rules also allow qualifying Nebius AI Cloud deployment; the current implementation uses Token Factory.
2. Complete one real detect/reproduce/generated-test/repair/verify/task-replay chain with negative controls and rejected candidates.
3. Run repeated, documented platform experiments; distinguish request mistakes, model limits, SDK faults and platform behavior. Useful positive observations count as evidence; do not manufacture negative findings.
4. Implement and run the comparison arms and task-specific Tavily research. Measure the effect instead of claiming it from API presence.
5. Record the proven workflow and complete the actual submission fields.

The remaining engineering is the assistant's work. API credentials enable live experiments but do not automatically finish these implementations. No defensible winning probability or fixed remaining-work percentage is available.

## Access and credits

- Recommended: a Nebius Token Factory API key with accessible NVIDIA Nemotron models and a stated credit/spend limit. Keep the key locally; share only its file path or environment-variable name.
- Tavily access is additionally needed to finish the original Tavily requirement and pursue its bonus award.
- NVIDIA's hosted free APIs and a DeepSeek API can support other development experiments, but neither alone substitutes for the required Nebius platform use. The existing client does not accept these keys interchangeably.
- Official resources list $25 Token Factory credits through the promo form with code `NEBIUS-DEVPOST-GLOBAL26`, plus another $25 through the Builders Program; approval and account availability must be verified.
- Sources: https://nebiusglobalaihackathon.devpost.com/rules ; https://nebiusglobalaihackathon.devpost.com/details/faqs ; https://nebiusglobalaihackathon.devpost.com/resources .
