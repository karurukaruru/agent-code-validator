"""Export a captured user boundary and a portable, independently rerunnable gate."""
import hashlib
from pathlib import Path
import shutil
import zipfile

from . import __version__
from .evidence import canonical, digest, sanitize, write_json
from .recording import read_recording, select_recording
from .semantic import compare_messages

PORTABLE_GATE_FILES = ("contract.json", "observed-candidate.json", "test_boundary_contract.py", "REGRESSION-GATE.md",
                       "_patchcourt_contract/version_snapshot.py", "_patchcourt_contract/evidence.py",
                       "_patchcourt_contract/semantic.py", "_patchcourt_contract/recording.py", "_patchcourt_contract/LICENSE")


GATE_TEST = '''"""Check the frozen input contract against a saved candidate; no SDK code runs.

Default: the observed candidate. A broken observation intentionally fails.
Set PATCHCOURT_CANDIDATE_TRACE to a future message-array JSON, or set
PATCHCOURT_CANDIDATE_RECORDING to a future BoundaryRecorder recording.
For a multi-transaction recording also set PATCHCOURT_REQUEST_ID.
"""
import hashlib
import json
import os
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parent


class CapturedBoundaryContract(unittest.TestCase):
    def bounded_bytes(self, path, limit):
        self.assertLessEqual(path.stat().st_size, limit, "Gate artifact exceeds its size limit")
        with path.open("rb") as stream:
            data = stream.read(limit + 1)
        self.assertLessEqual(len(data), limit, "Gate artifact exceeds its size limit")
        return data

    def test_candidate_preserves_captured_input(self):
        data = self.bounded_bytes(ROOT / "contract.json", 8_000_000)
        self.assertEqual(hashlib.sha256(data).hexdigest(), "CONTRACT_SHA256", "Frozen contract changed; inspect and export a new gate")
        contract = json.loads(data)
        verified_sources = {}
        for name, expected in contract["runtime_files_sha256"].items():
            source = self.bounded_bytes(ROOT / name, 1_000_000)
            self.assertEqual(hashlib.sha256(source).hexdigest(), expected, "Exported checker source changed")
            verified_sources[name] = source
        # Isolate snapshots when one CI process discovers several gate folders.
        # Compile exactly the verified bytes: never reuse pyc or preloaded modules.
        # These are fixed own-project checker modules, never captured/model Python.
        namespace = "_patchcourt_contract_" + hashlib.sha256(data).hexdigest()
        loaded = {}
        for short_name in ("__init__", "evidence", "semantic", "recording"):
            # No physical __init__.py: unittest discovery must not import the
            # snapshot directory before the test has checked its source hashes.
            filename = "version_snapshot" if short_name == "__init__" else short_name
            relative = "_patchcourt_contract/" + filename + ".py"
            module_name = namespace if short_name == "__init__" else namespace + "." + short_name
            module = types.ModuleType(module_name)
            module.__file__ = str(ROOT / relative)
            module.__package__ = namespace
            if short_name == "__init__":
                module.__path__ = []  # No fallback imports from an unverified file.
            sys.modules[module_name] = module
            exec(compile(verified_sources[relative], module.__file__, "exec"), module.__dict__)
            loaded[short_name] = module
        evidence_module, recording_module = loaded["evidence"], loaded["recording"]
        compare_messages = loaded["semantic"].compare_messages
        read_json = evidence_module.read_json
        read_recording, select_recording = recording_module.read_recording, recording_module.select_recording
        self.assertEqual(compare_messages(contract["expected_input"], contract["expected_input"])["status"], "PASS", "Frozen input is unsupported or invalid")
        trace = os.environ.get("PATCHCOURT_CANDIDATE_TRACE")
        recording = os.environ.get("PATCHCOURT_CANDIDATE_RECORDING")
        self.assertFalse(trace and recording, "Choose a candidate trace or a recording, not both")
        if recording:
            selected = select_recording(read_recording(recording), os.environ.get("PATCHCOURT_REQUEST_ID"))
            self.assertEqual(selected["adapter"], contract["adapter"], "Candidate adapter identity differs")
            self.assertFalse(selected["payload_redacted"], "A redacted capture cannot prove preservation of the original input")
            self.assertEqual(compare_messages(contract["expected_input"], selected["original_input"])["status"], "PASS", "Candidate recording uses a different input contract")
            candidate = selected["candidate"]
        elif trace:
            candidate = read_json(trace)
            self.assertIsInstance(candidate, list, "Candidate trace must be a message array")
        else:
            observed = self.bounded_bytes(ROOT / "observed-candidate.json", 8_000_000)
            self.assertEqual(hashlib.sha256(observed).hexdigest(), contract["observed_candidate_file_sha256"], "Observed fixture changed; supply future evidence through the documented environment variable")
            candidate = read_json(ROOT / "observed-candidate.json")
        verdict = compare_messages(contract["expected_input"], candidate)
        finding_paths = [(f.get("code"), f.get("path")) for f in verdict.get("findings", [])]
        self.assertEqual(verdict["status"], "PASS", "Captured contract is not preserved: " + str(finding_paths))


if __name__ == "__main__":
    unittest.main()
'''


