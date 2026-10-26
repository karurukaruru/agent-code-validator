"""Semantic comparison of supported OpenAI/LangChain message boundaries.

Unsupported parts abstain. No version-number inference, model judge, network or exec.
"""
from __future__ import annotations

from .evidence import canonical, strict_json, validate_shape


class Unsupported(ValueError):
    pass


def _token_counts(value):
    """Recognize observational counters without treating arbitrary metadata as safe."""
    if not isinstance(value, dict):
        raise Unsupported("Unsupported token usage metadata")
    for count in value.values():
        if isinstance(count, dict):
            _token_counts(count)
        elif type(count) is not int or count < 0:
            raise Unsupported("Unsupported token usage metadata")


def _metadata(message):
    # Message IDs and measured token counts are not message content. Unknown
    # response metadata can, however, encode refusal, truncation or safety state.
    if "id" in message and message["id"] is not None and not isinstance(message["id"], str):
        raise ValueError("Message id must be a string or null")
    usage = message.get("usage_metadata")
    if usage is not None:
        if not isinstance(usage, dict) or set(usage) - {
            "input_tokens", "output_tokens", "total_tokens", "input_token_details", "output_token_details"
        }:
            raise Unsupported("Unmodeled usage metadata")
        _token_counts(usage)
    metadata = message.get("response_metadata", {})
    if not isinstance(metadata, dict) or set(metadata) - {
        "token_usage", "model_name", "model", "system_fingerprint", "id", "service_tier"
    }:
        raise Unsupported("Unmodeled response metadata")
    for key, value in metadata.items():
        if key == "token_usage":
            if not isinstance(value, dict) or set(value) - {
                "prompt_tokens", "completion_tokens", "total_tokens", "prompt_tokens_details", "completion_tokens_details"
            }:
                raise Unsupported("Unmodeled token usage metadata")
            _token_counts(value)
        elif value is not None and not isinstance(value, str):
            raise Unsupported("Unsupported response metadata value")


def _arguments(value):
    if isinstance(value, str):
        try:
            value = strict_json(value)
        except (ValueError, TypeError) as exc:
            raise ValueError("Invalid JSON tool arguments") from exc
    if not isinstance(value, dict):
        raise ValueError("Tool arguments must be an object")
    canonical(value)  # Reject NaN/Infinity even when supplied as Python objects.
    return value


