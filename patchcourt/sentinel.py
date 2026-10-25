"""Read-only upgrade discovery built on ACV's bounded project inspection."""
from pathlib import Path
import re
import time
from acv.agent_tools import ProjectTools
from acv.scanner import _is_link_like
from .semantic import compare_messages

FRAMEWORKS = ("langchain-nvidia-ai-endpoints", "langchain-core", "crewai", "openai", "anthropic", "google-genai", "langgraph")
_UNSET = object()


def inspect_repository(root, dependency, baseline_version, candidate_version):
    tools = ProjectTools(root)
    dependencies = []
    for name in ("pyproject.toml", "requirements.txt", "package.json", "uv.lock"):
        path = tools.root / name
        if path.exists() and not _is_link_like(path) and path.is_file() and path.stat().st_size <= 1_000_000:
            content = path.read_text(encoding="utf-8", errors="replace")
            for framework in FRAMEWORKS:
                if framework in content:
                    dependencies.append({"manifest": name, "framework": framework})
    # Reuse ACV path validation and bounded search; never import project code.
    boundaries = []
    for query in ("tool_calls", "image_url", "convert_message", "format_messages"):
        try:
            result = tools.search_code(query)
            boundaries.append({"query": query, "observation": result})
        except (ValueError, TypeError) as exc:
            boundaries.append({"query": query, "error": str(exc)})
    return {"dependency": dependency, "baseline_version": baseline_version, "candidate_version": candidate_version, "discovered_dependencies": dependencies, "boundary_candidates": boundaries, "status": "NEEDS_REVIEW", "reason": "Source matches identify inspection targets, not defects. Supply executed baseline/candidate traces for a verdict."}


def check_trace_pair(baseline, candidate, metadata=None, original_input=_UNSET):
    start = time.perf_counter()
    verdict = compare_messages(baseline, candidate)
    result = {"id": "upgrade-trace", "title": "Recorded upgrade boundary comparison", **verdict, "baseline": baseline, "candidate": candidate, "provenance": {**(metadata or {}), "kind": "user-supplied traces; execution provenance not independently established"}, "duration_ms": round((time.perf_counter()-start)*1000,3)}
    if original_input is _UNSET:
        return result
    valid = compare_messages(original_input, original_input)
    result["contracts"] = {"input": valid, "baseline": compare_messages(original_input, baseline),
                           "candidate": compare_messages(original_input, candidate), "difference": verdict}
    if valid["status"] != "PASS":
        result.update(valid)
    elif result["contracts"]["baseline"]["status"] != "PASS":
        result.update({"status": "NEEDS_REVIEW", "findings": [{"code": "UNHEALTHY_BASELINE", "message": "Baseline does not establish preservation of the original input; matching outputs cannot certify compatibility"}],
                       "direction": "candidate_restores_contract" if result["contracts"]["candidate"]["status"] == "PASS" else "candidate_uncertain"})
    else:
        result.update(result["contracts"]["candidate"])
    return result
