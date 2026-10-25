"""Held-out protocol review; no provider requests or credentials are used."""
import copy
import unittest

from patchcourt.semantic import compare_messages, reconstruct_stream


def text_stream():
    return [{"choices": [{"index": 0, "delta": {"content": "東京"}, "finish_reason": "stop"}]}]


def call_message():
    return {"role": "assistant", "content": None, "tool_calls": [
        {"id": "call_quote", "type": "function", "function": {"name": "quote", "arguments": '{"amount":0}'}}
    ]}


def call_stream():
    return [{"choices": [{"index": 0, "delta": {"tool_calls": [
        {"index": 0, **call_message()["tool_calls"][0]}
    ]}, "finish_reason": "tool_calls"}]}]


class StreamProtocolReviewTests(unittest.TestCase):
    def test_malformed_json_containers_raise_validation_errors(self):
        malformed = [None, {}, [None], [{"choices": None}], [{"choices": {}}],
                     [{"choices": [None]}], [{"choices": [[]]}]]
        for field, values in (("delta", [None, []]),):
            for value in values:
                events = text_stream()
                events[0]["choices"][0][field] = value
                malformed.append(events)
        for value in (None, {}, [None], [[]], [{"index": 0, "function": None}],
                      [{"index": 0, "function": []}]):
            events = call_stream()
            events[0]["choices"][0]["delta"]["tool_calls"] = value
            malformed.append(events)
        for events in malformed:
            with self.subTest(events=events), self.assertRaises(ValueError):
                reconstruct_stream(events)

    def test_boolean_and_float_indices_do_not_alias_integer_indices(self):
        for value in (False, True, 0.0):
            events = text_stream()
            events[0]["choices"][0]["index"] = value
            with self.subTest(kind="choice", index=value), self.assertRaises(ValueError):
                reconstruct_stream(events)
            events = call_stream()
            events[0]["choices"][0]["delta"]["tool_calls"][0]["index"] = value
            with self.subTest(kind="tool", index=value), self.assertRaises(ValueError):
                reconstruct_stream(events)

    def test_falsey_nontext_content_is_not_silently_discarded(self):
        for value in (False, 0, [], {}):
            events = text_stream()
            events.insert(0, {"choices": [{"index": 0, "delta": {"content": value}, "finish_reason": None}]})
            with self.subTest(content=value), self.assertRaises(ValueError):
                reconstruct_stream(events)

    def test_tool_fragments_require_text_fields(self):
        for field, value in (("id", 7), ("name", None), ("arguments", {})):
            events = call_stream()
            call = events[0]["choices"][0]["delta"]["tool_calls"][0]
            (call if field == "id" else call["function"])[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                reconstruct_stream(events)

    def test_terminal_reason_must_match_tool_call_content(self):
        events = call_stream()
        events[0]["choices"][0]["finish_reason"] = "stop"
        with self.assertRaises(ValueError):
            reconstruct_stream(events)
        events = text_stream()
        events[0]["choices"][0]["finish_reason"] = "tool_calls"
        with self.assertRaises(ValueError):
            reconstruct_stream(events)
        for reason in (False, 0, "", [], {}):
            events = text_stream()
            events.insert(0, {"choices": [{"index": 0, "delta": {}, "finish_reason": reason}]})
            with self.subTest(reason=reason), self.assertRaises(ValueError):
                reconstruct_stream(events)

    def test_duplicate_choice_zero_cannot_merge_two_choices(self):
        events = text_stream()
        events[0]["choices"].insert(0, {"index": 0, "delta": {"content": "different choice"}, "finish_reason": None})
        with self.assertRaises(ValueError):
            reconstruct_stream(events)

    def test_completed_stream_requires_unique_nonempty_tool_ids(self):
        events = call_stream()
        events[0]["choices"][0]["delta"]["tool_calls"][0].pop("id")
        with self.assertRaises(ValueError):
            reconstruct_stream(events)
        events = call_stream()
        calls = events[0]["choices"][0]["delta"]["tool_calls"]
        duplicate = copy.deepcopy(calls[0])
        duplicate["index"] = 1
        calls.append(duplicate)
        with self.assertRaises(ValueError):
            reconstruct_stream(events)

    def test_usage_only_tail_and_null_content_remain_supported(self):
        events = text_stream()
        events.insert(0, {"choices": [{"index": 0, "delta": {"role": "assistant", "content": None}, "finish_reason": None}]})
        events.append({"choices": [], "usage": {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4}})
        self.assertEqual(reconstruct_stream(events), {"role": "assistant", "content": "東京"})

    def test_fragmented_call_arguments_and_assistant_text_are_preserved(self):
        events = call_stream()
        first = events[0]["choices"][0]
        first["finish_reason"] = None
        first["delta"]["content"] = "Looking up 東京"
        first["delta"]["tool_calls"][0]["function"]["arguments"] = '{"city":"'
        events.append({"choices": [{"index": 0, "delta": {"tool_calls": [
            {"index": 0, "function": {"arguments": '東京","includeTax":false}'}}
        ]}, "finish_reason": "tool_calls"}]})
        result = reconstruct_stream(events)
        expected = call_message()
        expected["content"] = "Looking up 東京"
        expected["tool_calls"][0]["function"]["arguments"] = '{"includeTax": false, "city": "東京"}'
        self.assertEqual(compare_messages([expected], [result])["status"], "PASS")


class NormalizeProtocolReviewTests(unittest.TestCase):
    def test_call_only_conversation_fragment_is_valid(self):
        message = call_message()
        self.assertEqual(compare_messages([message], [copy.deepcopy(message)])["status"], "PASS")

    def test_observational_ids_and_token_counters_do_not_change_semantics(self):
        before = [{"role": "assistant", "content": "same", "id": "first", "usage_metadata": {
            "input_tokens": 10, "output_tokens": 2, "total_tokens": 12,
            "input_token_details": {"cache_read": 3}}, "response_metadata": {
                "model_name": "model-a", "token_usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12}}}]
        after = copy.deepcopy(before)
        after[0]["id"] = "second"
        after[0]["usage_metadata"]["input_tokens"] = 11
        after[0]["response_metadata"]["model_name"] = "model-b"
        self.assertEqual(compare_messages(before, after)["status"], "PASS")

    def test_unmodeled_response_and_usage_metadata_abstain(self):
        for key, metadata in (("response_metadata", {"refusal": "blocked"}),
                              ("response_metadata", {"finish_reason": "length"}),
                              ("response_metadata", {"opaque": {"behavior": "unknown"}}),
                              ("usage_metadata", {"new_semantics": 1})):
            messages = [{"role": "assistant", "content": "same", key: metadata}]
            with self.subTest(key=key, metadata=metadata):
                self.assertEqual(compare_messages(messages, messages)["status"], "INCONCLUSIVE")

    def test_explicit_empty_and_nonempty_tool_representations_conflict(self):
        message = call_message()
        message["additional_kwargs"] = {"tool_calls": copy.deepcopy(message["tool_calls"])}
        message["tool_calls"] = []
        self.assertEqual(compare_messages([message], [message])["status"], "INCONCLUSIVE")

    def test_unknown_image_detail_abstains_even_when_unchanged(self):
        messages = [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "https://example.invalid/image", "detail": "future_mode"}}]}]
        self.assertEqual(compare_messages(messages, messages)["status"], "INCONCLUSIVE")


if __name__ == "__main__":
    unittest.main()
