# Downloadable developer build

Local development update: `agent_code_validator-0.3.2-py3-none-any.whl` now includes the reviewed boundary runner as well as reasoning/reporting fixes and verified plan reuse. Its packaged boundary workers and demo passed isolated verification; the full local suite passed 181 tests (four Windows permission skips). This build is not yet published; the 0.3.1 public-download/CI records below are historical. See `../BOUNDARY_RUN.md`, `../HANDOFF_ZH.md` and `../FINISH_PLAN_ZH.md` for scope and completion criteria.

- `agent_code_validator-0.3.1-py3-none-any.whl`: Python 3.10+ package. Install with `python -m pip install <wheel-path>`. Configure local GLM_API_KEY and run `patchcourt live-demo --port 8780`, or run `patchcourt demo --output outputs/patchcourt` without keys.
- `patchcourt-glm-live-demo.mp4`: actual 95-second live GLM browser workflow, English synthesized narration and burned-in English captions.
- `patchcourt-live.en.srt` / `patchcourt-live.zh.srt`: complete English/Chinese subtitle files.
- `SHA256SUMS.json`: hashes and byte counts for every downloadable release asset.

The new wheel's CLI and packaged resources are checked from an isolated extraction. The live workflow is bounded, executes local fixture tools and never arbitrary model Python. API credentials are not included. GLM use does not establish Nebius/NVIDIA competition eligibility. Full scope: ../GLM_DEVELOPMENT.md.

The 0.3.1 wheel and live video were anonymously downloaded from commit `37aba3524acd109fd588e495e48a49fe1afecc38`; both SHA-256 checksums matched. This commit also passed all 165 tests on Ubuntu Python 3.10 and 3.13. See `../evidence/tests/public-download-glm.json` and `../evidence/tests/github-actions-glm.json`.

Archived 0.3.0 assets remain available: patchcourt-demo-0.3.0.zip (unpack, open index.html, select report.json), the older wheel, and the 112-second silent offline video/subtitle. They are explicitly historical and do not include the new live workflow. Their anonymous public download was verified in evidence/tests/public-download.json.
