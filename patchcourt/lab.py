"""Repeatable provider contract probes; failures and missing gates are evidence.

These synthetic protocol probes establish only their narrow observed behavior.
They are not historical incompatibility discoveries or benchmark claims.
"""
from __future__ import annotations

import json
import math
import os
import statistics
from pathlib import Path

from . import providers
from .counterexamples import tool_conversation
from .evidence import now, write_json, environment, strict_json
from .reasoning import run_reasoning
from .semantic import reconstruct_stream

PROBES = ("structured_json", "tool_call", "streaming", "invalid_model_error")
INVALID_MODEL = "patchcourt-intentionally-nonexistent-model"
TOKEN_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["ok"],
                "properties": {"ok": {"type": "boolean"}}}


def _payload(model, probe):
    if probe not in PROBES:
        raise ValueError("Unknown reliability probe")
    payload = {"model": model, "temperature": 0, "max_tokens": 256,
               "messages": [{"role": "user", "content": 'Return exactly {"ok":true}.'}]}
    if probe == "structured_json":
        payload["response_format"] = {"type": "json_schema", "json_schema": {
            "name": "probe", "strict": True, "schema": TOKEN_SCHEMA}}
    elif probe == "tool_call":
        payload["messages"][0]["content"] = "Call report with ok=true."
        payload["tools"] = [{"type": "function", "function": {
            "name": "report", "description": "Report whether the probe is ready", "parameters": TOKEN_SCHEMA}}]
        payload["tool_choice"] = {"type": "function", "function": {"name": "report"}}
    elif probe == "streaming":
        payload["stream"] = True
        payload["stream_options"] = {"include_usage": True}
    elif probe == "invalid_model_error":
        payload["model"] = INVALID_MODEL
    return payload


def _check(probe, record, model=None):
    if probe not in PROBES:
        return "FAIL", "Unknown reliability probe"
    if record["status"] == "BLOCKED":
        return "BLOCKED", record.get("reason", "Missing gate")
    if record.get("provider", "nebius") != "nebius":
        return "FAIL", "Reliability lab requires the Nebius provider"
    if probe == "invalid_model_error":
        # An auth failure, timeout or generic 5xx does not demonstrate model validation.
        if record.get("status") != "FAIL" or record.get("http_status") not in {400, 404, 422}:
            return "FAIL", "Expected a model validation HTTP 400/404/422"
        parameters = record.get("parameters")
        if isinstance(parameters, dict) and parameters.get("model") != INVALID_MODEL:
            return "FAIL", "Negative control did not request the intentionally nonexistent model"
        try:
            error = strict_json(record.get("raw_response", ""))
            detail = error.get("error", error.get("detail")) if isinstance(error, dict) else None
            if not detail or "model" not in json.dumps(detail).lower():
                raise ValueError("Missing model-specific error detail")
        except (ValueError, TypeError):
            return "FAIL", "Expected a structured model-specific error"
        return "PASS", "Invalid model rejected with a structured error"
    if record["status"] != "PASS":
        return record["status"], record.get("reason", "Provider request failed")
    try:
        parameters = record.get("parameters")
        expected = model if model is not None else parameters.get("model") if isinstance(parameters, dict) else None
        if expected is None:
            raise ValueError("Missing requested model identity")
        expected = providers.select_model("nebius", expected, require_nemotron=True)
        if isinstance(parameters, dict) and parameters.get("model") != expected:
            raise ValueError("Recorded requested model differs from the selected model")
        body = record["response"]
        if probe == "streaming":
            if body.get("done") is not True:
                raise ValueError("Missing stream terminator")
            events = body["events"]
            if not isinstance(events, list) or not events:
                raise ValueError("Missing streaming events")
            for event in events:
                if not isinstance(event, dict):
                    raise ValueError("Invalid streaming event")
                providers.validate_response_model("nebius", expected, event.get("model"))
            first = events[0].get("choices")
            if not isinstance(first, list) or len(first) != 1 or not isinstance(first[0], dict):
                raise ValueError("Missing initial assistant stream choice")
            delta = first[0].get("delta")
            if not isinstance(delta, dict) or delta.get("role") != "assistant":
                raise ValueError("Streaming response must start with an explicit assistant role")
            message = reconstruct_stream(events)
            value = strict_json(message["content"])
            if message.get("tool_calls") or value != {"ok": True} or type(value["ok"]) is not bool:
                raise ValueError("Stream reassembly or finish reason failed")
        else:
            providers.validate_response_model("nebius", expected, body.get("model"))
            message = providers.validate_assistant_choice(body, allow_tools=probe == "tool_call")
            if probe == "structured_json":
                value = strict_json(message["content"])
                if value != {"ok": True} or type(value["ok"]) is not bool:
                    raise ValueError("Output violates the requested schema or content")
            elif probe == "tool_call":
                calls = message["tool_calls"]
                if len(calls) != 1:
                    raise ValueError("Expected exactly one completed tool call")
                call = calls[0]
                if not isinstance(call, dict) or set(call) - {"id", "type", "function", "index"}:
                    raise ValueError("Unsupported tool call fields")
                if "index" in call and (type(call["index"]) is not int or call["index"] != 0):
                    raise ValueError("Unexpected tool call index")
                if not isinstance(call.get("id"), str) or not call["id"] or call.get("type") != "function":
                    raise ValueError("Missing tool call identity")
                if not isinstance(call.get("function"), dict) or set(call["function"]) != {"name", "arguments"}:
                    raise ValueError("Unsupported function call fields")
                args = strict_json(call["function"]["arguments"])
                if call["function"]["name"] != "report" or args != {"ok": True} or type(args["ok"]) is not bool:
                    raise ValueError("Wrong tool name or arguments")
        return "PASS", "Observed the requested protocol contract with exact model identity: " + expected
    except (KeyError, IndexError, TypeError, ValueError, AttributeError) as exc:
        return "FAIL", "Contract validation failed: " + str(exc)


