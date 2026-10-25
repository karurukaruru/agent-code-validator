"""Held-out boundary checks written independently of implementation.

No network, provider credentials, generated-code execution, or third-party test
runner is required. These assertions deliberately include malformed and unknown
wire schemas, not just the demo fixtures.
"""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from patchcourt.evidence import sanitize
from patchcourt.knowledge import KnowledgeStore
from patchcourt.reproductions import SOURCES, load_crewai, nvidia_messages, run_reproductions, source
from patchcourt.semantic import compare_messages, reconstruct_stream


def conversation():
    return [
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "heldout-1", "type": "function", "function": {
                "name": "quote", "arguments": '{"currency":"JPY","quantity":0,"includeTax":false}'}},
            {"id": "heldout-2", "type": "function", "function": {
                "name": "ship", "arguments": '{"address":{"city":"東京"},"lines":["a","b"]}'}}]},
        {"role": "tool", "tool_call_id": "heldout-2", "content": ""},
        {"role": "tool", "tool_call_id": "heldout-1", "content": "0"},
    ]


def stream(call=None, role="assistant"):
    call = call or {"index": 0, "id": "heldout-stream", "type": "function", "function": {"name": "quote", "arguments": '{}'}}
    return [
        {"choices": [{"index": 0, "delta": {"role": role, "tool_calls": [call]}, "finish_reason": None}]},
        {"choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}]},
    ]


class SemanticAdversarialTests(unittest.TestCase):
    def test_unknown_content_abstains_even_when_identical(self):
        payload = [{"role": "user", "content": [{"type": "input_audio", "input_audio": {"data": "opaque", "format": "wav"}}]}]
        self.assertEqual(compare_messages(payload, payload)["status"], "INCONCLUSIVE")

    def test_unknown_tool_extension_abstains(self):
        candidate = conversation()
        candidate[0]["tool_calls"][0]["function"]["execution_policy"] = "parallel"
        self.assertEqual(compare_messages(conversation(), candidate)["status"], "INCONCLUSIVE")

    def test_nested_boolean_is_not_integer(self):
        candidate = conversation()
        candidate[0]["tool_calls"][0]["function"]["arguments"] = '{"currency":"JPY","quantity":0,"includeTax":0}'
        self.assertEqual(compare_messages(conversation(), candidate)["status"], "FAIL")

    def test_return_order_need_not_equal_call_order(self):
        self.assertEqual(compare_messages(conversation(), conversation())["status"], "PASS")

    def test_duplicate_result_is_invalid_baseline(self):
        payload = conversation()
        payload.append(copy.deepcopy(payload[-1]))
        self.assertEqual(compare_messages(payload, payload)["status"], "NEEDS_REVIEW")

    def test_contradictory_role_alias_cannot_pass(self):
        candidate = [{"role": "user", "type": "ai", "content": "hello"}]
        self.assertNotEqual(compare_messages(candidate, candidate)["status"], "PASS")

    def test_conflicting_call_representations_cannot_pass(self):
        payload = conversation()
        conflict = copy.deepcopy(payload[0]["tool_calls"])
        conflict[0]["function"]["name"] = "different_action"
        payload[0]["additional_kwargs"] = {"tool_calls": conflict}
        self.assertNotEqual(compare_messages(payload, payload)["status"], "PASS")

    def test_nonfinite_arguments_cannot_pass(self):
        for number in (float("nan"), float("inf"), -float("inf")):
            payload = [{"role": "assistant", "content": "", "tool_calls": [{"id": "x", "name": "quote", "args": {"amount": number}}]}]
            with self.subTest(number=number):
                self.assertNotEqual(compare_messages(payload, copy.deepcopy(payload))["status"], "PASS")

    def test_fragmented_stream_preserves_argument_bytes(self):
        events = stream()
        events[0]["choices"][0]["delta"]["tool_calls"][0]["function"]["arguments"] = '{"city":"'
        events.insert(1, {"choices": [{"index": 0, "delta": {"tool_calls": [{"index": 0, "function": {"arguments": '東京"}'}}]}, "finish_reason": None}]})
        result = reconstruct_stream(events)
        self.assertEqual(json.loads(result["tool_calls"][0]["function"]["arguments"]), {"city": "東京"})

    def test_truncated_stream_is_rejected(self):
        events = stream()
        events[-1]["choices"][0]["finish_reason"] = "length"
        with self.assertRaises(ValueError):
            reconstruct_stream(events)

    def test_unknown_stream_tool_type_is_rejected(self):
        call = {"index": 0, "id": "x", "type": "custom", "function": {"name": "quote", "arguments": "{}"}}
        with self.assertRaises(ValueError):
            reconstruct_stream(stream(call))

    def test_unknown_stream_function_fields_are_rejected(self):
        call = {"index": 0, "id": "x", "type": "function", "function": {"name": "quote", "arguments": "{}", "execution_policy": "parallel"}}
        with self.assertRaises(ValueError):
            reconstruct_stream(stream(call))

    def test_nonassistant_stream_role_is_rejected(self):
        with self.assertRaises(ValueError):
            reconstruct_stream(stream(role="user"))


class EvidenceAdversarialTests(unittest.TestCase):
    def identity(self):
        return {"software": "heldout", "version": "1.0", "boundary": "serializer", "source_sha256": "a" * 64, "environment": "stdlib-test"}

    def test_plain_unexecuted_assertion_cannot_enter_knowledge(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as tmp:
            store = KnowledgeStore(tmp)
            with self.assertRaises(ValueError):
                store.save(self.identity(), {"status": "PASS", "execution": False})

    def test_string_execution_flag_cannot_enter_verified_knowledge(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as tmp:
            store = KnowledgeStore(tmp)
            with self.assertRaises(ValueError):
                store.save(self.identity(), {"status": "PASS", "execution": "false"})

    def test_inconclusive_execution_cannot_enter_verified_knowledge(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as tmp:
            store = KnowledgeStore(tmp)
            with self.assertRaises(ValueError):
                store.save(self.identity(), {"status": "INCONCLUSIVE", "execution": True})

    def test_tampered_knowledge_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as tmp:
            store = KnowledgeStore(tmp)
            key = store.save(self.identity(), {"status": "FAIL", "execution": True})
            path = Path(tmp) / (key + ".json")
            record = json.loads(path.read_text(encoding="utf-8"))
            record["evidence"]["status"] = "PASS"
            path.write_text(json.dumps(record), encoding="utf-8")
            with self.assertRaises(ValueError):
                store.lookup(self.identity())

    def test_version_change_never_reuses_prior_observation(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as tmp:
            store = KnowledgeStore(tmp)
            store.save(self.identity(), {"status": "PASS", "execution": True})
            other = self.identity()
            other["version"] = "1.1"
            self.assertIsNone(store.lookup(other))

    def test_redaction_keeps_saved_knowledge_integrity_valid(self):
        secret = "heldout_private_value_123456"
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as tmp, patch.dict(os.environ, {"PATCHCOURT_TEST_API_KEY": secret}):
            store = KnowledgeStore(tmp)
            key = store.save(self.identity(), {"status": "FAIL", "execution": True, "log": "observed " + secret})
            self.assertNotIn(secret, (Path(tmp) / (key + ".json")).read_text(encoding="utf-8"))
            self.assertIsNotNone(store.lookup(self.identity()))

    def test_authorization_and_nested_secrets_redacted(self):
        result = sanitize({"Authorization": "Bearer private", "nested": [{"api_key": "private"}], "log": "Bearer abcdefghijklmnop"})
        self.assertNotIn("private", json.dumps(result))
        self.assertNotIn("abcdefghijklmnop", json.dumps(result))


class ReproductionAdversarialTests(unittest.TestCase):
    def test_actual_source_hash_mismatch_refuses_execution(self):
        with patch.dict(SOURCES["nvidia"], {"sha256": "0" * 64}):
            with self.assertRaises(ValueError):
                source("nvidia")

    def test_nvidia_repair_preserves_heldout_parallel_calls(self):
        original = conversation()
        before = nvidia_messages(original)
        after = nvidia_messages(original, repaired=True)
        self.assertEqual(compare_messages(original, before)["status"], "FAIL")
        self.assertEqual(compare_messages(original, after)["status"], "PASS")
        self.assertEqual(after[2]["content"], "0")
        self.assertEqual(after[1]["content"], "")

    def test_crewai_patch_preserves_two_distinct_image_payloads(self):
        messages = [{"role": "user", "content": [
            {"type": "text", "text": "Compare"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,AQID"}},
            {"type": "image_url", "image_url": "data:image/jpeg;base64,BAUG"},
        ]}]
        content, _ = load_crewai(repaired=True)(messages)
        images = [part.inline_data for part in content[0].parts if part.inline_data is not None]
        self.assertEqual([(part.data, part.mime_type) for part in images], [(b"\x01\x02\x03", "image/png"), (b"\x04\x05\x06", "image/jpeg")])

    def test_crewai_patch_rejects_corrupt_base64(self):
        messages = [{"role": "user", "content": [{"type": "image_url", "image_url": "data:image/png;base64,%%%"}]}]
        with self.assertRaises(ValueError):
            load_crewai(repaired=True)(messages)

    def test_reproduction_never_claims_full_sdk_or_live_vision(self):
        results = run_reproductions()
        self.assertEqual(len(results), 2)
        for result in results:
            self.assertIs(result["provenance"]["full_sdk_verified"], False)
            self.assertEqual(result["repair"]["scope"], "source-boundary harness only")
        vision = next(item for item in results if item["id"] == "crewai-8434")
        self.assertEqual(vision["task_replay"]["after"]["status"], "INCONCLUSIVE")

    def test_repair_verification_catches_second_call_corruption(self):
        actual_adapter = nvidia_messages

        def damaged_adapter(messages, repaired=False):
            result = actual_adapter(messages, repaired)
            if repaired:
                result[0]["tool_calls"][1]["function"]["arguments"] = '{"sku":"WRONG"}'
            return result

        with patch("patchcourt.reproductions.nvidia_messages", side_effect=damaged_adapter):
            result = next(item for item in run_reproductions() if item["id"] == "langchain-nvidia-387")
        self.assertNotEqual(result["repair"]["status"], "VERIFIED")


if __name__ == "__main__":
    unittest.main()
