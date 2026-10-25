"""Deterministic controls and mutations; these are not historical discoveries."""
from copy import deepcopy
from .semantic import compare_messages


def tool_conversation():
    return [
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "call_a", "type": "function", "function": {"name": "inventory", "arguments": '{"sku":"A","options":{"warehouse":2}}'}},
            {"id": "call_b", "type": "function", "function": {"name": "price", "arguments": '{"sku":"A"}'}}]},
        {"role": "tool", "tool_call_id": "call_a", "content": '{"quantity":3}'},
        {"role": "tool", "tool_call_id": "call_b", "content": '{"price":7}'}]


def cases():
    base = tool_conversation()
    result = []
    def add(ident, candidate, expected="FAIL", baseline=None):
        result.append({"id": ident, "title": ident.replace("-", " ").title(), "baseline": deepcopy(base if baseline is None else baseline), "candidate": candidate, "expected_status": expected, "provenance": "controlled mutation" if expected == "FAIL" else "negative control"})
    add("unchanged-tool-workflow", deepcopy(base), "PASS")
    changed = deepcopy(base); changed[0]["content"] = None
    changed[0]["tool_calls"][0]["function"]["arguments"] = '{ "options": {"warehouse": 2}, "sku": "A" }'
    add("json-formatting-equivalence", changed, "PASS")
    changed = deepcopy(base); changed[0].pop("tool_calls")
    add("dropped-tool-calls", changed)
    changed = deepcopy(base); changed[0]["tool_calls"][0].pop("id")
    add("missing-call-id", changed)
    changed = deepcopy(base); changed[0]["tool_calls"][1]["id"] = "call_a"
    add("duplicate-call-id", changed)
    changed = deepcopy(base); changed[0]["tool_calls"][0]["function"]["arguments"] = '{"sku":"A","options":{"warehouse":9}}'
    add("nested-argument-corruption", changed)
    changed = deepcopy(base); changed[1]["tool_call_id"] = "call_z"
    add("orphan-tool-result", changed)
    changed = deepcopy(base); changed[0]["role"] = "user"
    add("invalid-role-conversion", changed)
    changed = deepcopy(base); changed[0]["tool_calls"][0]["function"]["arguments"] = '{"unfinished":'
    add("truncated-arguments", changed)
    vision = [{"role": "user", "content": [{"type": "text", "text": "Count items"}, {"type": "image_url", "image_url": {"url": "data:image/png;base64,aW1hZ2U=", "detail": "high"}}]}]
    add("image-control", deepcopy(vision), "PASS", vision)
    changed = deepcopy(vision); changed[0]["content"].pop()
    add("lost-image-reference", changed, baseline=vision)
    changed = deepcopy(vision); changed[0]["content"][1]["image_url"]["detail"] = "low"
    add("lost-image-detail", changed, baseline=vision)
    unknown = [{"role": "user", "content": [{"type": "audio", "data": "opaque"}]}]
    add("unsupported-audio-abstention", unknown, "INCONCLUSIVE", unknown)
    invalid = deepcopy(base); invalid[1]["tool_call_id"] = "missing"
    add("invalid-baseline-abstention", deepcopy(invalid), "NEEDS_REVIEW", invalid)
    return result


def minimize(baseline, candidate, budget=100):
    """Remove matching message positions while retaining the same failure codes."""
    expected = {f["code"] for f in compare_messages(baseline, candidate)["findings"]}
    if compare_messages(baseline, candidate)["status"] != "FAIL":
        raise ValueError("Only confirmed failures can be minimized")
    before, after = deepcopy(baseline), deepcopy(candidate)
    attempts = 0
    for i in reversed(range(min(len(before), len(after)))):
        if attempts >= budget:
            break
        a, b = before[:i] + before[i+1:], after[:i] + after[i+1:]
        attempts += 1
        verdict = compare_messages(a, b)
        if verdict["status"] == "FAIL" and {f["code"] for f in verdict["findings"]} == expected:
            before, after = a, b
    return {"baseline": before, "candidate": after, "attempts": attempts, "scope": "message deletion only"}


def replay(messages):
    """Deterministic task simulator; no inference or external tool execution."""
    from .semantic import normalize, relationship_errors
    try:
        normalized = normalize(messages)
        if relationship_errors(normalized):
            return {"status": "FAIL", "reason": "Cannot associate tool results with requests", "kind": "deterministic task simulation"}
        import json
        calls = {c["id"]: c["name"] for m in normalized for c in m["tool_calls"]}
        outputs = {calls[m["tool_call_id"]]: json.loads("".join(p.get("text", "") for p in m["content"])) for m in normalized if m["role"] == "tool"}
        total = outputs["inventory"]["quantity"] * outputs["price"]["price"]
        return {"status": "PASS" if total == 21 else "FAIL", "inventory_value": total, "kind": "deterministic task simulation"}
    except (KeyError, ValueError, TypeError):
        return {"status": "INCONCLUSIVE", "reason": "Not the inventory task protocol", "kind": "deterministic task simulation"}
