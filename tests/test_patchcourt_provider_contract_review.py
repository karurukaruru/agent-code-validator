"""Independent malformed-response checks; all transports are synthetic."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from patchcourt import providers
from patchcourt.budget import RequestBudget
from patchcourt.evidence import read_json
from patchcourt.live_workflow import run_live_workflow
from patchcourt.reasoning import run_reasoning
from tests.test_patchcourt_provider_workflows import NEMOTRON, model_replies


def valid_replies():
    values = model_replies(providers.DEEPSEEK_MODEL)
    for value in values:
        choice = value["response"]["choices"][0]
        choice["message"].setdefault("role", "assistant")
        choice["finish_reason"] = "tool_calls" if choice["message"].get("tool_calls") else "stop"
    return values


class ProviderContractReviewTests(unittest.TestCase):
    def test_workflow_rejects_role_refusal_and_inconsistent_tool_finish(self):
        for mutation in ("role", "refusal", "tool-stop", "final-tool-finish"):
            values = valid_replies()
            if mutation == "role": values[-1]["response"]["choices"][0]["message"]["role"] = "user"
            if mutation == "refusal": values[-1]["response"]["choices"][0]["message"]["refusal"] = "refused"
            if mutation == "tool-stop": values[1]["response"]["choices"][0]["finish_reason"] = "stop"
            if mutation == "final-tool-finish": values[-1]["response"]["choices"][0]["finish_reason"] = "tool_calls"
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as folder, patch.object(
                providers, "request", side_effect=values):
                root = Path(folder) / "run"
                result = run_live_workflow(root, provider="deepseek")
                self.assertEqual(result["status"], "FAIL")
                self.assertTrue((root / "manifest.json").exists())

    def test_malformed_usage_never_prevents_final_report_and_manifest(self):
        for usage in ("not-an-object", {"total_tokens": None}, {"total_tokens": True}):
            values = valid_replies()
            values[0]["usage"] = usage
            with self.subTest(usage=usage), tempfile.TemporaryDirectory() as folder, patch.object(
                providers, "request", side_effect=values):
                root = Path(folder) / "run"
                result = run_live_workflow(root, provider="deepseek")
                self.assertEqual(result["status"], "PASS")
                self.assertEqual(result["total_reported_tokens"], 20)
                self.assertEqual(result["requests_missing_token_usage"], 1)
                self.assertTrue((root / "manifest.json").exists())

    def test_budget_exhaustion_is_a_preserved_failed_attempt_without_retry(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(providers, "request", side_effect=valid_replies()) as transport:
            root = Path(folder) / "run"
            with RequestBudget(Path(folder) / "budget.json", model_calls=1).applied():
                result = run_live_workflow(root, provider="deepseek")
            self.assertEqual(result["status"], "FAIL")
            self.assertEqual(transport.call_count, 1)
            self.assertEqual(len(result["requests"]), 2)
            self.assertEqual(result["requests"][-1]["status"], "FAIL")
            failed = read_json(root / result["requests"][-1]["evidence_file"])
            self.assertIn("budget exhausted", failed["reason"])

    def test_nebius_schema_rejection_is_retained_without_fallback_or_retry(self):
        failed = {"status": "FAIL", "provenance": "synthetic HTTP attempt", "http_status": 400,
            "reason": "Provider HTTP error", "raw_response": '{"error":"json_schema unsupported"}'}
        with patch.dict("os.environ", {"NEBIUS_API_KEY": "synthetic-key"}, clear=True), patch.object(
            providers, "request", return_value=failed) as request:
            result = run_reasoning("adapter source", {}, provider="nebius", model=NEMOTRON)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["inference"], failed)
        self.assertEqual(request.call_count, 1)
        self.assertEqual(request.call_args.args[1]["response_format"]["type"], "json_schema")

    def test_provider_reasoning_echo_cannot_mutate_the_verified_boundary_evidence(self):
        from patchcourt.semantic import compare_messages
        values, sent = valid_replies(), []
        values[1]["response"]["choices"][0]["message"]["reasoning_content"] = "synthetic provider-only metadata"
        def request(provider, payload):
            sent.append(deepcopy(payload))
            return values[len(sent) - 1]
        with tempfile.TemporaryDirectory() as folder, patch.object(providers, "request", side_effect=request):
            root = Path(folder) / "run"
            result = run_live_workflow(root, provider="deepseek")
            self.assertEqual(result["status"], "PASS")
            boundary = result["live_boundaries"][0]
            self.assertEqual(compare_messages(boundary["input"], boundary["repaired"])["status"], boundary["after"]["status"])
            self.assertNotIn("reasoning_content", boundary["repaired"][0])
            self.assertEqual(sent[-1]["messages"][-3]["reasoning_content"], "synthetic provider-only metadata")
            self.assertEqual(read_json(root / "task-turn-1.json")["response"]["choices"][0]["message"]["reasoning_content"],
                             "synthetic provider-only metadata")

    def test_reasoning_does_not_accept_a_proposal_with_tool_calls_or_wrong_role(self):
        proposal = {"hypothesis": "synthetic", "test_cases": [{"name": "control", "baseline": [],
            "candidate": [], "expected_status": "PASS"}], "repair_proposals": [], "citations": []}
        for field in ({"role": "user"}, {"tool_calls": [{"id": "unexpected"}]}, {"refusal": "refused"}):
            response = {"status": "PASS", "provenance": "synthetic", "response": {
                "model": providers.DEEPSEEK_MODEL, "choices": [{"finish_reason": "stop", "message": {
                    "role": "assistant", "content": json.dumps(proposal), **deepcopy(field)}}]}}
            with self.subTest(field=field), patch.dict("os.environ", {"DEEPSEEK_API_KEY": "synthetic-key"}, clear=True), patch.object(
                providers, "request", return_value=response):
                result = run_reasoning("source", {}, provider="deepseek")
            self.assertEqual(result["status"], "FAIL")

    def test_reasoning_wrapper_failure_returns_record_instead_of_losing_attempt(self):
        with patch.dict("os.environ", {"DEEPSEEK_API_KEY": "synthetic-key"}, clear=True), patch.object(
            providers, "request", side_effect=ValueError("Experiment model_calls budget exhausted")) as request:
            result = run_reasoning("source", {}, provider="deepseek")
        self.assertEqual(request.call_count, 1)
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("budget exhausted", result["inference"]["reason"])


if __name__ == "__main__":
    unittest.main()
