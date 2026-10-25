"""One evidence pipeline for the local product and future live experiments."""
from collections import Counter
from pathlib import Path
import shutil
import time
import uuid
from .evidence import digest, environment, now, write_json
from .counterexamples import cases, minimize
from .semantic import compare_messages
from .reproductions import run_reproductions, SOURCES, patch_diff
from .knowledge import KnowledgeStore


LIMITATIONS = [
    "No Nebius/Nemotron or Tavily credentials: no live model or search claims.",
    "Historical reproductions execute hash-pinned upstream functions with inert SDK stubs; full SDK environments are not validated.",
    "NVIDIA snapshot is an upstream blob, not a verified release wheel; CrewAI snapshot comes from tag 1.15.28.",
    "Task recovery is a deterministic tool-protocol simulation, not a stochastic model outcome.",
    "Repair candidates are reviewed deterministic patches, not Nemotron-generated.",
    "The runner does not execute arbitrary repositories or model-generated Python; container execution is not implemented.",
    "Local knowledge is integrity-checked, not cryptographically authenticated against malicious writers.",
]


def acceptance_gates(report):
    by_id = {c["id"]: c for c in report["cases"]}
    repairs = [c for c in report["cases"] if "repair" in c]
    controls = [c for c in report["cases"] if c.get("expected_status") == "PASS"]
    gates = [
        (1, "Real NVIDIA inference through Nebius", "BLOCKED", "No credentials supplied"),
        (2, "Product end to end", "PASS", "Offline detection, reproduction, repair verification, reports and viewer; live path excluded"),
        (3, "Authentic compatibility defect", "PASS" if by_id.get("crewai-8434", {}).get("status") == "FAIL" else "FAIL", "Pinned upstream source-boundary reproduction; full SDK remains unverified"),
        (4, "Nemotron-generated test executes", "BLOCKED", "No real inference"),
        (5, "Repair independently verified", "PASS" if repairs and all(c.get("repair", {}).get("status") == "VERIFIED" for c in repairs) else "INCONCLUSIVE" if not repairs else "FAIL", "Fixed deterministic assertions and negative controls; source-boundary scope"),
        (6, "Normal behavior controls", "PASS" if controls and all(c["status"] == "PASS" for c in controls) else "INCONCLUSIVE" if not controls else "FAIL", "See recorded control cases"),
        (7, "ASM save and reuse", "PASS" if report["knowledge"]["reused"] else "FAIL", "Exact source/version/environment key; contract rerun"),
        (8, "Documented CLI", "INCONCLUSIVE", "See TESTING.md for separately executed CLI smoke checks"),
        (9, "Evidence demo interface", "INCONCLUSIVE", "Static evidence viewer; browser verification recorded separately"),
        (10, "Real reliability experiments", "BLOCKED", "Live credentials unavailable"),
        (11, "Reproducible platform feedback", "BLOCKED", "No observed platform findings; preparation is not feedback evidence"),
        (12, "English Devpost materials", "INCONCLUSIVE", "Draft prepared; authenticated form not inspected"),
        (13, "Demo video", "BLOCKED", "Script prepared; real video recording and public YouTube URL missing"),
        (14, "Public judge-accessible release", "BLOCKED", "Local build only until branch/release publication confirmed"),
        (15, "No exposed credentials", "INCONCLUSIVE", "Redaction tested; release scan required"),
        (16, "Official requirements checked", "PASS", "COMPETITION_AUDIT.md; entrant eligibility and private fields remain unverified"),
    ]
    return [{"id": n, "title": title, "status": status, "evidence": evidence} for n, title, status, evidence in gates]


def make_report(case_results):
    counts = Counter(c["status"].lower() for c in case_results)
    return {"schema_version": "1.0", "run_id": str(uuid.uuid4()), "created_at": now(), "mode": "offline", "environment": environment(), "summary": {k: counts[k] for k in ("pass", "fail", "inconclusive", "needs_review")}, "cases": case_results, "knowledge": {}, "lab": {"status": "BLOCKED", "live_requests": 0, "reason": "No Nebius credentials; mocked client tests are not platform experiments"}, "limitations": LIMITATIONS}


