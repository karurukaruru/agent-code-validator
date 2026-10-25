"""Real isolated workers, plus bounded failure and input-abstention cases."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from patchcourt.boundary_run import run_boundary, _run_side, validate_input
from patchcourt.cli import main
from patchcourt.counterexamples import tool_conversation
from patchcourt.evidence import digest, read_json


class BoundaryRunTests(unittest.TestCase):
    def run_pair(self, **kwargs):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "run"
            result = run_boundary(root, **kwargs)
            self.assertEqual(digest(read_json(root / "report.json")), read_json(root / "manifest.json")["report_sha256"])
            self.assertEqual(main(["verify", str(root)]), 0)
            self.assertTrue((root / "index.html").is_file())
            return result

    def test_real_children_detect_regression_and_record_boundaries(self):
        result = self.run_pair()
        self.assertEqual(result["status"], "FAIL")
        case = result["cases"][0]
        self.assertEqual(case["contracts"]["baseline"]["status"], "PASS")
        self.assertEqual(case["contracts"]["candidate"]["status"], "FAIL")
        self.assertEqual(case["task_replay"]["before"]["inventory_value"], 21)
        self.assertEqual(case["task_replay"]["after"]["status"], "FAIL")
        for run in result["executions"].values():
            self.assertNotEqual(run["pid"], os.getpid())
            self.assertEqual([e["stage"] for e in run["events"]], ["framework_input", "adapter_output"])
            self.assertEqual(run["input_conversion"]["status"], "PASS")
            self.assertEqual(run["provider_requests"], 0)
            self.assertFalse(run["provenance"]["real_sdk_classes"])

    def test_identical_broken_variants_never_pass(self):
        result = self.run_pair(baseline="upstream", candidate="upstream")
        self.assertEqual(result["status"], "NEEDS_REVIEW")
        self.assertEqual(result["cases"][0]["direction"], "baseline_and_candidate_unhealthy")

    def test_repaired_candidate_reports_recovery_without_trusting_bad_baseline(self):
        result = self.run_pair(baseline="upstream", candidate="reviewed-patch")
        self.assertEqual(result["status"], "NEEDS_REVIEW")
        case = result["cases"][0]
        self.assertEqual(case["direction"], "candidate_restores_contract")
        self.assertEqual(case["contracts"]["candidate"]["status"], "PASS")
        self.assertEqual(case["task_replay"]["after"]["inventory_value"], 21)

    def test_healthy_pair_preserves_unicode_nested_false_zero(self):
        messages = tool_conversation()
        messages[0]["tool_calls"][0]["function"]["arguments"] = '{"城市":"東京","x":[false,0,{"k":null}]}'
        result = self.run_pair(candidate="reviewed-patch", messages=messages)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["summary"]["pass"], 1)
        self.assertNotIn("task_replay", result["cases"][0])

    def test_plain_text_has_no_false_positive(self):
        result = self.run_pair(messages=[{"role": "system", "content": "instruction"}, {"role": "user", "content": "hello"}, {"role": "assistant", "content": "world"}])
        self.assertEqual(result["status"], "PASS")

    def test_unsupported_metadata_and_content_do_not_start_processes(self):
        inputs = [[], [{"role": "developer", "content": "text"}],
                  [{"role": "user", "content": "hello", "response_metadata": {"opaque": 1}}],
                  [{"role": "user", "content": [{"type": "text", "text": "hello"}]}],
                  [{"role": "user", "content": "sk-testcredential123456"}],
                  [{"role": "user", "content": "x" * 128001}]]
        broken = tool_conversation(); broken[1]["tool_call_id"] = "orphan"; inputs.append(broken)
        for messages in inputs:
            with self.subTest(messages=str(messages)[:80]), patch("patchcourt.boundary_run._run_side") as child:
                result = self.run_pair(messages=messages)
                child.assert_not_called()
                self.assertEqual(result["status"], "INCONCLUSIVE")

    def test_ambiguous_json_and_non_openai_calls_rejected(self):
        for arguments in ('{"x":1,"x":2}', '{"x":NaN}', '[]'):
            messages = tool_conversation()
            messages[0]["tool_calls"][0]["function"]["arguments"] = arguments
            with self.assertRaises(ValueError):
                validate_input(messages)
        messages = tool_conversation()
        messages[0]["tool_calls"][0] = {"id": "call_a", "name": "inventory", "args": {}}
        with self.assertRaises(ValueError):
            validate_input(messages)

    def test_missing_installed_sdk_is_preserved_as_uncertainty(self):
        with tempfile.TemporaryDirectory() as sdk:
            result = self.run_pair(sdk_root=sdk)
        self.assertEqual(result["status"], "INCONCLUSIVE")
        self.assertIn("FileNotFoundError", result["executions"]["baseline"]["error"])

    def test_changed_installed_source_is_not_executed(self):
        with tempfile.TemporaryDirectory() as sdk:
            source = Path(sdk) / "langchain_nvidia_ai_endpoints" / "_utils.py"
            source.parent.mkdir(); source.write_text('raise AssertionError("must not execute")', encoding="utf-8")
            result = self.run_pair(sdk_root=sdk)
        self.assertEqual(result["status"], "INCONCLUSIVE")
        self.assertIn("not the reviewed", result["executions"]["candidate"]["error"])

    def test_child_does_not_receive_parent_credentials_or_pythonpath(self):
        actual = subprocess.Popen
        def observe(*args, **kwargs):
            self.assertNotIn("GLM_API_KEY", kwargs["env"])
            self.assertNotIn("PYTHONPATH", kwargs["env"])
            self.assertNotIn("LANGSMITH_API_KEY", kwargs["env"])
            self.assertIn("-I", args[0]); self.assertIn("-S", args[0])
            return actual(*args, **kwargs)
        with patch.dict(os.environ, {"GLM_API_KEY": "test-private-credential", "LANGSMITH_API_KEY": "test-private-telemetry", "PYTHONPATH": "untrusted"}), patch("patchcourt.boundary_run.subprocess.Popen", side_effect=observe):
            result = _run_side(tool_conversation(), "reviewed-patch", None)
        self.assertEqual(result["status"], "EXECUTED")

    def test_timeout_kills_worker_and_reports_uncertainty(self):
        with patch("patchcourt.boundary_run.subprocess.Popen") as create, patch("patchcourt.boundary_run.TIMEOUT", -1):
            child = create.return_value
            child.wait.side_effect = [subprocess.TimeoutExpired("worker", 0.1), 0]
            child.returncode = -9
            result = _run_side(tool_conversation(), "upstream", None)
            child.kill.assert_called_once()
        self.assertEqual(result["status"], "INCONCLUSIVE")
        self.assertIn("deadline", result["error"])

    def test_output_budget_kills_worker(self):
        actual = subprocess.Popen
        def noisy(*args, **kwargs):
            kwargs["stdout"].write(b"x" * 1000); kwargs["stdout"].flush()
            return actual(*args, **kwargs)
        with patch("patchcourt.boundary_run.OUTPUT_LIMIT", 100), patch("patchcourt.boundary_run.subprocess.Popen", side_effect=noisy):
            result = _run_side(tool_conversation(), "upstream", None)
        self.assertEqual(result["status"], "INCONCLUSIVE")
        self.assertIn("output budget", result["error"])

    def test_existing_evidence_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            marker = Path(temp) / "keep.txt"; marker.write_text("original", encoding="utf-8")
            self.assertEqual(main(["boundary-run", "--output", temp]), 2)
            self.assertEqual(marker.read_text(encoding="utf-8"), "original")


if __name__ == "__main__":
    unittest.main()
