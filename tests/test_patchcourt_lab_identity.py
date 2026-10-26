"""Nebius lab identity/protocol regressions with synthetic provider responses."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from patchcourt import providers
from patchcourt.evidence import read_json
from patchcourt.lab import PROBES, _check, _payload, run_lab

MODEL = "nvidia/Nemotron-synthetic-test"
INVALID = "patchcourt-intentionally-nonexistent-model"


def discovery(models=(MODEL,)):
    return {"status": "PASS", "models": list(models), "nemotron_models": [m for m in models if "nemotron" in m.lower()]}


def record(probe):
    result = {"provider": "nebius", "status": "PASS", "http_status": 200,
              "parameters": _payload(MODEL, probe), "latency_ms": 2, "usage": {"total_tokens": 8},
              "provenance": "synthetic test response"}
    if probe == "invalid_model_error":
        return {**result, "status": "FAIL", "http_status": 404, "raw_response": '{"error":{"code":"model_not_found","message":"model does not exist"}}'}
    if probe == "streaming":
        result["response"] = {"done": True, "events": [
            {"model": MODEL, "choices": [{"index": 0, "delta": {"role": "assistant", "content": '{"ok":'}, "finish_reason": None}]},
            {"model": MODEL, "choices": [{"index": 0, "delta": {"content": "true}"}, "finish_reason": "stop"}]},
            {"model": MODEL, "choices": [], "usage": {"total_tokens": 8}}]}
    else:
        message = {"role": "assistant", "content": '{"ok":true}'}
        if probe == "tool_call":
            message = {"role": "assistant", "content": None, "tool_calls": [
                {"id": "c_18", "type": "function", "function": {"name": "report", "arguments": '{"ok":true}'}}]}
        result["response"] = {"model": MODEL, "choices": [{"index": 0, "message": message,
            "finish_reason": "tool_calls" if probe == "tool_call" else "stop"}]}
    return result


class LabIdentityTests(unittest.TestCase):
    def test_all_declared_probes_pass_their_distinct_contracts(self):
        for probe in PROBES:
            with self.subTest(probe=probe):
                self.assertEqual(_check(probe, record(probe))[0], "PASS")

    def test_normal_completions_reject_missing_wrong_model_and_other_provider(self):
        for probe in ("structured_json", "tool_call"):
            for mutation in ("missing-model", "wrong-model", "provider", "extra-choice", "refusal", "role", "finish"):
                value = record(probe)
                body = value["response"]
                if mutation == "missing-model": body.pop("model")
                if mutation == "wrong-model": body["model"] = "nvidia/Other-Nemotron"
                if mutation == "provider": value["provider"] = "deepseek"
                if mutation == "extra-choice": body["choices"].append(deepcopy(body["choices"][0]))
                if mutation == "refusal": body["choices"][0]["message"]["refusal"] = "refused"
                if mutation == "role": body["choices"][0]["message"]["role"] = "user"
                if mutation == "finish": body["choices"][0]["finish_reason"] = "stop" if probe == "tool_call" else "tool_calls"
                with self.subTest(probe=probe, mutation=mutation):
                    self.assertEqual(_check(probe, value)[0], "FAIL")

    def test_every_stream_event_requires_same_model_and_explicit_assistant_start(self):
        for mutation in ("missing-model", "different-middle-model", "different-usage-model", "role", "missing-role", "truthy-done", "truncated"):
            value = record("streaming")
            events = value["response"]["events"]
            if mutation == "missing-model": events[0].pop("model")
            if mutation == "different-middle-model": events[1]["model"] = "nvidia/Other-Nemotron"
            if mutation == "different-usage-model": events[-1]["model"] = "nvidia/Other-Nemotron"
            if mutation == "role": events[0]["choices"][0]["delta"]["role"] = "user"
            if mutation == "missing-role": events[0]["choices"][0]["delta"].pop("role")
            if mutation == "truthy-done": value["response"]["done"] = "true"
            if mutation == "truncated": events[1]["choices"][0]["finish_reason"] = "length"
            with self.subTest(mutation=mutation):
                self.assertEqual(_check("streaming", value)[0], "FAIL")

    def test_intentional_invalid_model_is_not_required_to_return_a_completion_identity(self):
        value = record("invalid_model_error")
        self.assertEqual(value["parameters"]["model"], INVALID)
        self.assertEqual(_check("invalid_model_error", value)[0], "PASS")
        value["http_status"] = 401
        self.assertEqual(_check("invalid_model_error", value)[0], "FAIL")
        value["http_status"] = 400
        value["raw_response"] = '{"error":"schema unsupported"}'
        self.assertEqual(_check("invalid_model_error", value)[0], "FAIL")
        value = record("invalid_model_error")
        value["provider"] = "deepseek"
        self.assertEqual(_check("invalid_model_error", value)[0], "FAIL")
        value = record("invalid_model_error")
        value["parameters"]["model"] = MODEL
        self.assertEqual(_check("invalid_model_error", value)[0], "FAIL")

    def test_selected_model_not_in_discovery_blocks_every_paid_probe(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(providers, "discover_models", return_value=discovery(("nvidia/Other-Nemotron",))), patch.object(
            providers, "request") as request, patch("patchcourt.lab._ablation") as ablation:
            report = run_lab(folder, model=MODEL, trials=1)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(len(report["trials"]), 4)
        self.assertTrue(all(r["status"] == "BLOCKED" for r in report["trials"]))
        request.assert_not_called()
        ablation.assert_not_called()

    def test_non_nvidia_or_non_nemotron_explicit_models_are_rejected_before_discovery(self):
        for model in ("other/Nemotron", "nvidia/OtherModel", INVALID):
            with self.subTest(model=model), tempfile.TemporaryDirectory() as folder, patch.object(
                providers, "discover_models", return_value=discovery((model, MODEL))) as discover, patch.object(
                    providers, "request", return_value=record("structured_json")) as request, patch(
                        "patchcourt.lab._ablation", return_value={"status": "PASS"}):
                with self.assertRaises(ValueError):
                    run_lab(folder, model=model, trials=1)
                discover.assert_not_called()
                request.assert_not_called()

    def test_discovery_filters_vendor_and_all_scheduled_requests_keep_exact_identity(self):
        observed = []
        def request(provider, payload):
            observed.append((provider, deepcopy(payload)))
            probe = "invalid_model_error" if payload["model"] == INVALID else "streaming" if payload.get("stream") else "tool_call" if payload.get("tools") else "structured_json"
            return record(probe)
        with tempfile.TemporaryDirectory() as folder, patch.dict("os.environ", {}, clear=True), patch.object(
            providers, "discover_models", return_value=discovery(("other/Nemotron", MODEL))), patch.object(
                providers, "request", side_effect=request), patch("patchcourt.lab._ablation", return_value={"status": "PASS"}):
            report = run_lab(folder, trials=1)
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(report["selected_model"], MODEL)
            self.assertEqual(report["provider"], "nebius")
            self.assertTrue(report["nemotron_selected"])
            self.assertEqual(len(observed), 4)
            self.assertTrue(all(p == "nebius" for p, _ in observed))
            self.assertEqual([p["model"] for _, p in observed], [MODEL, MODEL, MODEL, INVALID])
            self.assertEqual(read_json(Path(folder) / "trials" / "invalid_model_error-1.json")["status"], "PASS")

    def test_missing_model_replies_are_saved_as_failures_instead_of_dropped(self):
        def request(provider, payload):
            probe = "invalid_model_error" if payload["model"] == INVALID else "streaming" if payload.get("stream") else "tool_call" if payload.get("tools") else "structured_json"
            result = record(probe)
            if probe == "streaming":
                for event in result["response"]["events"]: event.pop("model")
            elif probe != "invalid_model_error":
                result["response"].pop("model")
            return result
        with tempfile.TemporaryDirectory() as folder, patch.object(providers, "discover_models", return_value=discovery()), patch.object(
            providers, "request", side_effect=request), patch("patchcourt.lab._ablation", return_value={"status": "PASS"}):
            report = run_lab(folder, model=MODEL, trials=1)
            self.assertEqual(report["status"], "FAIL")
            self.assertEqual(len(report["trials"]), 4)
            self.assertEqual(sum(r["status"] == "FAIL" for r in report["trials"]), 3)
            self.assertEqual(report["trials"][-1]["status"], "PASS")
            self.assertNotIn("model", read_json(Path(folder) / "trials" / "structured_json-1.json")["request"]["response"])


if __name__ == "__main__":
    unittest.main()
