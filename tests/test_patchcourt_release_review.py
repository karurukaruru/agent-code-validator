"""Independent release checks. All provider responses are mocked, never live."""
import copy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from patchcourt import providers
from patchcourt.cli import main, serve_static
from patchcourt.evidence import digest, read_json, strict_json
from patchcourt.lab import _check, _ablation
from patchcourt.reasoning import run_reasoning
from patchcourt.runner import acceptance_gates, export_report, make_report


ROOT = Path(__file__).resolve().parents[1]
LAB_MODEL = "nvidia/Nemotron-synthetic-test"


def proposal(case):
    return {"hypothesis": "Held-out release check", "test_cases": [case], "repair_proposals": [], "citations": []}


def mocked_reasoning(value):
    response = {"status": "PASS", "provenance": "mocked release review", "response": {"model": "mock/Nemotron", "choices": [
        {"finish_reason": "stop", "message": {"role": "assistant", "content": json.dumps(value)}}]}}
    with patch.dict(os.environ, {"NEBIUS_API_KEY": "dummy-release-key"}, clear=True), patch.object(providers, "request", return_value=response):
        return run_reasoning("reviewed example source", {}, model="mock/Nemotron")


def stream_record():
    return {"status": "PASS", "parameters": {"model": LAB_MODEL}, "response": {"done": True, "events": [
        {"model": LAB_MODEL, "choices": [{"index": 0, "delta": {"role": "assistant", "content": '{"ok":true}'}, "finish_reason": "stop"}]}
    ]}}


class ReleaseReasoningTests(unittest.TestCase):
    def test_model_wrong_expectation_does_not_receive_pass(self):
        case = {"name": "Wrong expectation", "baseline": [{"role": "user", "content": "preserve me"}],
                "candidate": [{"role": "user", "content": ""}], "expected_status": "PASS"}
        result = mocked_reasoning(proposal(case))
        self.assertFalse(result["case_results"][0]["expectation_matched"])
        self.assertNotEqual(result["status"], "PASS")

    def test_only_unknown_contracts_remain_inconclusive(self):
        unknown = [{"role": "user", "content": [{"type": "new_audio", "data": "opaque"}]}]
        case = {"name": "Unmodeled schema", "baseline": unknown, "candidate": unknown, "expected_status": "INCONCLUSIVE"}
        result = mocked_reasoning(proposal(case))
        self.assertEqual(result["case_results"][0]["verdict"]["status"], "INCONCLUSIVE")
        self.assertEqual(result["status"], "INCONCLUSIVE")

    def test_malformed_model_choice_does_not_escape_validation(self):
        with patch.dict(os.environ, {"NEBIUS_API_KEY": "dummy-release-key"}, clear=True), patch.object(providers, "request", return_value={
            "status": "PASS", "provenance": "mocked", "response": {"choices": [None]}}):
            result = run_reasoning("source", {}, model="mock/Nemotron")
        self.assertEqual(result["status"], "FAIL")
        self.assertFalse(result["executed_repairs"])

    def test_ablation_does_not_downgrade_failed_arm_to_uncertainty(self):
        runs = [{"status": "PASS", "case_results": []}, {"status": "FAIL", "reason": "Malformed provider proposal"}]
        with patch("patchcourt.lab.run_reasoning", side_effect=runs):
            result = _ablation("mock/Nemotron")
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["with_tavily"]["status"], "FAIL")


class ReleaseProtocolTests(unittest.TestCase):
    def test_duplicate_json_output_key_does_not_pass_schema(self):
        record = {"status": "PASS", "parameters": {"model": LAB_MODEL}, "response": {"model": LAB_MODEL, "choices": [{"finish_reason": "stop", "message": {
            "role": "assistant", "content": '{"ok":false,"ok":true}'}}]}}
        self.assertNotEqual(_check("structured_json", record)[0], "PASS")

    def test_stream_nonassistant_role_cannot_pass(self):
        record = stream_record()
        record["response"]["events"][0]["choices"][0]["delta"]["role"] = "user"
        self.assertNotEqual(_check("streaming", record)[0], "PASS")

    def test_stream_extra_choice_cannot_be_ignored(self):
        record = stream_record()
        record["response"]["events"][0]["choices"].append({"index": 1, "delta": {"content": "truncated"}, "finish_reason": "length"})
        self.assertNotEqual(_check("streaming", record)[0], "PASS")

    def test_stream_unknown_delta_semantics_cannot_pass(self):
        record = stream_record()
        record["response"]["events"][0]["choices"][0]["delta"]["refusal"] = "I cannot perform this"
        self.assertNotEqual(_check("streaming", record)[0], "PASS")

    def test_repeated_stream_finish_cannot_pass(self):
        record = stream_record()
        record["response"]["events"].append({"model": LAB_MODEL, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]})
        self.assertNotEqual(_check("streaming", record)[0], "PASS")

    def test_valid_stream_with_usage_only_tail_passes(self):
        record = stream_record()
        record["response"]["events"].append({"model": LAB_MODEL, "choices": [], "usage": {"completion_tokens": 5}})
        self.assertEqual(_check("streaming", record)[0], "PASS")

    def test_false_boolean_value_rejected_in_all_probe_forms(self):
        record = stream_record()
        record["response"]["events"][0]["choices"][0]["delta"]["content"] = '{"ok":false}'
        self.assertEqual(_check("streaming", record)[0], "FAIL")
        plain = {"status": "PASS", "parameters": {"model": LAB_MODEL}, "response": {"model": LAB_MODEL, "choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": '{"ok":false}'}}]}}
        self.assertEqual(_check("structured_json", plain)[0], "FAIL")


