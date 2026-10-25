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
TAVILY_URL = "https://api.tavily.com/search"
MAX_BYTES = 1_000_000
TIMEOUT = 30
OFFICIAL_DOMAINS = ("docs.python.org", "docs.langchain.com", "reference.langchain.com")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _transport(url, key, payload):
    """Single bounded request. Redirects never forward authorization."""
    allowed = {NEBIUS_BASE + "/models", NEBIUS_BASE + "/chat/completions", GLM_BASE + "/chat/completions", TAVILY_URL}
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
    if provider not in {"nebius", "tavily", "glm"}:
        raise ValueError("Unsupported provider")
    if provider == "nebius" and endpoint not in {"models", "chat/completions"}:
        raise ValueError("Unsupported Nebius endpoint")
    if provider == "glm" and endpoint != "chat/completions":
        raise ValueError("Unsupported GLM endpoint")
    env_name = {"nebius": "NEBIUS_API_KEY", "glm": "GLM_API_KEY", "tavily": "TAVILY_API_KEY"}[provider]
    key = os.environ.get(env_name, "").strip()
    url = {"nebius": NEBIUS_BASE + "/" + endpoint, "glm": GLM_BASE + "/chat/completions", "tavily": TAVILY_URL}[provider]
    record = {"provider": provider, "endpoint": url, "timestamp": now(),
              "provenance": "not executed", "status": "BLOCKED", "http_status": None,
              "latency_ms": None, "usage": None, "cost_usd": None,
              "cost_note": "Unknown; no pricing assumption or zero-cost claim", "parameters": sanitize(payload)}
    if not key:
        return {**record, "reason": "Missing " + env_name}
    if provider in {"nebius", "glm"} and endpoint == "chat/completions":
        maximum = 8192 if provider == "glm" else 2048
        if not isinstance(payload, dict) or type(payload.get("max_tokens")) is not int or not 1 <= payload["max_tokens"] <= maximum:
            raise ValueError(f"Each inference request requires max_tokens between 1 and {maximum}")
        if provider == "glm" and payload.get("model") != GLM_MODEL:
            raise ValueError("Only the explicitly authorized glm-5.3-flash model is enabled; no fallback")
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


def search_docs():
    """Fixed query sends no user source or evidence to the search provider."""
    record = request("tavily", {"query": "LangChain AIMessage tool_calls tool_call_id ToolMessage conversion function arguments",
                                "include_domains": list(OFFICIAL_DOMAINS), "max_results": 3,
                                "search_depth": "basic", "include_answer": False,
                                "include_raw_content": False, "include_usage": True})
    record["documents"] = []
    if record["status"] == "PASS":
        results = record["response"].get("results")
        if not isinstance(results, list):
            record.update(status="FAIL", reason="Search returned no result list")
            return record
        for item in results[:3]:
            if not isinstance(item, dict):
                continue
            url = item.get("url", "")
            if not isinstance(url, str):
                continue
            try:
                parsed = urllib.parse.urlsplit(url)
            except ValueError:
                continue
            if parsed.scheme == "https" and parsed.hostname in OFFICIAL_DOMAINS and not parsed.username:
                record["documents"].append({"url": url, "title": str(item.get("title", ""))[:300],
                                            "content": str(item.get("content", ""))[:4000]})
        if not record["documents"]:
            record.update(status="INCONCLUSIVE", reason="No allowlisted official documentation returned")
    return record
