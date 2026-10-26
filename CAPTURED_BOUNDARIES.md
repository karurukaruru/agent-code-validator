# Turn your captured boundary into a regression gate

Wrap the adapter you choose, then export its actual input/output contract. The
checker reads message data; it never imports the repository being inspected or
executes a model's proposed Python. Capture with a new `BoundaryRecorder`
transaction ID for every adapter call:

```python
from patchcourt.recorder import BoundaryRecorder

recorder = BoundaryRecorder("my-agent/message-adapter", "1.0")
outbound, verdict = recorder.transform(messages, my_adapter, request_id="request-001")
recorder.save("outputs/boundary.json")
```

`my_adapter` is the callable your application already uses. The example does
not instrument a whole framework. Inspect and sanitize private data before
publishing recordings. If redaction changed a payload, PatchCourt abstains
instead of treating two masked values as proof of equivalence.

## Try the complete loop without an account

Run these commands separately from the source checkout. The example is an
in-memory courier adapter with one deliberately omitted tool call; it makes no
SDK or model request.

```bash
python examples/captured-boundary/capture.py --output outputs/courier-broken.json
python -m patchcourt check-recording outputs/courier-broken.json --output outputs/courier-gate
python -I -S -m unittest discover -s outputs/courier-gate -p test_boundary_contract.py
```

The check command returns **1 / FAIL**, and the exported test is red. That is
the detected defect. The output includes an evidence viewer, frozen input,
observed output, a standalone checker snapshot with its license, and a test
bound to those files. It checks this captured courier boundary, not the built-in
inventory/price demonstration.

Capture a later candidate, then ask the same frozen gate to inspect it:

```bash
python examples/captured-boundary/capture.py --fixed --output outputs/courier-fixed.json
```

On PowerShell:

```powershell
$env:PATCHCOURT_CANDIDATE_RECORDING = (Resolve-Path outputs/courier-fixed.json).Path
python -I -S -m unittest discover -s outputs/courier-gate -p test_boundary_contract.py
Remove-Item Env:PATCHCOURT_CANDIDATE_RECORDING
```

On bash:

```bash
PATCHCOURT_CANDIDATE_RECORDING="$PWD/outputs/courier-fixed.json" python -I -S -m unittest discover -s outputs/courier-gate -p test_boundary_contract.py
```

The repaired candidate is green. Altering a call ID makes it red again. A
candidate recording must preserve the same input and adapter identity; its
version and transaction ID may change. For a recording with several
transactions, select `--request-id` while exporting and set
`PATCHCOURT_REQUEST_ID` when checking a future capture. A raw message-array JSON
can instead be supplied through `PATCHCOURT_CANDIDATE_TRACE`.

## Put the gate in CI

Copy the entire exported gate directory to your repository. Capture the new
SDK's output in the application's test job, set the candidate path, and run the
generated unittest. The test needs only Python's standard library; `-I -S`
demonstrates independence from installed PatchCourt and third-party packages.
The captured test does not execute or independently authenticate a future SDK.
Running the adapter and supplying a fresh candidate remains the application's
responsibility.

Missing or duplicate pairs, unsupported input, changed input/adapter identity,
redacted captures, and altered contract/runtime files stop the gate. Legacy
captures without paired request IDs must be captured again rather than guessed.

The installed-SDK integration in `scripts/verify_recording_gate.py` separately
executes an unmodified NVIDIA 1.4.3 serializer and a reviewed patch with real
installed SDK types. Its three expected outcomes are broken/red, patched/green,
and corrupted/red, with zero provider requests. The patch is explicitly local;
it is not an upstream fixed release.
