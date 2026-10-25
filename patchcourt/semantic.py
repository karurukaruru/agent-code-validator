"""Semantic comparison of supported OpenAI/LangChain message boundaries.

Unsupported parts abstain. No version-number inference, model judge, network or exec.
"""
from __future__ import annotations

import json
from collections import Counter
from .evidence import canonical, strict_json, validate_shape


class Unsupported(ValueError):
    pass


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
        role = {"ai": "assistant", "human": "user"}.get(role, role)
        if "role" in message and "type" in message and {"ai": "assistant", "human": "user"}.get(message["type"], message["type"]) != role:
            raise Unsupported("Contradictory message role representations")
        if role not in {"system", "developer", "user", "assistant", "tool"}:
            raise Unsupported(f"Unsupported role: {role}")
        allowed = {"role", "type", "content", "tool_calls", "tool_call_id", "name", "additional_kwargs", "id", "response_metadata", "usage_metadata"}
        if set(message) - allowed:
            raise Unsupported("Unsupported message fields: " + ", ".join(sorted(set(message) - allowed)))
        extra = message.get("additional_kwargs", {})
        if not isinstance(extra, dict) or set(extra) - {"tool_calls"}:
            raise Unsupported("Unmodeled additional_kwargs semantics")
        if "tool_calls" in message and not isinstance(message["tool_calls"], list):
            raise ValueError("tool_calls must be a list")
        if "tool_calls" in extra and not isinstance(extra["tool_calls"], list):
            raise ValueError("Legacy tool_calls must be a list")
        calls = message.get("tool_calls") or extra.get("tool_calls") or []
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
            if call.get("type", "function") not in {"function", "tool_call"}:
                raise Unsupported("Unsupported tool call type")
            if not isinstance(name, str) or not name:
                raise ValueError("Tool call name must be non-empty")
            normalized_calls.append({"id": call.get("id"), "name": name, "args": _arguments(args)})
        if message.get("tool_calls") and extra.get("tool_calls"):
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
                    image = part["image_url"]
                    if isinstance(image, str):
                        image = {"url": image}
                    if not isinstance(image, dict) or set(image) - {"url", "detail"} or not isinstance(image.get("url"), str):
                        raise Unsupported("Unsupported image reference")
                    parts.append({"type": "image_url", "url": image["url"], "detail": image.get("detail", "auto")})
                else:
                    raise Unsupported(f"Unsupported content part type: {kind}")
        else:
            raise ValueError("content must be text, null, or a list")
        item = {"role": role, "content": parts, "tool_calls": normalized_calls}
        for key in ("tool_call_id", "name"):
            if key in message:
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
    calls, content, done = {}, [], False
    if not isinstance(events, list) or len(events) > 10000:
        raise ValueError("Too many streaming events")
    for event in events:
        if not isinstance(event, dict) or set(event) - {"id", "object", "created", "model", "choices", "usage", "system_fingerprint", "service_tier"}:
            raise Unsupported("Unmodeled streaming event")
        for choice in event.get("choices", []):
            if done:
                raise ValueError("Data after stream finish")
            if choice.get("index", 0) != 0:
                raise Unsupported("Only one stream choice is supported")
            if set(choice) - {"index", "delta", "finish_reason", "logprobs"}:
                raise Unsupported("Unmodeled streaming choice")
            delta = choice.get("delta", {})
            if set(delta) - {"role", "content", "tool_calls"}:
                raise Unsupported("Unmodeled streaming delta")
            if delta.get("role", "assistant") != "assistant":
                raise ValueError("Completion stream role must be assistant")
            if delta.get("content"):
                content.append(delta["content"])
            for call in delta.get("tool_calls", []):
                if set(call) - {"index", "id", "type", "function"} or set(call.get("function", {})) - {"name", "arguments"}:
                    raise Unsupported("Unmodeled streaming tool fields")
                if call.get("type", "function") != "function":
                    raise Unsupported("Unsupported streaming tool type")
                index = call.get("index")
                if not isinstance(index, int) or not 0 <= index < 100:
                    raise ValueError("Invalid streaming call index")
                current = calls.setdefault(index, {"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
                current["id"] += call.get("id", "")
                for key in ("name", "arguments"):
                    current["function"][key] += call.get("function", {}).get(key, "")
            reason = choice.get("finish_reason")
            if reason:
                if reason not in {"stop", "tool_calls"}:
                    raise ValueError("Truncated or unsuccessful completion: " + str(reason))
                done = True
    if not done:
        raise ValueError("Stream has no terminal finish reason")
    message = {"role": "assistant", "content": "".join(content)}
    if calls:
        if sorted(calls) != list(range(len(calls))):
            raise ValueError("Missing streaming call index")
        message["tool_calls"] = [calls[i] for i in sorted(calls)]
    normalize([message])
    return message