def _summary(rows):
    result = {}
    for probe in PROBES:
        group = [r for r in rows if r["probe"] == probe]
        measured = [r["request"]["latency_ms"] for r in group
                    if type(r["request"].get("latency_ms")) in (int, float)
                    and r["request"]["latency_ms"] >= 0 and math.isfinite(r["request"]["latency_ms"])]
        executed = [r for r in group if r["status"] != "BLOCKED"]
        passes = sum(r["status"] == "PASS" for r in executed)
        result[probe] = {"planned": len(group), "executed": len(executed), "passed": passes,
                         "failed": sum(r["status"] == "FAIL" for r in executed),
                         "blocked": len(group) - len(executed),
                         "pass_rate": passes / len(executed) if executed else None,
                         "median_latency_ms": statistics.median(measured) if measured else None}
    return result


def _ablation(model):
    source = "An adapter copies assistant content but may omit tool_calls and tool_call_id."
    evidence = {"baseline": tool_conversation(), "question": "Which declarative message tests detect tool linkage loss?"}
    without = run_reasoning(source, evidence, use_tavily=False, model=model)
    with_docs = run_reasoning(source, evidence, use_tavily=True, model=model)
    complete = all(r["status"] == "PASS" for r in (without, with_docs))
    def metrics(run):
        cases = run.get("case_results", [])
        return {"valid_cases": len(cases), "matched_expectations": sum(bool(c["expectation_matched"]) for c in cases),
                "confirmed_failure_cases": sum(c["verdict"]["status"] == "FAIL" for c in cases),
                "verified_citations": len(run.get("proposal", {}).get("citations", []))}
    return {"status": "PASS" if complete else "FAIL" if any(r["status"] == "FAIL" for r in (without, with_docs)) else "BLOCKED" if any(r["status"] == "BLOCKED" for r in (without, with_docs)) else "INCONCLUSIVE",
            "design": "Paired same-model, same-source, same-evidence proposal generation; only official-document retrieval differs",
            "without_tavily": without, "with_tavily": with_docs,
            "metrics": {"without_tavily": metrics(without), "with_tavily": metrics(with_docs)} if complete else None,
            "interpretation": "One paired descriptive comparison; no statistical or causal improvement claim"}


