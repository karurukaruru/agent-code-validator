"""Check the frozen input contract against a saved candidate; no SDK code runs.

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
        self.assertEqual(hashlib.sha256(data).hexdigest(), "f5561f08c22968467451755aca412bb807fa6c9580ee0817896faeae7b1dae87", "Frozen contract changed; inspect and export a new gate")
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