def normalize(messages):
    validate_shape(messages)
    if not isinstance(messages, list) or len(messages) > 1000:
        raise ValueError("messages must be a list of at most 1000 entries")
    result = []
    for message in messages:
        if not isinstance(message, dict):
            raise ValueError("Each message must be an object")
        role = message.get("role", message.get("type"))
        if not isinstance(role, str):
            raise ValueError("Message role must be a string")
        role = {"ai": "assistant", "human": "user"}.get(role, role)
        if "role" in message and "type" in message:
            if not isinstance(message["type"], str):
                raise ValueError("Message type must be a string")
            if {"ai": "assistant", "human": "user"}.get(message["type"], message["type"]) != role:
                raise Unsupported("Contradictory message role representations")
        if role not in {"system", "developer", "user", "assistant", "tool"}:
            raise Unsupported(f"Unsupported role: {role}")
        allowed = {"role", "type", "content", "tool_calls", "tool_call_id", "name", "additional_kwargs", "id", "response_metadata", "usage_metadata"}
        if set(message) - allowed:
            raise Unsupported("Unsupported message fields: " + ", ".join(sorted(set(message) - allowed)))
        _metadata(message)
        extra = message.get("additional_kwargs", {})
        if not isinstance(extra, dict) or set(extra) - {"tool_calls"}:
            raise Unsupported("Unmodeled additional_kwargs semantics")
        if "tool_calls" in message and not isinstance(message["tool_calls"], list):
            raise ValueError("tool_calls must be a list")
        if "tool_calls" in extra and not isinstance(extra["tool_calls"], list):
            raise ValueError("Legacy tool_calls must be a list")
        calls = message["tool_calls"] if "tool_calls" in message else extra.get("tool_calls", [])
        if not isinstance(calls, list):
            raise ValueError("tool_calls must be a list")
        normalized_calls = []
        for call in calls:
            if not isinstance(call, dict):
                raise ValueError("tool call must be an object")
            if "function" in call:
                fn = call["function"]
                if not isinstance(fn, dict):
                    raise ValueError("function must be an object")
                if set(call) - {"id", "type", "function"} or set(fn) - {"name", "arguments"}:
                    raise Unsupported("Unmodeled tool call fields")
                name, args = fn.get("name"), fn.get("arguments")
            else:
                if set(call) - {"id", "type", "name", "args"}:
                    raise Unsupported("Unmodeled normalized tool call fields")
                name, args = call.get("name"), call.get("args")
            if call.get("type", "function") not in ("function", "tool_call"):
                raise Unsupported("Unsupported tool call type")
            if not isinstance(name, str) or not name:
                raise ValueError("Tool call name must be non-empty")
            normalized_calls.append({"id": call.get("id"), "name": name, "args": _arguments(args)})
        if "tool_calls" in message and "tool_calls" in extra:
            legacy = normalize([{"role": "assistant", "content": "", "tool_calls": extra["tool_calls"]}])[0]["tool_calls"]
            if _diff(normalized_calls, legacy):
                raise Unsupported("Conflicting normalized and legacy tool calls")
        if normalized_calls and role != "assistant":
            raise ValueError("Only assistant messages may contain tool calls")
        content = message.get("content")
        parts = []
        if content is None:
            content = ""
        if isinstance(content, str):
            if content:
                parts.append({"type": "text", "text": content})
        elif isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    raise Unsupported("Unsupported content part")
                kind = part.get("type")
                if kind == "text" and set(part) <= {"type", "text"} and isinstance(part.get("text"), str):
                    if part["text"]:
                        if parts and parts[-1]["type"] == "text":
                            parts[-1]["text"] += part["text"]
                        else:
                            parts.append(part.copy())
                elif kind == "image_url" and set(part) <= {"type", "image_url"}:
                    image = part.get("image_url")
                    if isinstance(image, str):
                        image = {"url": image}
                    if not isinstance(image, dict) or set(image) - {"url", "detail"} or not isinstance(image.get("url"), str):
                        raise Unsupported("Unsupported image reference")
                    if image.get("detail", "auto") not in ("auto", "low", "high"):
                        raise Unsupported("Unsupported image detail")
                    parts.append({"type": "image_url", "url": image["url"], "detail": image.get("detail", "auto")})
                else:
                    raise Unsupported(f"Unsupported content part type: {kind}")
        else:
            raise ValueError("content must be text, null, or a list")
        item = {"role": role, "content": parts, "tool_calls": normalized_calls}
        for key in ("tool_call_id", "name"):
            if key in message:
                if key == "name" and message[key] is None:
                    item[key] = None  # Normal LangChain optional name default.
                elif not isinstance(message[key], str) or not message[key]:
                    raise ValueError(key + " must be a non-empty string")
                else:
                    item[key] = message[key]
        result.append(item)
    return result


def relationship_errors(messages):
    errors, pending, seen = [], set(), set()
    for i, message in enumerate(messages):
        for call in message["tool_calls"]:
            ident = call["id"]
            if not isinstance(ident, str) or not ident:
                errors.append((f"/{i}/tool_calls", "MISSING_ID", "Tool call has no non-empty identifier"))
            elif ident in seen:
                errors.append((f"/{i}/tool_calls", "DUPLICATE_ID", f"Duplicate tool call identifier {ident}"))
            else:
                pending.add(ident)
                seen.add(ident)
        if message["role"] == "tool":
            ident = message.get("tool_call_id")
            if not isinstance(ident, str) or ident not in pending:
                errors.append((f"/{i}/tool_call_id", "ORPHAN_RESULT", "Tool result lacks an earlier unmatched call"))
            else:
                pending.remove(ident)
    return errors


def _diff(a, b, path=""):
    if type(a) is not type(b):
        return [(path, a, b)]
    if isinstance(a, dict):
        out = []
        for key in sorted(set(a) | set(b)):
            p = path + "/" + key.replace("~", "~0").replace("/", "~1")
            if key not in a or key not in b:
                out.append((p, a.get(key), b.get(key)))
            else:
                out.extend(_diff(a[key], b[key], p))
        return out
    if isinstance(a, list):
        out = []
        for i in range(max(len(a), len(b))):
            p = path + "/" + str(i)
            if i >= len(a) or i >= len(b):
                out.append((p, a[i] if i < len(a) else None, b[i] if i < len(b) else None))
            else:
                out.extend(_diff(a[i], b[i], p))
        return out
    return [] if a == b else [(path, a, b)]