def run_lab(output_dir, model=None, trials=3) -> dict:
    if type(trials) is not int or not 1 <= trials <= 5:
        raise ValueError("trials must be an integer from 1 through 5")
    # This gate precedes discovery or inference. The intentionally nonexistent
    # model is confined to its explicit negative-control request below.
    selected = providers.select_model("nebius", model, require_nemotron=True)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    # Refuse accidental overwrite so failed and previous runs remain reviewable.
    report_path = output / "report.json"
    if report_path.exists() or (output / "trials").exists():
        raise ValueError("Lab output already contains a run; choose a new output directory")
    try:
        discovery = providers.discover_models()
    except (OSError, ValueError, TypeError) as exc:
        discovery = {"status": "FAIL", "models": [], "nemotron_models": [],
                     "reason": type(exc).__name__ + ": " + str(exc), "provenance": "Discovery raised; no successful response"}
    discovered = discovery.get("models", [])
    candidates = sorted(m for m in discovered if providers.is_nvidia_nemotron(m)) if isinstance(discovered, list) else []
    if selected is None and candidates:
        selected = providers.select_model("nebius", candidates[0], require_nemotron=True)
    blocked_reason = None
    if discovery["status"] != "PASS":
        blocked_reason = discovery.get("reason", "Model discovery failed")
    elif not selected:
        blocked_reason = "No discovered Nemotron model; choose a model from model discovery"
    elif not isinstance(discovered, list) or selected not in discovered:
        blocked_reason = "Selected model was not returned by provider discovery"
    report = {"schema_version": 1, "kind": "live provider reliability lab", "created_at": now(),
              "status": "RUNNING", "environment": environment(), "provider": "nebius", "selected_model": selected,
              "nemotron_selected": providers.is_nvidia_nemotron(selected),
              "identity_policy": "Positive probes require the exact discovered NVIDIA Nemotron model in every completion and stream event. The invalid-model probe is an explicit HTTP error negative control.",
              "discovery": discovery, "trials": [], "ablation": None, "summary": {},
              "budget": {"maximum_http_calls": 1 + 4 * trials + 3, "maximum_output_tokens": 4 * trials * 256 + 4096,
                         "per_request_timeout_seconds": providers.TIMEOUT, "retries": 0},
              "cost_usd": None, "cost_note": "Unknown; provider usage recorded without invented pricing",
              "scope": "Synthetic protocol observations only; no universal model compatibility or production reliability claim"}
    report["credential_gates"] = {name: {"status": "PRESENT" if os.environ.get(env, "").strip() else "BLOCKED",
                                        "variable": env}
                                  for name, env in (("nebius", "NEBIUS_API_KEY"), ("tavily", "TAVILY_API_KEY"))}
    write_json(report_path, report)
    for probe in PROBES:
        for attempt in range(1, trials + 1):
            if blocked_reason:
                record = {"status": "BLOCKED", "reason": blocked_reason, "provenance": "not executed",
                          "latency_ms": None, "usage": None, "cost_usd": None}
            else:
                try:
                    record = providers.request("nebius", _payload(selected, probe))
                except (OSError, ValueError, TypeError) as exc:
                    record = {"provider": "nebius", "status": "FAIL", "reason": type(exc).__name__ + ": " + str(exc),
                              "provenance": "Request raised; no successful response", "http_status": None,
                              "latency_ms": None, "usage": None}
            status, reason = _check(probe, record, model=selected)
            row = {"probe": probe, "attempt": attempt, "model": selected, "parameters": _payload(selected, probe),
                   "status": status, "reason": reason, "request": record}
            write_json(output / "trials" / f"{probe}-{attempt}.json", row)
            report["trials"].append(row)
            write_json(report_path, report)
    report["ablation"] = {"status": "BLOCKED", "reason": blocked_reason} if blocked_reason else _ablation(selected)
    report["summary"] = _summary(report["trials"])
    states = {r["status"] for r in report["trials"]} | {report["ablation"]["status"]}
    report["status"] = "FAIL" if "FAIL" in states else "BLOCKED" if "BLOCKED" in states else "INCONCLUSIVE" if states - {"PASS"} else "PASS"
    report["completed_at"] = now()
    return write_json(report_path, report)
