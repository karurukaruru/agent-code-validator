"""Runner error accounting tests use synthetic credentials and no transport."""
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from patchcourt import providers
from patchcourt.budget import RequestBudget
from scripts.run_release_experiments import main


class ExperimentRunnerTests(unittest.TestCase):
    def arguments(self, root, mode="reason"):
        credential = root / "test.env"
        credential.write_text("DEEPSEEK_API_KEY=synthetic-runner-secret\n", encoding="utf-8")
        return [mode, "--provider", "deepseek", "--env-file", str(credential),
                "--budget", str(root / "budget.json"), "--output", str(root / "run")]

    def test_budget_exhaustion_preserves_an_explicit_failure_and_never_calls_transport(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}, clear=True), patch.object(
                providers, "_transport") as transport, patch("sys.stdout", new_callable=io.StringIO) as output:
            root = Path(folder)
            budget = RequestBudget(root / "budget.json")
            for _ in range(30):
                budget.reserve("deepseek", {"model": "deepseek-flash", "max_tokens": 100})
            status = main(self.arguments(root))
            record = json.loads((root / "run" / "reasoning.json").read_text(encoding="utf-8"))
            self.assertEqual(status, 2)
            self.assertEqual(record["status"], "FAIL")
            self.assertIn("budget exhausted", record["inference"]["reason"])
            self.assertNotIn("synthetic-runner-secret", output.getvalue())
            self.assertNotIn("synthetic-runner-secret", json.dumps(record))
            transport.assert_not_called()

    def test_old_output_is_not_modified_when_runner_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as folder, patch("sys.stdout", new_callable=io.StringIO), patch.object(
                providers, "_transport") as transport:
            root = Path(folder)
            run = root / "run"
            run.mkdir()
            prior = run / "prior.json"
            prior.write_text('{"status":"FAIL"}', encoding="utf-8")
            self.assertEqual(main(self.arguments(root)), 2)
            self.assertEqual(list(run.iterdir()), [prior])
            self.assertEqual(prior.read_text(encoding="utf-8"), '{"status":"FAIL"}')
            self.assertFalse((root / "budget.json").exists())
            transport.assert_not_called()

    def test_sanitized_child_error_is_retained_without_a_traceback_or_secret(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}, clear=True), patch(
                "scripts.run_release_experiments.execute", side_effect=ValueError("synthetic-runner-secret")), patch(
                "sys.stdout", new_callable=io.StringIO) as output:
            root = Path(folder)
            self.assertEqual(main(self.arguments(root)), 2)
            saved = (root / "run" / "experiment-failure.json").read_text(encoding="utf-8")
            self.assertIn("[REDACTED]", saved)
            self.assertNotIn("synthetic-runner-secret", saved + output.getvalue())


if __name__ == "__main__":
    unittest.main()
