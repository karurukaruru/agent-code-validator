# PatchCourt 0.5.1 developer delivery

- [Judge demo ZIP](patchcourt-judge-demo-0.5.1-development.zip): extract and double-click Start-Judge-Demo.cmd on Windows, or run `python launch_demo.py`. Includes actual saved repair evidence, installed-SDK inspection and a downloadable captured-boundary CI gate. No API key is needed.
- [Python wheel](agent_code_validator-0.5.1-py3-none-any.whl): current installable CLI, recording checker and source resources; isolated checks passed.
- [Standalone captured CI gate](patchcourt-captured-gate-0.5.1.zip): only Python's standard library is required. Its saved broken candidate intentionally fails. A future candidate must preserve the captured input; [instructions](../CAPTURED_BOUNDARIES.md) explain the complete loop.
- [Checksums](SHA256SUMS-0.5.1.json).

[Current review](../RELEASE_REVIEW_051_ZH.md) records fixes, verification and limits.
No model/search credit was used for 0.5.1 development. The earlier English
DeepSeek video is development evidence; the final competition video awaits
actual required-platform inference. [Your three final steps](../USER_ACTIONS_ZH.md).

## Historical 0.5.0 assets

# PatchCourt 0.5.0 development delivery

- [patchcourt-judge-demo-0.5.0-development.zip](patchcourt-judge-demo-0.5.0-development.zip): free recorded-evidence portal. Extract and double-click `Start-Judge-Demo.cmd` on Windows, or run `python launch_demo.py`. No API key, account or pip install is needed. Recorded DeepSeek repair, independent controls and real installed-SDK comparison are explicitly scoped.
- [agent_code_validator-0.5.0-py3-none-any.whl](agent_code_validator-0.5.0-py3-none-any.whl): installable Python build, isolated CLI/resource checks passed.
- [patchcourt-development-replay-0.5.0.mp4](patchcourt-development-replay-0.5.0.mp4): 137-second English narrated, captioned browser replay of real saved DeepSeek development evidence. It is not a fresh inference capture or the final NVIDIA/Nebius competition video.
- [patchcourt-development-replay-0.5.0.en.srt](patchcourt-development-replay-0.5.0.en.srt): English subtitle file.
- [SHA256SUMS-0.5.0.json](SHA256SUMS-0.5.0.json): byte counts and checksums for these files.

Current verification and remaining required-platform/publication/form gates:
[RELEASE_REVIEW_050_ZH.md](../RELEASE_REVIEW_050_ZH.md),
[SUBMISSION_CHECKLIST.md](../SUBMISSION_CHECKLIST.md). No final submission or award is claimed.

## Historical builds

# Downloadable developer build

Latest local build: **0.4.0**. `agent_code_validator-0.4.0-py3-none-any.whl`
contains the controlled real SDK upgrade runner, fixed common dependencies,
stronger protocol validation and the upgrade evidence UI. `patchcourt-demo-0.4.0.zip`
is a fresh offline demonstration: unzip, open `index.html`, choose `report.json`.
Both require no API key for offline use. Full scope and current local results:
[development review](../DEVELOPMENT_REVIEW_ZH.md). No new remote publication or
0.4.0 remote CI is claimed. The SDK/CrewAI execution evidence is shipped in the
source tree, rather than claimed to be a live provider result.

The paragraphs below describe historical releases.

Local development update: `agent_code_validator-0.3.2-py3-none-any.whl` now includes the reviewed boundary runner as well as reasoning/reporting fixes and verified plan reuse. Its packaged boundary workers and demo passed isolated verification; the full local suite passed 186 tests (four Windows permission skips). This build is not yet published; the 0.3.1 public-download/CI records below are historical. See `../BOUNDARY_RUN.md`, `../HANDOFF_ZH.md` and `../FINISH_PLAN_ZH.md` for scope and completion criteria.

- `agent_code_validator-0.3.1-py3-none-any.whl`: Python 3.10+ package. Install with `python -m pip install <wheel-path>`. Configure local GLM_API_KEY and run `patchcourt live-demo --port 8780`, or run `patchcourt demo --output outputs/patchcourt` without keys.
- `patchcourt-glm-live-demo.mp4`: actual 95-second live GLM browser workflow, English synthesized narration and burned-in English captions.
- `patchcourt-live.en.srt` / `patchcourt-live.zh.srt`: complete English/Chinese subtitle files.
- `SHA256SUMS.json`: hashes and byte counts for every downloadable release asset.

The new wheel's CLI and packaged resources are checked from an isolated extraction. The live workflow is bounded, executes local fixture tools and never arbitrary model Python. API credentials are not included. GLM use does not establish Nebius/NVIDIA competition eligibility. Full scope: ../GLM_DEVELOPMENT.md.

The 0.3.1 wheel and live video were anonymously downloaded from commit `37aba3524acd109fd588e495e48a49fe1afecc38`; both SHA-256 checksums matched. This commit also passed all 165 tests on Ubuntu Python 3.10 and 3.13. See `../evidence/tests/public-download-glm.json` and `../evidence/tests/github-actions-glm.json`.

Archived 0.3.0 assets remain available: patchcourt-demo-0.3.0.zip (unpack, open index.html, select report.json), the older wheel, and the 112-second silent offline video/subtitle. They are explicitly historical and do not include the new live workflow. Their anonymous public download was verified in evidence/tests/public-download.json.