def compare_messages(baseline, candidate):
    """PASS only for valid, supported, semantically equivalent messages."""
    try:
        before = normalize(baseline)
        invalid = relationship_errors(before)
        if invalid:
            return {"status": "NEEDS_REVIEW", "findings": [{"code": c, "path": p, "message": "Invalid baseline: " + m} for p, c, m in invalid]}
    except (ValueError, TypeError, KeyError) as exc:
        return {"status": "INCONCLUSIVE", "findings": [{"code": "BASELINE_UNSUPPORTED", "path": "", "message": str(exc)}]}
    try:
        after = normalize(candidate)
    except Unsupported as exc:
        return {"status": "INCONCLUSIVE", "findings": [{"code": "CANDIDATE_UNSUPPORTED", "path": "", "message": str(exc)}]}
    except (ValueError, TypeError, KeyError) as exc:
        return {"status": "FAIL", "findings": [{"code": "INVALID_CANDIDATE", "path": "", "message": str(exc)}]}
    findings = [{"code": c, "path": p, "message": m} for p, c, m in relationship_errors(after)]
    for path, expected, actual in _diff(before, after):
        findings.append({"code": "SEMANTIC_CHANGE", "path": path, "expected": expected, "actual": actual, "message": "Observable message semantics changed"})
    return {"status": "FAIL" if findings else "PASS", "findings": findings}


def reconstruct_stream(events):
    """Reconstruct one OpenAI chat completion choice; reject incomplete streams."""
    calls, content, done, terminal_reason = {}, [], False, None
    if not isinstance(events, list) or len(events) > 10000:
        raise ValueError("Streaming events must be a list of at most 10000 entries")
    validate_shape(events)
    for event in events:
        if not isinstance(event, dict):
            raise ValueError("Streaming event must be an object")
        if set(event) - {"id", "object", "created", "model", "choices", "usage", "system_fingerprint", "service_tier"}:
            raise Unsupported("Unmodeled streaming event")
        choices = event.get("choices")
        if not isinstance(choices, list):
            raise ValueError("Streaming choices must be a list")
        if "usage" in event and event["usage"] is not None and not isinstance(event["usage"], dict):
            raise ValueError("Streaming usage must be an object or null")
        if not choices:
            if not done or not isinstance(event.get("usage"), dict):
                raise ValueError("Empty choices require a usage-only stream tail")
            continue
        if len(choices) != 1:
            raise Unsupported("Only one stream choice is supported")
        for choice in choices:
            if done:
                raise ValueError("Data after stream finish")
            if not isinstance(choice, dict):
                raise ValueError("Streaming choice must be an object")
            if type(choice.get("index", 0)) is not int or choice.get("index", 0) != 0:
                raise Unsupported("Only one stream choice is supported")
            if set(choice) - {"index", "delta", "finish_reason", "logprobs"}:
                raise Unsupported("Unmodeled streaming choice")
            delta = choice.get("delta", {})
            if not isinstance(delta, dict):
                raise ValueError("Streaming delta must be an object")
            if set(delta) - {"role", "content", "tool_calls"}:
                raise Unsupported("Unmodeled streaming delta")
            if delta.get("role", "assistant") != "assistant":
                raise ValueError("Completion stream role must be assistant")
            text = delta.get("content")
            if text is not None and not isinstance(text, str):
                raise ValueError("Streaming content must be text or null")
            if text:
                content.append(text)
            fragments = delta.get("tool_calls", [])
            if not isinstance(fragments, list):
                raise ValueError("Streaming tool_calls must be a list")
            for call in fragments:
                if not isinstance(call, dict):
                    raise ValueError("Streaming tool call must be an object")
                function = call.get("function", {})
                if not isinstance(function, dict):
                    raise ValueError("Streaming function must be an object")
                if set(call) - {"index", "id", "type", "function"} or set(function) - {"name", "arguments"}:
                    raise Unsupported("Unmodeled streaming tool fields")
                if call.get("type", "function") != "function":
                    raise Unsupported("Unsupported streaming tool type")
                index = call.get("index")
                if type(index) is not int or not 0 <= index < 100:
                    raise ValueError("Invalid streaming call index")
                current = calls.setdefault(index, {"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
                ident = call.get("id", "")
                if not isinstance(ident, str):
                    raise ValueError("Streaming tool call id must be text")
                current["id"] += ident
                for key in ("name", "arguments"):
                    fragment = function.get(key, "")
                    if not isinstance(fragment, str):
                        raise ValueError("Streaming function " + key + " must be text")
                    current["function"][key] += fragment
            reason = choice.get("finish_reason")
            if reason is not None:
                if reason not in ("stop", "tool_calls"):
                    raise ValueError("Truncated or unsuccessful completion: " + str(reason))
                terminal_reason = reason
                done = True
    if not done:
        raise ValueError("Stream has no terminal finish reason")
    message = {"role": "assistant", "content": "".join(content)}
    if calls:
        if sorted(calls) != list(range(len(calls))):
            raise ValueError("Missing streaming call index")
        message["tool_calls"] = [calls[i] for i in sorted(calls)]
    if (terminal_reason == "tool_calls") != bool(calls):
        raise ValueError("Stream finish reason disagrees with tool call content")
    normalized = normalize([message])
    if relationship_errors(normalized):
        raise ValueError("Invalid streaming tool call identifiers")
    return message