class ReleaseProviderTests(unittest.TestCase):
    def test_duplicate_provider_response_keys_fail(self):
        with patch.dict(os.environ, {"NEBIUS_API_KEY": "dummy-release-key"}, clear=True), patch.object(providers, "_transport", return_value=(200, {}, '{"data":null,"data":[]}')):
            self.assertEqual(providers.discover_models()["status"], "FAIL")

    def test_provider_numeric_overflow_is_recorded_as_failure(self):
        raw = '{"data":[],"usage":{"total_tokens":1e999}}'
        with patch.dict(os.environ, {"NEBIUS_API_KEY": "dummy-release-key"}, clear=True), patch.object(providers, "_transport", return_value=(200, {}, raw)):
            record = providers.discover_models()
        self.assertEqual(record["status"], "FAIL")
        json.dumps(record, allow_nan=False)

    def test_malformed_provider_events_do_not_raise_uncaught_exception(self):
        with patch.dict(os.environ, {"NEBIUS_API_KEY": "dummy-release-key"}, clear=True), patch.object(providers, "_transport", return_value=(200, {}, '{"events":[1]}')):
            record = providers.request("nebius", {"max_tokens": 10})
        self.assertEqual(record["status"], "FAIL")

    def test_duplicate_sse_delta_keys_rejected(self):
        raw = 'data: {"choices":[{"index":0,"delta":{"content":"wrong","content":"right"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n'
        with self.assertRaises(ValueError):
            providers.parse_stream(raw)

    def test_empty_inference_payload_cannot_bypass_token_budget(self):
        for payload in (None, {}):
            with self.subTest(payload=payload), patch.dict(os.environ, {"NEBIUS_API_KEY": "dummy-release-key"}, clear=True), patch.object(providers, "_transport", return_value=(200, {}, '{}')) as transport:
                with self.assertRaises(ValueError):
                    providers.request("nebius", payload)
                transport.assert_not_called()

    def test_nonobject_inference_payload_rejected_before_transport(self):
        with patch.dict(os.environ, {"NEBIUS_API_KEY": "dummy-release-key"}, clear=True), patch.object(providers, "_transport") as transport:
            with self.assertRaises(ValueError):
                providers.request("nebius", ["bad-payload"])
            transport.assert_not_called()

    def test_provider_echoed_key_in_dictionary_key_is_redacted(self):
        dummy_key = "dummy-release-secret-ABCDEF"
        raw = json.dumps({"data": [], "debug": {dummy_key: "echoed key"}})
        with patch.dict(os.environ, {"NEBIUS_API_KEY": dummy_key}, clear=True), patch.object(providers, "_transport", return_value=(200, {}, raw)):
            record = providers.discover_models()
        self.assertNotIn(dummy_key, json.dumps(record))

    def test_out_of_range_max_tokens_never_reaches_transport(self):
        with patch.dict(os.environ, {"NEBIUS_API_KEY": "dummy-release-key"}, clear=True), patch.object(providers, "_transport") as transport:
            for value in (True, 0, 2049, "100"):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    providers.request("nebius", {"max_tokens": value})
            transport.assert_not_called()

    def test_search_rejects_credentials_and_subdomain_suffix_spoofing(self):
        urls = ["https://user:password@docs.python.org/3", "https://docs.python.org.evil.invalid/", "http://docs.python.org/3"]
        raw = json.dumps({"results": [{"url": url, "content": "untrusted"} for url in urls]})
        with patch.dict(os.environ, {"TAVILY_API_KEY": "dummy-release-key"}, clear=True), patch.object(providers, "_transport", return_value=(200, {}, raw)):
            record = providers.search_docs()
        self.assertEqual(record["status"], "INCONCLUSIVE")
        self.assertEqual(record["documents"], [])


