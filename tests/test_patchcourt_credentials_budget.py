import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch

from patchcourt.budget import RequestBudget
from patchcourt.credentials import load_local_credentials


class LocalCredentialsTests(unittest.TestCase):
    def test_only_explicit_credential_values_are_loaded_without_shell_expansion(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}, clear=True):
            path = Path(folder) / "local.env"
            path.write_text('DEEPSEEK_API_KEY="dummy-$(must-not-run)"\nTAVILY_API_KEY=dummy-search\n', encoding="utf-8")
            metadata = load_local_credentials(path)
            self.assertEqual(metadata["loaded"], ["DEEPSEEK_API_KEY", "TAVILY_API_KEY"])
            self.assertNotIn("dummy", json.dumps(metadata))
            self.assertEqual(os.environ["DEEPSEEK_API_KEY"], "dummy-$(must-not-run)")

    def test_bad_declarations_do_not_partially_modify_environment(self):
        for body in ("DEEPSEEK_API_KEY=dummy\nPYTHONPATH=untrusted", "DEEPSEEK_API_KEY=first\nDEEPSEEK_API_KEY=second", "DEEPSEEK_API_KEY=\"unterminated"):
            with self.subTest(body=body), tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}, clear=True):
                path = Path(folder) / "local.env"; path.write_text(body, encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_local_credentials(path)
                self.assertNotIn("DEEPSEEK_API_KEY", os.environ)

    def test_existing_process_key_is_not_silently_replaced(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"DEEPSEEK_API_KEY": "existing-dummy"}, clear=True):
            path = Path(folder) / "local.env"; path.write_text("DEEPSEEK_API_KEY=new-dummy", encoding="utf-8")
            self.assertEqual(load_local_credentials(path)["loaded"], [])
            self.assertEqual(os.environ["DEEPSEEK_API_KEY"], "existing-dummy")


class RequestBudgetTests(unittest.TestCase):
    def test_concurrent_context_cannot_replace_or_restore_another_threads_budget(self):
        from patchcourt import providers
        with tempfile.TemporaryDirectory() as folder:
            first = RequestBudget(Path(folder) / "first.json")
            second = RequestBudget(Path(folder) / "second.json")
            def enter_other_context():
                try:
                    with second.applied():
                        return "unexpectedly entered"
                except ValueError as exc:
                    return str(exc)
            with patch.object(providers, "request", return_value={}) as transport:
                with first.applied():
                    active = providers.request
                    with ThreadPoolExecutor(max_workers=1) as pool:
                        message = pool.submit(enter_other_context).result(timeout=5)
                    self.assertIn("budget context is active", message)
                    self.assertIs(providers.request, active)
                    providers.request("deepseek", {"model": "deepseek-flash", "max_tokens": 100})
                self.assertIs(providers.request, transport)
                self.assertEqual(transport.call_count, 1)
            self.assertEqual(len(first.state["reservations"]), 1)
            self.assertEqual(second.state["reservations"], [])

    def test_two_instances_cannot_spend_the_same_last_reservation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "budget.json"
            first = RequestBudget(path, model_calls=1)
            second = RequestBudget(path, model_calls=1)
            first.reserve("deepseek", {"model": "deepseek-flash", "max_tokens": 100})
            with self.assertRaisesRegex(ValueError, "budget exhausted"):
                second.reserve("deepseek", {"model": "deepseek-flash", "max_tokens": 100})
            self.assertEqual(len(json.loads(path.read_text(encoding="utf-8"))["reservations"]), 1)

    def test_existing_instance_observes_reservation_from_another_process(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "budget.json"
            budget = RequestBudget(path, model_calls=1)
            program = ("from patchcourt.budget import RequestBudget; import sys; "
                       "RequestBudget(sys.argv[1], model_calls=1).reserve('deepseek', "
                       "{'model':'deepseek-flash','max_tokens':100})")
            result = subprocess.run([sys.executable, "-c", program, str(path)],
                                    cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            with self.assertRaisesRegex(ValueError, "budget exhausted"):
                budget.reserve("deepseek", {"model": "deepseek-flash", "max_tokens": 100})

    def test_os_lock_prevents_another_runner_from_reading_a_stale_ledger(self):
        from patchcourt.budget import _ledger_lock
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "budget.json"
            RequestBudget(path)
            with _ledger_lock(path):
                result = subprocess.run([sys.executable, "-c",
                                         "from patchcourt.budget import RequestBudget; import sys; RequestBudget(sys.argv[1])",
                                         str(path)], cwd=Path(__file__).resolve().parents[1],
                                        capture_output=True, text=True, timeout=15)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("already in use", result.stderr)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["reservations"], [])

    def test_failed_ledger_write_stops_transport_and_preserves_valid_previous_ledger(self):
        from patchcourt import providers
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "budget.json"
            budget = RequestBudget(path, model_calls=1)
            prior = path.read_bytes()
            with patch.object(providers, "request") as request, patch("patchcourt.budget.write_json", side_effect=OSError("disk full")):
                with budget.applied():
                    with self.assertRaisesRegex(OSError, "disk full"):
                        providers.request("deepseek", {"model": "deepseek-flash", "max_tokens": 100})
            request.assert_not_called()
            self.assertEqual(path.read_bytes(), prior)
            self.assertEqual(list(path.parent.glob(".budget-*.tmp")), [])

    def test_reservation_survives_failed_transport_and_process_restart(self):
        from patchcourt import providers
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "budget.json"
            with patch.object(providers, "request", side_effect=ValueError("transport failed")) as request:
                with RequestBudget(path, model_calls=1).applied():
                    with self.assertRaisesRegex(ValueError, "transport failed"):
                        providers.request("deepseek", {"model": "deepseek-flash", "max_tokens": 100})
                with RequestBudget(path, model_calls=1).applied():
                    with self.assertRaisesRegex(ValueError, "budget exhausted"):
                        providers.request("deepseek", {"model": "deepseek-flash", "max_tokens": 100})
                self.assertEqual(request.call_count, 1)

    def test_searches_and_models_have_independent_hard_limits(self):
        with tempfile.TemporaryDirectory() as folder:
            budget = RequestBudget(Path(folder) / "budget.json", model_calls=1, searches=1)
            budget.reserve("tavily", {"query": "official docs", "search_depth": "basic"})
            budget.reserve("deepseek", {"model": "deepseek-flash", "max_tokens": 100})
            with self.assertRaisesRegex(ValueError, "budget exhausted"):
                budget.reserve("tavily", {"query": "more", "search_depth": "basic"})
            with self.assertRaisesRegex(ValueError, "basic search only"):
                budget.reserve("tavily", {"query": "advanced", "search_depth": "advanced"})


if __name__ == "__main__":
    unittest.main()
