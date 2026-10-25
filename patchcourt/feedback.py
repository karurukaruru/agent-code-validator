"""Turn recorded lab observations into reviewable feedback, never invented bugs."""
from __future__ import annotations

import math
import json
import statistics
from pathlib import Path
from .evidence import digest, now, read_json, sanitize, write_json
from .providers import NEBIUS_BASE

CONTRACTS = {
    "structured_json": ("Structured-output contract", "Return exactly an object with boolean ok=true under the supplied JSON schema.", "Typed consumers must distinguish a boolean from text or numeric lookalikes.", "Clarify model-specific schema support and unsupported-keyword errors; if supported, rerun this exact schema probe."),
    "tool_call": ("Tool-call identity and arguments", "Return one completed report tool call with a non-empty ID and JSON boolean ok=true.", "Agent tools need stable call identifiers and valid arguments to associate results.", "Document forced-tool-choice behavior for the exact model and provide a round-trip example with matching tool results."),
    "streaming": ("Streaming reconstruction", "Complete SSE output with terminal markers reconstructs the requested JSON object.", "Truncation or lost deltas can corrupt typed agent state.", "Provide a tested streaming example including finish_reason, DONE and usage-only chunks; clarify truncation handling."),
    "invalid_model_error": ("Invalid-model error contract", "An intentionally nonexistent model returns a structured model-specific 400/404/422 error.", "Developers need actionable configuration errors rather than retrying invalid model IDs.", "Include a stable error code, requested model identifier and a link to model discovery in unsupported-model errors."),
}


def wilson(successes, total):
    """Descriptive 95% binomial interval; repeated model trials may not be independent."""
    if not total:
        return None
    z, rate = 1.959963984540054, successes / total
    scale = 1 + z*z/total
    center = (rate + z*z/(2*total)) / scale
    radius = z * math.sqrt(rate*(1-rate)/total + z*z/(4*total*total)) / scale
    return [max(0, center-radius), min(1, center+radius)]


def summarize(report):
    if report.get("kind") != "live provider reliability lab" or not isinstance(report.get("trials"), list):
        raise ValueError("Expected a PatchCourt lab report")
    groups = []
    for probe, (title, expectation, impact, recommendation) in CONTRACTS.items():
        planned = [r for r in report["trials"] if isinstance(r, dict) and r.get("probe") == probe]
        eligible, excluded = [], []
        for row in planned:
            request = row.get("request", {})
            genuine_scope = isinstance(request, dict) and request.get("provenance") == "live HTTP attempt" and request.get("provider") == "nebius" and request.get("endpoint") == NEBIUS_BASE + "/chat/completions" and type(request.get("http_status")) is int
            if genuine_scope and row.get("status") in {"PASS", "FAIL"}:
                eligible.append(row)
            else:
                excluded.append(row)
        passes = sum(r["status"] == "PASS" for r in eligible)
        failures = len(eligible) - passes
        latency = [r["request"]["latency_ms"] for r in eligible if type(r["request"].get("latency_ms")) in {int, float} and math.isfinite(r["request"]["latency_ms"]) and r["request"]["latency_ms"] >= 0]
        evidence = [{"attempt": r.get("attempt"), "status": r["status"], "reason": r.get("reason"), "http_status": r["request"]["http_status"], "request_id": r["request"].get("request_id"), "timestamp": r["request"].get("timestamp"), "parameters": r.get("parameters", r["request"].get("parameters")), "usage": r["request"].get("usage"), "trial_file": f"trials/{probe}-{r.get('attempt')}.json"} for r in eligible]
        classification = "BLOCKED_OR_UNVERIFIED" if not eligible else "OBSERVED_CONTRACT_FAILURE" if failures else "OBSERVED_SUCCESS"
        groups.append({"probe": probe, "title": title, "classification": classification, "planned": len(planned), "observed_http_trials": len(eligible), "passed": passes, "failed": failures, "excluded_or_blocked": len(excluded), "success_fraction": passes/len(eligible) if eligible else None, "descriptive_wilson_95": wilson(passes, len(eligible)), "median_latency_ms": statistics.median(latency) if latency else None, "expected": expectation, "developer_impact": impact, "recommendation_to_evaluate": recommendation, "acceptance_test": f"Rerun the {probe} probe with the same model and parameters; publish every attempt and confirm its contract. Do not use one passing trial as a reliability guarantee.", "evidence": evidence})
    return {"status": "DRAFT_REQUIRES_REVIEW" if any(g["observed_http_trials"] for g in groups) else "BLOCKED", "created_at": now(), "source_report_sha256": digest(report), "environment": report.get("environment"), "model": report.get("selected_model"), "endpoint": NEBIUS_BASE, "groups": groups, "cost_usd": None, "caveats": ["Producer-declared HTTP provenance is not independently authenticated by this renderer.", "A contract failure is not automatically a platform bug: inspect model support, request validity, account limits and harness behavior.", "Repeated same-model trials can be correlated; Wilson intervals are descriptive under independent-binomial assumptions, not a population reliability guarantee.", "No observed HTTP response means no positive or negative platform claim.", "Exact Devpost field and character limit remain unverified."]}


