"""Capture an executed SDK boundary and challenge its exported standalone gate.

No API is called. With --sdk-root, both serializer variants use verified real SDK
classes in isolated child processes. The reviewed patch remains explicitly named.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from patchcourt.boundary_run import run_boundary
from patchcourt.evidence import digest, now, read_json, write_json
from patchcourt.recorder import BoundaryRecorder


def verify(output, sdk_root=None):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    execution = run_boundary(output / "sdk-execution", baseline="upstream", candidate="reviewed-patch", sdk_root=sdk_root)
    workers = execution.get("executions", {})
    if (len(workers) != 2 or any(row.get("status") != "EXECUTED" or row.get("provider_requests") != 0
                               for row in workers.values())):
        raise ValueError("Both serializer workers must execute without provider calls")
    if sdk_root and any(row.get("provenance", {}).get("real_sdk_classes") is not True for row in workers.values()):
        raise ValueError("Expected actual installed SDK classes")
    recordings = {}
    for role, version in (("baseline", "1.4.3"), ("candidate", "1.4.3+reviewed-patch")):
        recorder = BoundaryRecorder("langchain-nvidia-ai-endpoints/convert_message_to_dict", version)
        recorder.record("framework_input", execution["input"], request_id="sdk-contract-1")
        recorder.record("adapter_output", workers[role]["output"], request_id="sdk-contract-1")
        path = output / (role + "-recording.json")
        saved = recorder.save(path)
        recordings[role] = {"path": path.name, "sha256": digest(saved),
                            "input_matches_executed_worker": saved["events"][0]["payload"] == execution["input"],
                            "output_matches_executed_worker": saved["events"][1]["payload"] == workers[role]["output"]}
    gate = output / "regression-gate"
    command = [sys.executable, "-m", "patchcourt", "check-recording", str(output / "baseline-recording.json"),
               "--output", str(gate)]
    generated = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=30)
    (output / "gate-export.log").write_text(generated.stdout + generated.stderr, encoding="utf-8")
    if generated.returncode != 1 or not (gate / "test_boundary_contract.py").is_file():
        raise ValueError("A detected broken recording must export a failing gate")
    # -I -S prevents editable installs, site-packages and user import paths from
    # helping the generated test. Only its exported runtime and stdlib can work.
    test = [sys.executable, "-I", "-S", "-m", "unittest", "discover", "-s", str(gate),
            "-p", "test_boundary_contract.py"]
    mutant = deepcopy(read_json(output / "candidate-recording.json"))
    mutant["events"][1]["payload"][0]["tool_calls"][0]["id"] = "deliberately-wrong-id"
    write_json(output / "mutant-recording.json", mutant)
    scenarios = (("observed-broken", None, 1), ("reviewed-patch", "candidate-recording.json", 0),
                 ("corrupted-patch", "mutant-recording.json", 1))
    results = []
    for name, candidate, expected in scenarios:
        clean = {k: v for k, v in os.environ.items() if k not in {
            "PATCHCOURT_CANDIDATE_TRACE", "PATCHCOURT_CANDIDATE_RECORDING", "PATCHCOURT_REQUEST_ID"}}
        if candidate:
            clean["PATCHCOURT_CANDIDATE_RECORDING"] = str(output / candidate)
        result = subprocess.run(test, cwd=output, env=clean, capture_output=True, text=True, timeout=30)
        (output / (name + ".log")).write_text(result.stdout + result.stderr, encoding="utf-8")
        reached_contract = ("Captured contract is not preserved" in result.stderr
                            and "SEMANTIC_CHANGE" in result.stderr) if expected else "Ran 1 test" in result.stderr and "\nOK" in result.stderr
        results.append({"scenario": name, "expected_exit_code": expected, "actual_exit_code": result.returncode,
                        "reached_expected_contract_assertion": reached_contract,
                        "passed": result.returncode == expected and reached_contract})
    report = {"status": "PASS" if all(row["passed"] for row in results) else "FAIL", "created_at": now(),
              "kind": "Executed boundary capture to standalone regression gate",
              "sdk_execution_report": "sdk-execution/report.json", "sdk_execution_report_sha256": digest(execution),
              "real_sdk_classes": bool(sdk_root), "recordings": recordings, "scenarios": results,
              "provider_requests": 0, "standalone_test_flags": ["-I", "-S"],
              "scope": "Actual reviewed serializer execution and its captured messages; future candidate records are data supplied to the gate, not SDK execution initiated by the gate. The repaired variant is a reviewed patch, not an upstream fixed release."}
    write_json(output / "matrix.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sdk-root", type=Path)
    args = parser.parse_args()
    report = verify(args.output, args.sdk_root)
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
