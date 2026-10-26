# PatchCourt — judge testing instructions

**Target platform:** Windows, Linux or macOS with Python 3.10 or newer and a modern browser. The packaged offline demonstration requires no paid account, API key or optional SDK dependency. All instructions are in English.

## Start the exported judge portal

Download `release/patchcourt-judge-demo-0.5.1-development.zip` and extract it.
Double-click `Start-Judge-Demo.cmd` on Windows, or run `python launch_demo.py`.
The launcher uses a free dynamic localhost port and opens the browser; stop it
with Ctrl+C. It installs nothing and sends no provider request. Alternatively,
open `index.html` directly for repair playback; serve the folder for automatic
SDK report loading.

Choose **Replay the verified repair** to inspect an actual saved DeepSeek
conversation, then **Inspect a real SDK upgrade** for the separately executed
1.4.3/1.5.0 comparison. The development-provider label stays visible. This is a
recorded evidence demonstration, not fresh cloud inference and not proof of the
pending required Nebius/NVIDIA platform use.

## Start the source demonstration in two commands

From a fresh source checkout or extracted source release:

```bash
python -m patchcourt demo --output outputs/judge-demo
python -m patchcourt serve outputs/judge-demo --port 8765
```

Open `http://127.0.0.1:8765` on the same computer. On Windows, `Start-PatchCourt.cmd` starts a fresh offline demonstration. If port 8765 is occupied, choose another port. Stop the local server with Ctrl+C. An exported `index.html` can also open the saved `report.json` through **Open evidence**.

## Five-minute review

1. Open the NVIDIA tool-call case. The historical adapter loses calls and leaves orphaned tool results. **FAIL** is the correctly detected defect, not a broken application launch.
2. Inspect the repaired boundary, independent controls and counterexample. The repair must preserve IDs, names and arguments. A deliberately corrupted repair must be rejected.
3. Inspect task recovery. The deterministic offline task returns **21** after the reviewed repair. This offline replay is labeled separately from actual saved model conversations.
4. Open the CrewAI/Gemini case. Inspect the lost image bytes, reviewed formatting repair and limits. Preserved image bytes do not establish a live vision-task result.
5. Open saved provenance and scope. Source hashes, environment, failed attempts and request records show which paths actually executed.

The dependency-free demo uses audited source functions and inert SDK-shaped types. Stronger installed-SDK evidence is retained in `evidence/full-sdk`, `evidence/crewai-sdk` and `evidence/upgrade-run-050/real-sdk`. These are separate executed experiments, with exact setup and limitations described in [REPRODUCTION_GUIDE.md](REPRODUCTION_GUIDE.md) and [UPGRADE_RUN.md](UPGRADE_RUN.md).

## Inspect a captured-boundary CI gate

The 0.5.1 portal also links a complete standalone CI gate. Extract it and run
`python -I -S -m unittest discover -s . -p test_boundary_contract.py` from its
folder. Its observed broken candidate intentionally fails. The frozen input,
observed output, checker source and license are included. Supply a freshly
captured candidate to reuse this contract; the gate does not execute a future
SDK. [Complete capture-to-CI steps](CAPTURED_BOUNDARIES.md).

## Replay exported regression checks

```bash
python -m unittest discover -s outputs/judge-demo -p test_regression.py
```

For the complete development tests, install the documented dependencies and run:

```bash
python -m pip install -r requirements.txt
python -m pytest
```

Some optional installed-SDK/permission checks may skip when their explicit environment prerequisites are absent. Read the skip reason; an unavailable dependency is not evidence of a passing live run.

## Inspect cloud execution without supplying a key

The final delivery must link the actual completed required-platform run through `submission-manifest.json` → `runtime_workflow`. Its directory includes the workflow report, request/response records, independent verifier results, corruption control, tool-call boundaries and integrity manifest. Read those saved records without supplying credentials.

At this checkpoint that manifest field is **null**: the existing GLM development run and successful Nebius model discovery do not establish NVIDIA inference through Nebius. Do not treat a missing live-evidence gate as an executed result. The current public development ZIP has passed anonymous download, byte comparison and a fresh local launch; its URL and verification record are in the manifest. This does not replace the missing required-platform inference.

Fresh model inference requires legitimate platform access and incurs the provider's normal usage. API keys stay in local environment variables or an ignored local credential file; they are never requested from judges through the public viewer. The offline review and published evidence remain usable without a judge buying access. A local-only server is not a public remote inference endpoint.

## Scope to assess

The product verifies reviewed message boundaries and bounded declarative mappings. It does not execute generated Python, patch arbitrary production repositories or claim complete framework compatibility. Two supported releases can share a defect, producing **NEEDS_REVIEW** even when their serialized messages match. Credited historical defects demonstrate this distinction; they are not claimed as new discoveries.

If setup fails, preserve the Python version, OS, command and error text, excluding credentials. Consult [README.md](README.md), [TESTING.md](TESTING.md), and [SECURITY.md](SECURITY.md). The submission checker reports missing delivery evidence explicitly:

```bash
python scripts/submission_check.py
```
