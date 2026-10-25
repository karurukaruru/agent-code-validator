# Final review — live development release 0.3.1

**Local 0.3.2 handoff update:** 168 local tests passed, four Windows permission skips; bounded plan reuse now reruns verification and the task, with one actual first/repeat pair recorded in `evidence/glm-reuse`. The new version remains unpushed. `HANDOFF_ZH.md` and `FINISH_PLAN_ZH.md` are the current handoff and acceptance criteria; the 0.3.1 review below remains historical.

The GLM development path runs end to end, with preserved raw responses, failed attempts, independent repair controls, actual local tool execution, a reviewed narrated video and an executable comparison. This is a scoped prototype, not completion of the full original mission or a competition-compliant submission.

| Gate | Current result | Evidence or limitation |
|---|---|---|
| Actual model inference | PASS for GLM only | Exact glm-5.3-flash; no NVIDIA/Nemotron inference |
| Detect / propose / verify / task recovery | PASS in bounded scope | Two successful live runs; eight independent controls and rejected ID mutation |
| Historical SDK defect | PASS | Installed NVIDIA SDK 1.4.3 original FAIL, repaired copy PASS; source-only CrewAI reproduction |
| Generated test execution | NEEDS_REVIEW | Five model tests executed; two incorrect model expectations preserved |
| Five-arm development evaluation | EXECUTED | 70 rows; ACV review adapter explicitly differs from direct classification |
| Tavily benefit | NOT ESTABLISHED | C 14/14, D 13/14 on one developer-authored trial |
| Knowledge reuse | PASS in exact scope | 12 validated exact-match hits; all 14 comparisons rerun; no token-savings estimate |
| Workbench | PASS | 13 real Chrome checks, desktop/mobile and request authorization |
| Local test suite | PASS | 161 passed, four Windows symlink permission skips |
| Package | PASS after isolated verification | See evidence/tests/wheel-verification-glm.json |
| Video | LOCAL ARTIFACT COMPLETE | 95 seconds, English audio/captions, Chinese SRT, inspected frames and full decode |
| Nebius reliability feedback | BLOCKED | User stopped NVIDIA calls; discovery alone is not inference or platform findings |
| Full original mission | INCOMPLETE | Explicit gap audit includes automatic environments, broad instrumentation and sandboxed source repair |
| Public YouTube / final Devpost | OUTSTANDING | No uploaded video or final submission claimed |

Review fixes include model tool-call ordinal handling, guaranteed structured task output, preservation of failed model expectations, stronger mapping controls, stale display state, oversized subtitles, fixed placeholder evaluation arms and stale package-version metadata. All new network use is fixed-provider, explicitly bounded, with no automatic retry and no browser-visible API credentials.

Runtime evidence, synthetic tests and historical artifacts are kept distinct. The new 0.3.1 commit `37aba3524acd109fd588e495e48a49fe1afecc38` passed **all 165 tests on both Ubuntu Python 3.10 and 3.13**, including all four tests skipped locally for Windows permissions. Demo, exported regression and offline benchmark steps also passed. See [CI run 40163644009](https://github.com/karurukaruru/agent-code-validator/actions/runs/40163644009) and `evidence/tests/github-actions-glm.json`. Anonymous downloads of the new wheel and video match local SHA-256 checksums (`evidence/tests/public-download-glm.json`). Archive contents were individually compared with reviewed source and scanned (`evidence/tests/wheel-publish-safety.json`). File hashes establish integrity, not independent provider authentication.

Remaining engineering belongs to the project work, not to the user merely supplying another key. User-dependent steps are competition-runtime authorization if resumed, entrant/account access, public video publication and final submission approval. No fixed completion percentage or numerical winning probability is supported.