def _export_gate(output, selected, observed_status):
    package = output / "_patchcourt_contract"
    package.mkdir()
    (package / "version_snapshot.py").write_text('__version__ = ' + repr(__version__) + '\n', encoding="utf-8")
    root = Path(__file__).resolve().parent
    for name in ("evidence.py", "semantic.py", "recording.py"):
        shutil.copyfile(root / name, package / name)
    shutil.copyfile(root / "fixtures" / "PATCHCOURT-LICENSE", package / "LICENSE")
    runtime = {path.relative_to(output).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
               for path in sorted(package.iterdir()) if path.is_file()}
    write_json(output / "observed-candidate.json", selected["candidate"])
    contract = {"schema_version": "1.0", "kind": "captured-boundary-regression-contract",
                "adapter": selected["adapter"], "captured_version": selected["version"],
                "request_id": selected["request_id"], "expected_input": selected["original_input"],
                "observed_status": observed_status, "runtime_files_sha256": runtime,
                "observed_candidate_file_sha256": hashlib.sha256((output / "observed-candidate.json").read_bytes()).hexdigest(),
                "scope": "Checks captured messages, not future SDK execution; the source recording is user-supplied and is not independently authenticated"}
    write_json(output / "contract.json", contract)
    checksum = hashlib.sha256((output / "contract.json").read_bytes()).hexdigest()
    (output / "test_boundary_contract.py").write_text(GATE_TEST.replace("CONTRACT_SHA256", checksum), encoding="utf-8")
    (output / "REGRESSION-GATE.md").write_text("# Captured boundary regression gate\n\nRun `python -m unittest discover -s . -p test_boundary_contract.py` from this folder. Only Python's standard library is required; the frozen PatchCourt checker source and license are bundled.\n\nThe default candidate is the actual observed output. A broken observation intentionally produces a failing test. Set `PATCHCOURT_CANDIDATE_TRACE` to a future message-array JSON file, or `PATCHCOURT_CANDIDATE_RECORDING` to a new BoundaryRecorder recording. Multi-transaction recordings also require `PATCHCOURT_REQUEST_ID`. A new recording must use the same adapter and preserve the frozen input; its SDK version and transaction ID may differ.\n\nCapture the new SDK output before running the gate. This test does not execute or authenticate a future SDK or application. No model, network, generated model code or provider credentials are used. Review captured data before publishing it. Hashes detect accidental changes; they do not authenticate an untrusted producer.\n", encoding="utf-8")
    archive = output / "regression-gate.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
        for name in PORTABLE_GATE_FILES:
            zipped.write(output / name, name)
    return {"status": "EXPORTED", "default_candidate_status": observed_status,
            "default_test_expected": "PASS" if observed_status == "PASS" else "FAIL",
            "standalone_standard_library": True, "runtime_files_sha256": runtime,
            "contract_file_sha256": checksum,
            "test_file_sha256": hashlib.sha256((output / "test_boundary_contract.py").read_bytes()).hexdigest(),
            "download_file": "regression-gate.zip", "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest()}


def check_recording(recording_path, output, request_id=None):
    from .runner import export_report, make_report
    output = Path(output)
    if output.exists():
        raise ValueError("Use a new output directory; prior captured evidence must not be overwritten")
    recording = read_recording(recording_path)
    # Redaction must never collapse unequal sensitive values into a false PASS.
    if canonical(recording) != canonical(sanitize(recording)):
        raise ValueError("Recording still contains data requiring redaction; capture safe fixture data before exporting a public contract")
    selected = select_recording(recording, request_id)
    baseline = compare_messages(selected["original_input"], selected["original_input"])
    verdict = compare_messages(selected["original_input"], selected["candidate"])
    if selected["payload_redacted"]:
        verdict = {"status": "INCONCLUSIVE", "findings": [{"code": "REDACTED_CAPTURE", "path": "",
                    "message": "Capture redaction changed payloads; it cannot establish original message preservation"}]}
    case = {"id": "captured-boundary", "title": selected["adapter"] + " / " + selected["request_id"],
            **verdict, "baseline": selected["original_input"], "candidate": selected["candidate"],
            "contracts": {"input": baseline, "baseline": baseline, "candidate": verdict, "difference": verdict},
            "execution": False, "provenance": {"kind": "User-supplied opt-in BoundaryRecorder transaction; no SDK is executed by this check",
                "adapter": selected["adapter"], "version": selected["version"], "request_id": selected["request_id"],
                "recording_sha256": digest(recording), "timestamps": selected["timestamps"], "event_indexes": selected["event_indexes"]}}
    report = make_report([case])
    report.update({"mode": "recording-check", "status": verdict["status"], "input": selected["original_input"],
        "provider_requests": 0, "recording": {key: selected[key] for key in ("adapter", "version", "request_id", "recording_event_count", "payload_redacted")},
        "limitations": ["Checks a selected captured message pair without executing an SDK or application.",
                         "A saved recording and its checksums do not independently authenticate its producer.",
                         "A future regression gate requires a freshly captured candidate trace or recording."]})
    output.mkdir(parents=True, exist_ok=False)
    if baseline["status"] == "PASS" and not selected["payload_redacted"]:
        report["regression_gate"] = _export_gate(output, selected, verdict["status"])
    else:
        report["regression_gate"] = {"status": "BLOCKED", "reason": "A valid, supported, unredacted input contract is required"}
    exported = export_report(report, output)
    page = output / "index.html"
    html = page.read_text(encoding="utf-8")
    page.write_text(html.replace("<head>", '<head><meta name="patchcourt-static-export" content="recording-check">', 1), encoding="utf-8")
    return exported
