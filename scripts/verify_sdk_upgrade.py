"""Execute the controlled SDK upgrade, negative control, regression and recovery.

--prepare explicitly permits official wheel installation (or a local wheelhouse).
No model/provider API is called. All scheduled outcomes are retained.
"""
import argparse
import json
from pathlib import Path

from patchcourt.boundary_run import run_boundary
from patchcourt.evidence import digest, read_json, write_json
from patchcourt.upgrade_run import run_upgrade


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--wheelhouse", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    repository = args.output / "sample-agent"
    repository.mkdir()
    (repository / "requirements.txt").write_text("langchain-nvidia-ai-endpoints==1.4.3\n", encoding="utf-8")
    (repository / "agent.py").write_text("# convert_message_to_dict consumes AIMessage.tool_calls here\n", encoding="utf-8")
    rows = []
    def record(name, expected, run):
        try:
            report = run()
            saved = read_json(args.output / name / "report.json")
            manifest = read_json(args.output / name / "manifest.json")
            integral = digest(saved) == manifest["report_sha256"] and saved["run_id"] == manifest["run_id"]
            runs = report.get("executions", {})
            executed = bool(runs) and all(r.get("status") == "EXECUTED" and r.get("provider_requests") == 0
                                          and r["provenance"].get("real_sdk_classes") is True for r in runs.values())
            case = report["cases"][0]
            recovered = (case.get("task_replay", {}).get("after", {}).get("inventory_value") == 21
                         if name == "recovery" else True)
            row = {"scenario": name, "expected": expected, "actual": report["status"],
                   "integrity": integral, "real_sdk_workers": executed, "recovery": recovered,
                   "passed": report["status"] == expected and integral and executed and recovered}
        except Exception as exc:
            row = {"scenario": name, "expected": expected, "actual": "ERROR", "error": type(exc).__name__ + ": " + str(exc), "passed": False}
        rows.append(row)
        write_json(args.output / "matrix.json", {"status": "RUNNING", "rows": rows, "provider_requests": 0})
    common = dict(baseline="1.4.3", candidate="1.5.0", environment_dir=args.environment_dir)
    record("upgrade", "NEEDS_REVIEW", lambda: run_upgrade(repository, args.output / "upgrade", **common,
                                                           prepare=args.prepare, wheelhouse=args.wheelhouse))
    record("text-control", "PASS", lambda: run_upgrade(repository, args.output / "text-control", **common,
                                                        messages=[{"role": "system", "content": "Be concise"},
                                                                  {"role": "user", "content": "hello"},
                                                                  {"role": "assistant", "content": "world"}]))
    sdk = args.environment_dir / "nvidia-1.4.3"
    record("regression", "FAIL", lambda: run_boundary(args.output / "regression", sdk_root=sdk))
    record("recovery", "NEEDS_REVIEW", lambda: run_boundary(args.output / "recovery", sdk_root=sdk,
                                                              baseline="upstream", candidate="reviewed-patch"))
    result = {"status": "PASS" if all(r["passed"] for r in rows) else "FAIL", "rows": rows, "provider_requests": 0,
              "scope": "Four controlled installed-SDK serializer scenarios; no model inference or full agent application execution"}
    write_json(args.output / "matrix.json", result)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
