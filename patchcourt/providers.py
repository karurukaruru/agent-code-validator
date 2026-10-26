"""Bounded, fixed-origin provider access. No retries or credential persistence.

API references: https://api.tokenfactory.nebius.com/docs and
https://docs.tavily.com/documentation/api-reference/endpoint/search
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from .evidence import now, sanitize, strict_json

NEBIUS_BASE = "https://api.tokenfactory.nebius.com/v1"
GLM_BASE = "https://open.bigmodel.cn/api/paas/v4"
GLM_MODEL = "glm-5.3-flash"
DEEPSEEK_BASE = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-flash"
# Explicitly verified official alias on 2026-10-25, never a fuzzy match.
DEEPSEEK_RESPONSE_MODELS = frozenset({DEEPSEEK_MODEL, "DeepSeek-V4.1-Flash-1017"})
INFERENCE_PROVIDERS = ("glm", "deepseek", "nebius")
TOKEN_LIMITS = {"glm": 8192, "deepseek": 8192, "nebius": 2048}
KEY_ENVIRONMENTS = {"nebius": "NEBIUS_API_KEY", "glm": "GLM_API_KEY",
                    "deepseek": "DEEPSEEK_API_KEY", "tavily": "TAVILY_API_KEY"}
TAVILY_URL = "https://api.tavily.com/search"
MAX_BYTES = 1_000_000
TIMEOUT = 30
OFFICIAL_DOMAINS = ("docs.python.org", "docs.langchain.com", "reference.langchain.com",
                    "docs.nvidia.com", "api-docs.deepseek.com", "docs.crewai.com")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def is_nvidia_nemotron(model):
    return isinstance(model, str) and model.lower().startswith("nvidia/") and "nemotron" in model.lower()


def select_model(provider, model=None, require_nemotron=False):
    """Resolve only an authorized fixed model or an explicit Nebius model ID.

    A None Nebius result means discovery is still required; this helper never
    performs HTTP and never silently substitutes a model.
    """
    if provider not in INFERENCE_PROVIDERS:
        raise ValueError("Unsupported inference provider")
    fixed = {"glm": GLM_MODEL, "deepseek": DEEPSEEK_MODEL}.get(provider)
    if fixed:
        if model is not None and model != fixed:
            raise ValueError("Only the explicitly authorized " + fixed + " model is enabled; no fallback")
        return fixed
    selected = model if model is not None else os.environ.get("NEBIUS_MODEL", "").strip() or None
    if selected is not None and (not isinstance(selected, str) or not selected.strip() or len(selected) > 200):
        raise ValueError("Invalid Nebius model ID")
    if selected is not None and require_nemotron and not is_nvidia_nemotron(selected):
        raise ValueError("The competition workflow requires an explicit nvidia/ Nemotron model on Nebius")
    return selected


def validate_response_model(provider, requested, returned):
    """Return auditable identity metadata only for exact or verified aliases."""
    select_model(provider, requested)
    if not isinstance(requested, str) or not isinstance(returned, str) or not returned:
        raise ValueError("Missing requested or returned model identity")
    accepted = returned == requested
    policy = "exact requested model"
    if provider == "deepseek":
        accepted = requested == DEEPSEEK_MODEL and returned in DEEPSEEK_RESPONSE_MODELS
        policy = "exact requested model or explicitly verified official DeepSeek version alias"
    if not accepted:
        raise ValueError("Response model differs from authorized " + requested)
    return {"requested_model": requested, "returned_model": returned, "policy": policy}


def validate_assistant_choice(body, allow_tools=False):
    """Validate one complete assistant response before dropping envelope fields."""
    if not isinstance(body, dict):
        raise ValueError("Invalid completion response object")
    choices = body.get("choices")
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
        raise ValueError("Expected exactly one completion choice")
    choice = choices[0]
    if "index" in choice and (type(choice["index"]) is not int or choice["index"] != 0):
        raise ValueError("Unexpected completion choice index")
    reason = choice.get("finish_reason")
    if reason not in {"stop", "tool_calls"}:
        raise ValueError("Incomplete model response")
    message = choice.get("message")
    if not isinstance(message, dict) or message.get("role") != "assistant":
        raise ValueError("Expected an assistant response role")
    if set(message) - {"role", "content", "tool_calls", "refusal", "reasoning_content"}:
        raise ValueError("Unsupported assistant response fields")
    if message.get("refusal") not in (None, ""):
        raise ValueError("Assistant refusal cannot be accepted as a successful response")
    if message.get("content") is not None and not isinstance(message["content"], str):
        raise ValueError("Expected text or null assistant content")
    if message.get("reasoning_content") is not None and not isinstance(message["reasoning_content"], str):
        raise ValueError("Invalid provider reasoning metadata")
    calls = message.get("tool_calls", [])
    if not isinstance(calls, list) or len(calls) > 4:
        raise ValueError("Invalid or unbounded assistant tool calls")
    if bool(calls) != (reason == "tool_calls"):
        raise ValueError("Completion finish reason disagrees with tool calls")
    if calls and not allow_tools:
        raise ValueError("Tool calls are not allowed for this text-only request")
    return message


def summarize_token_usage(records):
    """Count only reported nonnegative integers; missing usage remains unknown."""
    values = [r["usage"]["total_tokens"] for r in records if isinstance(r.get("usage"), dict)
              and type(r["usage"].get("total_tokens")) is int and r["usage"]["total_tokens"] >= 0]
    return {"total_reported_tokens": sum(values) if values else None,
            "requests_missing_token_usage": len(records) - len(values)}


def completion_payload(provider, messages, model=None, max_tokens=None, json_object=False, **extra):
    """Provider-specific bounded chat settings; no network or model fallback."""
    selected = select_model(provider, model)
    if selected is None:
        raise ValueError("Select a discovered Nebius model before inference")
    payload = {"model": selected, "messages": messages,
               "max_tokens": max_tokens if max_tokens is not None else (2048 if provider == "nebius" else 4096),
               "temperature": 1 if provider == "glm" else 0}
    if provider == "glm":
        payload["reasoning_effort"] = "low"
    if provider == "deepseek":
        payload["thinking"] = {"type": "disabled"}
    if json_object:
        payload["response_format"] = {"type": "json_object"}
    payload.update(extra)
    # Identity and DeepSeek's mode are invariants, even with caller overrides.
    if payload["model"] != selected or provider == "deepseek" and (payload.get("thinking") != {"type": "disabled"} or "reasoning_effort" in payload):
        raise ValueError("Provider model or thinking mode cannot be overridden")
    maximum = TOKEN_LIMITS[provider]
    if type(payload["max_tokens"]) is not int or not 1 <= payload["max_tokens"] <= maximum:
        raise ValueError(f"Each inference request requires max_tokens between 1 and {maximum}")
    return payload


def _transport(url, key, payload):
    """Single bounded request. Redirects never forward authorization."""
    allowed = {NEBIUS_BASE + "/models", NEBIUS_BASE + "/chat/completions", GLM_BASE + "/chat/completions", DEEPSEEK_BASE + "/chat/completions", TAVILY_URL}
    if url not in allowed:
        raise ValueError("Untrusted provider endpoint")
    data = None if payload is None else json.dumps(payload, allow_nan=False).encode()
    if data and len(data) > 128_000:
        raise ValueError("Request exceeds 128 KB")
    request = urllib.request.Request(url, data=data, headers={
        "Authorization": "Bearer " + key, "Content-Type": "application/json",
        "Accept": "text/event-stream" if payload and payload.get("stream") else "application/json",
    })
    opener = urllib.request.build_opener(NoRedirect())
    try:
        response = opener.open(request, timeout=TIMEOUT)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("Response exceeds 1 MB")
        return response.code, dict(response.headers), raw.decode("utf-8")


def parse_stream(raw):
    """Parse complete SSE events, rejecting truncation and provider errors."""
    events, done = [], False
    normalized = raw.replace("\r\n", "\n")
    for block in normalized.split("\n\n"):
        data = "\n".join(line[5:].lstrip() for line in block.splitlines() if line.startswith("data:"))
        if not data:
            continue
        if done:
            raise ValueError("Data after stream terminator")
        if data == "[DONE]":
            done = True
            continue
        event = strict_json(data)
        if not isinstance(event, dict) or event.get("error"):
            raise ValueError("Provider stream error")
        events.append(event)
    if not done or not events:
        raise ValueError("Incomplete stream: missing events or DONE")
    return {"events": events, "done": done}


def request(provider, payload=None, endpoint="chat/completions"):
    if provider not in KEY_ENVIRONMENTS:
        raise ValueError("Unsupported provider")
    if provider == "nebius" and endpoint not in {"models", "chat/completions"}:
        raise ValueError("Unsupported Nebius endpoint")
    if provider in {"glm", "deepseek"} and endpoint != "chat/completions":
        raise ValueError("Unsupported inference endpoint")
    env_name = KEY_ENVIRONMENTS[provider]
    key = os.environ.get(env_name, "").strip()
    url = {"nebius": NEBIUS_BASE + "/" + endpoint, "glm": GLM_BASE + "/chat/completions", "deepseek": DEEPSEEK_BASE + "/chat/completions", "tavily": TAVILY_URL}[provider]
    record = {"provider": provider, "endpoint": url, "timestamp": now(),
              "provenance": "not executed", "status": "BLOCKED", "http_status": None,
              "latency_ms": None, "usage": None, "cost_usd": None,
              "cost_note": "Unknown; no pricing assumption or zero-cost claim", "parameters": sanitize(payload)}
    if not key:
        return {**record, "reason": "Missing " + env_name}
    if provider in INFERENCE_PROVIDERS and endpoint == "chat/completions":
        maximum = TOKEN_LIMITS[provider]
        if not isinstance(payload, dict) or type(payload.get("max_tokens")) is not int or not 1 <= payload["max_tokens"] <= maximum:
            raise ValueError(f"Each inference request requires max_tokens between 1 and {maximum}")
        if provider in {"glm", "deepseek"}:
            select_model(provider, payload.get("model"))
            if payload.get("model") is None:
                raise ValueError("Explicit model is required")
        if provider == "deepseek" and (payload.get("thinking") != {"type": "disabled"} or "reasoning_effort" in payload):
            raise ValueError("DeepSeek bounded workflows require thinking.type disabled and no reasoning_effort")
    start = time.monotonic()
    record["provenance"] = "live HTTP attempt"
    try:
        status, headers, raw = _transport(url, key, payload)
        record.update(http_status=status, latency_ms=round((time.monotonic() - start) * 1000, 3))
        record["request_id"] = headers.get("x-request-id") or headers.get("X-Request-Id")
        record["raw_response"] = raw
        if not 200 <= status < 300:
            record.update(status="FAIL", reason="Provider HTTP error")
        else:
            body = parse_stream(raw) if payload and payload.get("stream") else strict_json(raw)
            if not isinstance(body, dict) or body.get("error"):
                raise ValueError("Invalid provider response object")
            record.update(status="PASS", response=body, usage=body.get("usage"))
            if "events" in body:
                if not payload or not payload.get("stream") or not isinstance(body["events"], list) or any(not isinstance(e, dict) for e in body["events"]):
                    raise ValueError("Invalid or unexpected streaming events")
                record["usage"] = next((e["usage"] for e in reversed(body["events"]) if e.get("usage")), None)
    except (urllib.error.URLError, OSError, ValueError, TypeError) as exc:
        record.update(status="FAIL", reason=type(exc).__name__ + ": " + str(exc),
                      latency_ms=round((time.monotonic() - start) * 1000, 3))
    # Redact even short explicitly configured keys, as well as standard secrets.
    def redact(value):
        if isinstance(value, str):
            return value.replace(key, "[REDACTED]")
        if isinstance(value, list):
            return [redact(v) for v in value]
        if isinstance(value, dict):
            return {redact(k): redact(v) for k, v in value.items()}
        return value
    return redact(sanitize(record))


def discover_models():
    record = request("nebius", endpoint="models")
    record["models"], record["nemotron_models"] = [], []
    if record["status"] == "PASS":
        items = record["response"].get("data")
        if not isinstance(items, list):
            record.update(status="FAIL", reason="Model discovery returned no data list")
        else:
            record["models"] = sorted({x["id"] for x in items if isinstance(x, dict) and isinstance(x.get("id"), str)})
            record["nemotron_models"] = [m for m in record["models"] if "nemotron" in m.lower()]
    return record


def search_docs(query=None, domains=None, max_results=3):
    """One basic search, with bounded snippets from allowlisted official hosts.

    Callers may supply a task-specific public-documentation query; never pass
    credentials or private source. The no-argument form remains compatible.
    Tavily basic search consumes one search credit; no automatic retry or fetch.
    A configured docs host and its DNS subdomains are accepted, never a suffix
    lookalike. Search snippets are external evidence, not executable instructions.
    """
    query = ("LangChain AIMessage tool_calls tool_call_id ToolMessage conversion function arguments"
             if query is None else query)
    if not isinstance(query, str) or not query.strip() or len(query) > 512:
        raise ValueError("Documentation query must be 1 to 512 characters")
    if type(max_results) is not int or not 1 <= max_results <= 3:
        raise ValueError("Documentation result limit must be 1 to 3")
    if domains is None:
        domains = OFFICIAL_DOMAINS
    if not isinstance(domains, (list, tuple)) or not domains or len(domains) > len(OFFICIAL_DOMAINS):
        raise ValueError("Provide a nonempty list of allowlisted official domains")
    if any(not isinstance(d, str) or d not in OFFICIAL_DOMAINS for d in domains):
        raise ValueError("Untrusted documentation domain")
    domains = tuple(dict.fromkeys(domains))
    record = request("tavily", {"query": query.strip(),
                                "include_domains": list(domains), "max_results": max_results,
                                "search_depth": "basic", "include_answer": False,
                                "include_raw_content": False, "include_usage": True})
    record["search_contract"] = {"search_depth": "basic", "search_credits_per_request": 1,
                                  "automatic_retries": 0, "allowed_domains": list(domains),
                                  "max_results": max_results, "max_snippet_characters": 4000}
    record["documents"] = []
    if record["status"] == "PASS":
        response = record.get("response")
        results = response.get("results") if isinstance(response, dict) else None
        if not isinstance(results, list):
            record.update(status="FAIL", reason="Search returned no result list")
            return record
        for item in results[:max_results]:
            if not isinstance(item, dict):
                continue
            url = item.get("url", "")
            if not isinstance(url, str) or len(url) > 2048 or any(c.isspace() or ord(c) < 32 or ord(c) == 127 or c == "\\" for c in url):
                continue
            try:
                parsed = urllib.parse.urlsplit(url)
                host = parsed.hostname or ""
                valid_dns = host.isascii() and len(host) <= 253 and all(
                    1 <= len(label) <= 63 and label[0].isalnum() and label[-1].isalnum()
                    and all(c.isalnum() or c == "-" for c in label) for label in host.split("."))
                trusted = valid_dns and any(host == d or host.endswith("." + d) for d in domains)
                safe = parsed.scheme == "https" and trusted and parsed.username is None and parsed.password is None and parsed.port in (None, 443)
            except ValueError:
                continue
            content, title = item.get("content", ""), item.get("title", "")
            if safe and isinstance(content, str) and content.strip() and isinstance(title, str):
                record["documents"].append({"url": url, "title": title[:300], "content": content[:4000]})
        if not record["documents"]:
            record.update(status="INCONCLUSIVE", reason="No allowlisted official documentation returned")
    return record
