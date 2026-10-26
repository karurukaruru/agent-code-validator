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
import unittest

ROOT = Path(__file__).resolve().parent


class CapturedBoundaryContract(unittest.TestCase):
    def test_candidate_preserves_captured_input(self):
        data = (ROOT / "contract.json").read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), "81bd542d7d8f4726c44309ba8630f1f9bf058484de28634ce49a8eb5f562868f", "Frozen contract changed; inspect and export a new gate")
        contract = json.loads(data)
        for name, expected in contract["runtime_files_sha256"].items():
            self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), expected, "Exported checker source changed")
        sys.path.insert(0, str(ROOT))
        from _patchcourt_contract.evidence import read_json
        from _patchcourt_contract.recording import read_recording, select_recording
        from _patchcourt_contract.semantic import compare_messages
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
            observed = (ROOT / "observed-candidate.json").read_bytes()
            self.assertEqual(hashlib.sha256(observed).hexdigest(), contract["observed_candidate_file_sha256"], "Observed fixture changed; supply future evidence through the documented environment variable")
            candidate = read_json(ROOT / "observed-candidate.json")
        verdict = compare_messages(contract["expected_input"], candidate)
        finding_paths = [(f.get("code"), f.get("path")) for f in verdict.get("findings", [])]
        self.assertEqual(verdict["status"], "PASS", "Captured contract is not preserved: " + str(finding_paths))


if __name__ == "__main__":
    unittest.main()