class ReleaseEvidenceTests(unittest.TestCase):
    def test_strict_json_depth_limit(self):
        raw = "[" * 70 + "0" + "]" * 70
        with self.assertRaises(ValueError):
            strict_json(raw)

    def test_strict_json_numeric_overflow_rejected(self):
        with self.assertRaises(ValueError):
            strict_json('{"amount":1e999}')

    def test_no_repairs_or_controls_cannot_satisfy_acceptance(self):
        report = make_report([])
        report["knowledge"] = {"reused": False}
        gates = {gate["id"]: gate for gate in acceptance_gates(report)}
        self.assertNotEqual(gates[5]["status"], "PASS")
        self.assertNotEqual(gates[6]["status"], "PASS")

    def test_manifest_matches_sanitized_persisted_report(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder, patch.dict(os.environ, {"RELEASE_TEST_SECRET": "release-dummy-secret"}):
            report = make_report([{"id": "case", "status": "FAIL", "provenance": "release-dummy-secret"}])
            export_report(report, folder)
            saved = read_json(Path(folder) / "report.json")
            manifest = read_json(Path(folder) / "manifest.json")
            self.assertEqual(manifest["report_sha256"], digest(saved))
            self.assertNotIn("release-dummy-secret", (Path(folder) / "report.md").read_text(encoding="utf-8"))

    def test_malformed_cli_trace_returns_uncertain_exit(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            path = Path(folder) / "broken.json"
            path.write_text("{incomplete", encoding="utf-8")
            with patch("sys.stderr", new_callable=io.StringIO):
                self.assertEqual(main(["check", str(path), str(path), "--output", str(Path(folder) / "out")]), 2)


class FakeConnection:
    def __init__(self, request):
        self.request = request
        self.output = bytearray()

    def makefile(self, mode, *args):
        return io.BytesIO(self.request)

    def sendall(self, value):
        self.output.extend(value)


def static_request(folder, path, method="GET", host="127.0.0.1:8765"):
    connection = FakeConnection(f"{method} {path} HTTP/1.0\r\nHost: {host}\r\n\r\n".encode("ascii"))

    class FakeServer:
        def __init__(self, address, handler):
            self.handler = handler
            self.server_address = address
            self.server_name, self.server_port = address

        def serve_forever(self):
            self.handler(connection, ("127.0.0.1", 60000), self)

        def server_close(self):
            pass

    with patch("http.server.ThreadingHTTPServer", FakeServer), patch("sys.stderr", new_callable=io.StringIO), patch("sys.stdout", new_callable=io.StringIO):
        serve_static(folder, 8765)
    return bytes(connection.output)


class ReleaseStaticServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        (self.folder / "index.html").write_text("<!doctype html><p>review</p>", encoding="utf-8")
        (self.folder / "report.json").write_text('{"dummy":"visible"}', encoding="utf-8")
        (self.folder / "secret.txt").write_text("must-not-serve", encoding="utf-8")

    def test_explicit_report_and_security_headers(self):
        raw = static_request(self.folder, "/report.json")
        self.assertIn(b"200 OK", raw)
        self.assertIn(b"X-Content-Type-Options: nosniff", raw)
        self.assertIn(b"Cache-Control: no-store", raw)

    def test_traversal_encoded_traversal_and_unlisted_file_rejected(self):
        for path in ("/secret.txt", "/../secret.txt", "/%2e%2e/secret.txt", "/knowledge/record.json"):
            with self.subTest(path=path):
                raw = static_request(self.folder, path)
                self.assertIn(b"404", raw.split(b"\r\n", 1)[0])
                self.assertNotIn(b"must-not-serve", raw)

    def test_post_has_no_mutating_endpoint(self):
        self.assertIn(b"501", static_request(self.folder, "/report.json", method="POST").split(b"\r\n", 1)[0])

    def test_untrusted_host_cannot_read_local_evidence(self):
        raw = static_request(self.folder, "/report.json", host="attacker.example:8765")
        self.assertNotIn(b"200 OK", raw.split(b"\r\n", 1)[0])
        self.assertNotIn(b'"dummy":"visible"', raw)


if __name__ == "__main__":
    unittest.main()
