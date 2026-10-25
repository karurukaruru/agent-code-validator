"""Repeatable provider contract probes; failures and missing gates are evidence.

These synthetic protocol probes establish only their narrow observed behavior.
They are not historical incompatibility discoveries or benchmark claims.
"""
from __future__ import annotations

import json
import os
import statistics
from pathlib import Path

from . import providers
from .counterexamples import tool_conversation
from .evidence import now, write_json, environment, strict_json
from .reasoning import run_reasoning
from .semantic import reconstruct_stream

PROBES = ("structured_json", "tool_call", "streaming", "invalid_model_error")
TOKEN_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["ok"],
                "properties": {"ok": {"type": "boolean"}}}


def _payload(model, probe):
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
        payload["model"] = "patchcourt-intentionally-nonexistent-model"
    return payload


def _check(probe, record):
    if record["status"] == "BLOCKED":
        return "BLOCKED", record.get("reason", "Missing gate")
    if probe == "invalid_model_error":
        # An auth failure, timeout or generic 5xx does not demonstrate model validation.
        if record.get("http_status") not in {400, 404, 422}:
            return "FAIL", "Expected a model validation HTTP 400/404/422"
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
        body = record["response"]
        if probe == "streaming":
            if not body.get("done"):
                raise ValueError("Missing stream terminator")
            message = reconstruct_stream(body["events"])
            value = strict_json(message["content"])
            if message.get("tool_calls") or value != {"ok": True} or type(value["ok"]) is not bool:
                raise ValueError("Stream reassembly or finish reason failed")
        else:
            choice = body["choices"][0]
            message = choice["message"]
            if message.get("role") != "assistant":
                raise ValueError("Response role is not assistant")
            if probe == "structured_json":
                value = strict_json(message["content"])
                if choice.get("finish_reason") != "stop" or value != {"ok": True} or type(value["ok"]) is not bool:
                    raise ValueError("Output violates the requested schema or content")
            elif probe == "tool_call":
                calls = message["tool_calls"]
                if choice.get("finish_reason") != "tool_calls" or len(calls) != 1:
                    raise ValueError("Expected exactly one completed tool call")
                call = calls[0]
                if not isinstance(call.get("id"), str) or not call["id"] or call.get("type") != "function":
                    raise ValueError("Missing tool call identity")
                args = strict_json(call["function"]["arguments"])
                if call["function"]["name"] != "report" or args != {"ok": True} or type(args["ok"]) is not bool:
                    raise ValueError("Wrong tool name or arguments")
        return "PASS", "Observed the requested protocol contract"
    except (KeyError, IndexError, TypeError, ValueError, AttributeError) as exc:
        return "FAIL", "Contract validation failed: " + str(exc)


def _summary(rows):
    result = {}
    for probe in PROBES:
        group = [r for r in rows if r["probe"] == probe]
        measured = [r["request"]["latency_ms"] for r in group if r["request"].get("latency_ms") is not None]
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
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    # Refuse accidental overwrite so failed and previous runs remain reviewable.
    report_path = output / "report.json"
    if report_path.exists() or (output / "trials").exists():
        raise ValueError("Lab output already contains a run; choose a new output directory")
    discovery = providers.discover_models()
    selected = model or os.environ.get("NEBIUS_MODEL")
    if not selected and discovery.get("nemotron_models"):
        selected = discovery["nemotron_models"][0]
    blocked_reason = None
    if discovery["status"] != "PASS":
        blocked_reason = discovery.get("reason", "Model discovery failed")
    elif not selected:
        blocked_reason = "No discovered Nemotron model; choose a model from model discovery"
    elif selected not in discovery["models"]:
        blocked_reason = "Selected model was not returned by provider discovery"
    report = {"schema_version": 1, "kind": "live provider reliability lab", "created_at": now(),
              "status": "RUNNING", "environment": environment(), "selected_model": selected, "nemotron_selected": bool(selected and selected.lower().startswith("nvidia/") and "nemotron" in selected.lower()),
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
                record = providers.request("nebius", _payload(selected, probe))
            status, reason = _check(probe, record)
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