def render_feedback(run_directory, output_directory, max_chars=2000):
    if type(max_chars) is not int or not 500 <= max_chars <= 10000:
        raise ValueError("Field draft budget must be 500..10000 characters")
    report = read_json(Path(run_directory) / "report.json")
    summary = sanitize(summarize(report))
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    lines = ["# Nebius Reliability Lab — evidence-based feedback draft", "", "Status: " + summary["status"], "", "This draft requires human technical review and completion of the official feedback field.", "", "## Environment", "", "```json", json.dumps({"model":summary["model"],"endpoint":summary["endpoint"],"environment":summary["environment"],"source_report_sha256":summary["source_report_sha256"]},indent=2), "```", "", "## Raw counts", "", "| Probe | Planned | Observed HTTP | Pass | Fail | Excluded/blocked |", "|---|---:|---:|---:|---:|---:|"]
    for g in summary["groups"]:
        lines.append(f"| {g['probe']} | {g['planned']} | {g['observed_http_trials']} | {g['passed']} | {g['failed']} | {g['excluded_or_blocked']} |")
    for g in summary["groups"]:
        if not g["observed_http_trials"]:
            continue
        lines.extend(["", "## " + g["title"], "", "Classification: " + g["classification"] + " (not an automatic platform-bug conclusion).", "", "**Reproduction:** run the lab with the recorded model and exact per-trial parameters below. Keep a new output directory and all outcomes.", "", "**Expected:** " + g["expected"], "", f"**Actual:** {g['passed']} passing and {g['failed']} failing contracts in {g['observed_http_trials']} observed HTTP trials.", "", "**Impact:** " + g["developer_impact"], "", "**Recommendation to evaluate:** " + g["recommendation_to_evaluate"], "", "**Acceptance test:** " + g["acceptance_test"], "", "**Evidence:**"])
        for e in g["evidence"]:
            # Indented JSON remains data even if response text includes Markdown fences.
            lines.extend("    " + l for l in json.dumps(e, ensure_ascii=False, indent=2).splitlines())
        lines.extend(["", f"Median recorded request latency: {g['median_latency_ms']!s} ms. Descriptive interval: {g['descriptive_wilson_95']!s}."])
    if summary["status"] == "BLOCKED":
        lines.extend(["", "No authenticated HTTP observations are available. No platform findings, strengths, weaknesses or reliability rates can be asserted. Missing credentials are not a Nebius defect."])
        field = "PatchCourt's Nebius Reliability Lab is implemented, but this run contains no authenticated HTTP observations. We cannot yet claim NVIDIA/Nemotron runtime use, platform defects or measured reliability. Actual feedback requires legitimate API access and repeated recorded experiments."
    else:
        field = f"PatchCourt protocol experiments; model {summary['model']}, endpoint {summary['endpoint']}. "
        for g in summary["groups"]:
            if g["observed_http_trials"]:
                field += f"{g['probe']}: {g['passed']}/{g['observed_http_trials']} passed, {g['failed']} failed. "
        field += "These are narrow observations, not universal reliability estimates or automatic bug findings. See the linked reproducible report for parameters, request IDs, expected behavior, developer impact, recommendations and acceptance tests. Review model support and account/harness causes before attributing failures."
    lines.extend(["", "## Uncertainty and publication checks", ""] + ["- " + c for c in summary["caveats"]])
    (output / "feedback.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (output / "field-draft.txt").write_text(field[:max_chars] + "\n", encoding="utf-8")
    write_json(output / "feedback-summary.json", summary)
    return summary