def export_report(report, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    report = write_json(output / "report.json", report)
    shutil.copyfile(Path(__file__).parent / "web" / "index.html", output / "index.html")
    lines = ["# PatchCourt compatibility evidence", "", f"Run: {report['run_id']}", f"Recorded: {report['created_at']}", f"Mode: {report['mode']}", "", "| Case | Verdict | Evidence |", "|---|---|---|"]
    for c in report["cases"]:
        lines.append(f"| {c['id']} | {c['status']} | {c.get('provenance', '')!s} |")
    lines.extend(["", "## Limitations", ""] + ["- " + x for x in report["limitations"]])
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_json(output / "manifest.json", {"report_sha256": digest(report), "run_id": report["run_id"], "note": "Integrity checksum is not independent certification"})
    return report


def demo(output, knowledge_dir=None):
    results = run_reproductions()
    for case in cases():
        start = time.perf_counter()
        verdict = compare_messages(case["baseline"], case["candidate"])
        results.append({**case, **verdict, "execution": True, "duration_ms": round((time.perf_counter()-start)*1000,3)})
    report = make_report(results)
    store = KnowledgeStore(knowledge_dir or Path(output) / "knowledge")
    identity = {"software": "langchain-nvidia-ai-endpoints", "version": SOURCES["nvidia"]["version"], "boundary": "convert_message_to_dict", "source_sha256": SOURCES["nvidia"]["sha256"], "environment": environment()}
    started = time.perf_counter()
    prior = store.lookup(identity)
    lookup_ms = (time.perf_counter()-started)*1000
    key = store.save(identity, {"status": results[0]["status"], "execution": True, "run_id": report["run_id"], "findings": results[0]["findings"], "scope": "upstream function with inert SDK types"})
    reused = store.lookup(identity)
    report["knowledge"] = {"record_id": key, "prior_run_hit": bool(prior), "reused": bool(reused), "lookup_ms": round(lookup_ms,3), "verification_skipped": False, "benefit": "retrieves scoped prior evidence; no model token savings measured"}
    report["acceptance_gates"] = acceptance_gates(report)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "ASM-ChatNVIDIA.md").write_text(store.export_markdown(identity), encoding="utf-8")
    write_json(output / "minimal-counterexample.json", minimize(results[0]["baseline"], results[0]["candidate"]))
    for name in SOURCES:
        (output / (name + "-repair.diff")).write_text(patch_diff(name), encoding="utf-8")
    # Standalone unittest file: imports only installed PatchCourt, no provider credentials.
    (output / "test_regression.py").write_text('import unittest\nfrom patchcourt.reproductions import run_reproductions\n\nclass Regression(unittest.TestCase):\n    def test_repairs(self):\n        for case in run_reproductions():\n            self.assertEqual(case["status"], "FAIL", case["id"])\n            self.assertEqual(case["repair"]["status"], "VERIFIED", case["id"])\n\nif __name__ == "__main__":\n    unittest.main()\n', encoding="utf-8")
    return export_report(report, output)


def benchmark(output):
    """Publish every scheduled arm; unavailable model arms remain blocked."""
    rows = []
    for case in cases():
        for arm in ("A-simple-deterministic", "B-original-ACV", "C-Nemotron", "D-Nemotron-Tavily", "E-ASM"):
            started = time.perf_counter()
            if arm == "A-simple-deterministic":
                verdict = compare_messages(case["baseline"], case["candidate"])["status"]
                row = {"outcome": verdict, "executed": True}
            elif arm == "E-ASM":
                row = {"outcome": "INCONCLUSIVE", "executed": False, "reason": "Knowledge lookup is not an independent classifier; only demo reuse measured"}
            else:
                row = {"outcome": "BLOCKED", "executed": False, "reason": "Offline benchmark never makes API calls; use --provider glm for the explicit development comparison"}
            rows.append({"case": case["id"], "provenance": case["provenance"], "arm": arm, "expected": case["expected_status"], **row, "duration_ms": round((time.perf_counter()-started)*1000,3), "tokens": 0 if arm == "A-simple-deterministic" else None, "cost_usd": 0 if arm == "A-simple-deterministic" else None})
    executed = [r for r in rows if r["executed"]]
    metrics = {"true_positives": sum(r["expected"] == r["outcome"] == "FAIL" for r in executed), "false_positives": sum(r["expected"] == "PASS" and r["outcome"] == "FAIL" for r in executed), "false_negatives": sum(r["expected"] == "FAIL" and r["outcome"] != "FAIL" for r in executed), "true_negatives": sum(r["expected"] == r["outcome"] == "PASS" for r in executed), "correct_abstentions": sum(r["expected"] in {"INCONCLUSIVE", "NEEDS_REVIEW"} and r["outcome"] == r["expected"] for r in executed)}
    result = {"created_at": now(), "environment": environment(), "rows": rows, "metrics": {"A": metrics}, "limitations": ["Developer-authored controlled cases; not a blinded benchmark.", "No comparative model effectiveness or cost claim is supported.", "All scheduled unavailable outcomes are retained."]}
    write_json(Path(output) / "benchmark.json", result)
    return result
