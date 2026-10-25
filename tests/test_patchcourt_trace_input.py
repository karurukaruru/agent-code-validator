"""Optional input contracts catch equal-but-broken captured traces."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from patchcourt.cli import main
from patchcourt.counterexamples import tool_conversation
from patchcourt.evidence import digest, read_json, write_json
from patchcourt.sentinel import check_trace_pair


class TraceInputTests(unittest.TestCase):
    def test_explicit_null_input_never_selects_a_demo_or_prepares_dependencies(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "input.json").write_text("null", encoding="utf-8")
            args = ["--input", str(root / "input.json"), "--output", str(root / "report")]
            with patch("patchcourt.boundary_run.run_boundary") as boundary, patch("patchcourt.upgrade_run.run_upgrade") as upgrade:
                self.assertEqual(main(["boundary-run", *args]), 2)
                self.assertEqual(main(["upgrade-run", temp, "--from-version", "1.4.3", "--to-version", "1.5.0",
                                       "--environment-dir", str(root / "envs"), "--prepare", *args]), 2)
            boundary.assert_not_called(); upgrade.assert_not_called()
            self.assertFalse((root / "report").exists())

    def test_equal_lost_text_is_not_healthy(self):
        original = [{"role": "user", "content": "important context"}]
        damaged = [{"role": "user", "content": ""}]
        self.assertEqual(check_trace_pair(damaged, damaged)["status"], "PASS")
        checked = check_trace_pair(damaged, damaged, original_input=original)
        self.assertEqual(checked["status"], "NEEDS_REVIEW")
        self.assertEqual(checked["contracts"]["baseline"]["status"], "FAIL")
        self.assertEqual(checked["contracts"]["difference"]["status"], "PASS")

    def test_regression_and_recovery_remain_distinct(self):
        original = tool_conversation()
        damaged = [{"role": "assistant", "content": ""}, *original[1:]]
        self.assertEqual(check_trace_pair(original, damaged, original_input=original)["status"], "FAIL")
        recovered = check_trace_pair(damaged, original, original_input=original)
        self.assertEqual(recovered["status"], "NEEDS_REVIEW")
        self.assertEqual(recovered["direction"], "candidate_restores_contract")
        self.assertEqual(recovered["contracts"]["candidate"]["status"], "PASS")

    def test_unsupported_original_never_silently_disables_check(self):
        text = [{"role": "user", "content": "hello"}]
        for original in (None, {}, [{"role": "user", "content": [{"type": "audio"}]}]):
            with self.subTest(original=original):
                self.assertEqual(check_trace_pair(text, text, original_input=original)["status"], "INCONCLUSIVE")

    def test_cli_exports_contracts_and_original_input(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); original = tool_conversation()
            write_json(root / "input.json", original)
            write_json(root / "a.json", original)
            write_json(root / "b.json", original)
            output = root / "report"
            self.assertEqual(main(["check", str(root/"a.json"), str(root/"b.json"), "--input", str(root/"input.json"), "--output", str(output)]), 0)
            report = read_json(output / "report.json")
            self.assertEqual(report["input"], original)
            self.assertEqual(report["cases"][0]["contracts"]["candidate"]["status"], "PASS")
            self.assertEqual(main(["verify", str(output)]), 0)

    def test_verify_requires_structured_records_and_nonempty_matching_id(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for report, manifest in (({}, {"report_sha256": digest({})}),
                                     ({"run_id": " "}, {"run_id": " ", "report_sha256": digest({"run_id": " "})}),
                                     ([], []), ({"run_id": "a"}, []),
                                     ({"run_id": "a"}, {"run_id": "b", "report_sha256": digest({"run_id": "a"})})):
                with self.subTest(report=report, manifest=manifest):
                    write_json(root / "report.json", report); write_json(root / "manifest.json", manifest)
                    self.assertEqual(main(["verify", str(root)]), 1)


if __name__ == "__main__":
    unittest.main()
