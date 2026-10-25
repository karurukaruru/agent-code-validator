"""MOCKED provider transport tests. No credentials, network, or live claims."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from patchcourt import providers
from patchcourt.lab import _check, run_lab
from patchcourt.reasoning import run_reasoning, validate_proposal


class MockedProviderTests(unittest.TestCase):
    def test_missing_credentials_never_calls_transport(self):
        with patch.dict("os.environ", {}, clear=True), patch.object(providers, "_transport") as transport:
            self.assertEqual(providers.discover_models()["status"], "BLOCKED")
            self.assertEqual(providers.search_docs()["status"], "BLOCKED")
            self.assertEqual(run_reasoning("source", {}, True)["status"], "BLOCKED")
            transport.assert_not_called()

    def test_mocked_http_failure_and_key_redaction_are_preserved(self):
        secret = "test-secret-only"
        with patch.dict("os.environ", {"NEBIUS_API_KEY": secret}, clear=True), patch.object(
            providers, "_transport", return_value=(429, {}, json.dumps({"error": "limit " + secret}))):
            record = providers.discover_models()
        self.assertEqual(record["status"], "FAIL")
        self.assertEqual(record["http_status"], 429)
        self.assertIn("limit", record["raw_response"])
        self.assertNotIn(secret, json.dumps(record))
        self.assertIsNone(record["cost_usd"])

    def test_mocked_model_discovery_does_not_invent_model(self):
        with patch.dict("os.environ", {"NEBIUS_API_KEY": "mock-key"}, clear=True), patch.object(
            providers, "_transport", return_value=(200, {}, '{"data":[{"id":"nvidia/Nemotron-test"},{"id":"another"}]}')):
            record = providers.discover_models()
        self.assertEqual(record["nemotron_models"], ["nvidia/Nemotron-test"])

    def test_mocked_malformed_success_is_failure(self):
        with patch.dict("os.environ", {"NEBIUS_API_KEY": "mock-key"}, clear=True), patch.object(
            providers, "_transport", return_value=(200, {}, "not json")):
            self.assertEqual(providers.discover_models()["status"], "FAIL")

    def test_redirect_policy_and_origin_guard(self):
        self.assertIsNone(providers.NoRedirect().redirect_request(None, None, 302, "", {}, "https://evil.invalid"))
        with self.assertRaises(ValueError):
            providers._transport("https://evil.invalid", "mock-key", None)

    def test_mocked_tavily_filters_untrusted_hosts(self):
        raw = json.dumps({"results": [
            {"url": "https://docs.python.org.evil.invalid/a", "content": "bad"},
            {"url": "https://docs.python.org/3/", "content": "Python docs"}]})
        with patch.dict("os.environ", {"TAVILY_API_KEY": "mock-key"}, clear=True), patch.object(
            providers, "_transport", return_value=(200, {}, raw)) as transport:
            record = providers.search_docs()
        self.assertEqual([d["url"] for d in record["documents"]], ["https://docs.python.org/3/"])
        self.assertNotIn("source", transport.call_args.args[2])

    def test_stream_reassembly_and_truncation(self):
        events = [
            {"choices": [{"index": 0, "delta": {"content": '{"ok":'}, "finish_reason": None}]},
            {"choices": [{"index": 0, "delta": {"content": "true}"}, "finish_reason": "stop"}]},
            {"choices": [], "usage": {"completion_tokens": 5}}]
        raw = "".join("data: " + json.dumps(e) + "\r\n\r\n" for e in events) + "data: [DONE]\r\n\r\n"
        body = providers.parse_stream(raw)
        self.assertEqual(_check("streaming", {"status": "PASS", "response": body})[0], "PASS")
        with self.assertRaises(ValueError):
            providers.parse_stream(raw.replace("data: [DONE]", ""))
        with self.assertRaises(ValueError):
            providers.parse_stream('data: {"error":"failed"}\n\ndata: [DONE]\n\n')

    def test_expected_model_error_does_not_accept_auth_failure(self):
        record = {"status": "FAIL", "http_status": 401, "raw_response": '{"error":"model unauthorized"}'}
        self.assertEqual(_check("invalid_model_error", record)[0], "FAIL")
        record["http_status"] = 404
        record["raw_response"] = '{"error":{"message":"model does not exist"}}'
        self.assertEqual(_check("invalid_model_error", record)[0], "PASS")

    def test_schema_does_not_accept_integer_instead_of_boolean(self):
        record = {"status": "PASS", "response": {"choices": [{"finish_reason": "stop", "message": {
            "role": "assistant", "content": '{"ok":1}'}}]}}
        self.assertEqual(_check("structured_json", record)[0], "FAIL")

    def test_malformed_choice_is_preserved_as_contract_failure(self):
        record = {"status": "PASS", "response": {"choices": [7]}}
        self.assertEqual(_check("structured_json", record)[0], "FAIL")


class MockedLabTests(unittest.TestCase):
    def test_blocked_run_preserves_all_planned_trials(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as root, patch.dict("os.environ", {}, clear=True), patch.object(providers, "_transport") as transport:
            report = run_lab(root, trials=2)
            self.assertEqual(report["status"], "BLOCKED")
            self.assertEqual(len(list((Path(root) / "trials").glob("*.json"))), 8)
            self.assertEqual(report["summary"]["streaming"]["executed"], 0)
            self.assertIsNone(report["summary"]["streaming"]["pass_rate"])
            self.assertEqual(report["ablation"]["status"], "BLOCKED")
            transport.assert_not_called()
            with self.assertRaises(ValueError):
                run_lab(root)

    def test_mocked_failed_trials_are_not_dropped(self):
        discovery = {"status": "PASS", "models": ["mock/Nemotron"], "nemotron_models": ["mock/Nemotron"], "provenance": "mocked transport"}
        failure = {"status": "FAIL", "http_status": 429, "reason": "mocked rate limit", "latency_ms": 7,
                   "provenance": "mocked transport", "raw_response": '{"error":"rate limit"}'}
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as root, patch.object(providers, "discover_models", return_value=discovery), patch.object(
            providers, "request", return_value=failure), patch("patchcourt.lab._ablation", return_value={"status": "BLOCKED", "reason": "mocked"}):
            report = run_lab(root, trials=2)
            self.assertEqual(report["status"], "FAIL")
            self.assertEqual(len(report["trials"]), 8)
            self.assertEqual(report["summary"]["tool_call"]["failed"], 2)
            self.assertEqual(report["summary"]["tool_call"]["pass_rate"], 0)

    def test_declarative_schema_rejects_code_and_fabricated_citations(self):
        proposal = {"hypothesis": "A dropped call breaks linkage", "test_cases": [], "repair_proposals": [], "citations": []}
        self.assertEqual(validate_proposal(proposal), proposal)
        with self.assertRaises(ValueError):
            validate_proposal({**proposal, "python": "import os"})
        with self.assertRaises(ValueError):
            validate_proposal({**proposal, "citations": ["https://invented.invalid"]})
        with self.assertRaises(ValueError):
            validate_proposal({**proposal, "test_cases": [{"name": "x", "baseline": [], "candidate": [], "expected_status": "PASS", "code": "exec(...)"}]})

    def test_mocked_reasoning_evaluates_data_without_executing_repairs(self):
        proposal = {"hypothesis": "Text loss", "test_cases": [{"name": "text loss",
                    "baseline": [{"role": "user", "content": "hello"}], "candidate": [{"role": "user", "content": ""}], "expected_status": "FAIL"}],
                    "repair_proposals": ["Preserve content during conversion"], "citations": []}
        response = {"status": "PASS", "provenance": "mocked transport", "response": {"choices": [
            {"finish_reason": "stop", "message": {"content": json.dumps(proposal)}}]}}
        with patch.dict("os.environ", {"NEBIUS_API_KEY": "mock-key"}, clear=True), patch.object(providers, "request", return_value=response):
            report = run_reasoning("adapter", {}, model="mock/Nemotron")
        self.assertEqual(report["status"], "PASS")
        self.assertTrue(report["case_results"][0]["expectation_matched"])
        self.assertFalse(report["executed_repairs"])
        self.assertEqual(report["provenance"], "mocked transport")


if __name__ == "__main__":
    unittest.main()
