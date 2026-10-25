"""Record offline boundary matrix evidence. Optional SDK target must be trusted."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from patchcourt.boundary_run import run_boundary
from patchcourt.evidence import now, write_json


def inventory_oracle(output):
    """Concrete fixture expectations, independent of the semantic comparator."""
    try:
        calls = output[0]["tool_calls"]
        return (len(output) == 3 and output[0]["role"] == "assistant"
                and output[0]["content"] in (None, "") and len(calls) == 2
                and calls[0]["id"] == "call_a" and calls[1]["id"] == "call_b"
                and all(c["type"] == "function" for c in calls)
                and calls[0]["function"]["name"] == "inventory"
                and json.loads(calls[0]["function"]["arguments"]) == {"sku": "A", "options": {"warehouse": 2}}
                and calls[1]["function"]["name"] == "price"
                and json.loads(calls[1]["function"]["arguments"]) == {"sku": "A"}
                and output[1] == {"role": "tool", "tool_call_id": "call_a", "content": '{"quantity":3}'}
                and output[2] == {"role": "tool", "tool_call_id": "call_b", "content": '{"price":7}'})
    except (KeyError, TypeError, IndexError, ValueError):
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--sdk-root")
    args = parser.parse_args()
    root = Path(args.output); root.mkdir(parents=True, exist_ok=False)
    specs = [
        ("source-regression", "reviewed-patch", "upstream", "FAIL", None, None),
        ("source-healthy", "reviewed-patch", "reviewed-patch", "PASS", None, None),
        ("source-recovery", "upstream", "reviewed-patch", "NEEDS_REVIEW", None, None),
        ("source-both-broken", "upstream", "upstream", "NEEDS_REVIEW", None, None),
        ("source-text", "reviewed-patch", "upstream", "PASS", None, [{"role": "user", "content": "hello"}]),
    ]
    if args.sdk_root:
        specs += [
            ("sdk-regression", "reviewed-patch", "upstream", "FAIL", args.sdk_root, None),
            ("sdk-healthy", "reviewed-patch", "reviewed-patch", "PASS", args.sdk_root, None),
            ("sdk-recovery", "upstream", "reviewed-patch", "NEEDS_REVIEW", args.sdk_root, None),
        ]
    rows = []
    for name, baseline, candidate, expected, sdk, messages in specs:
        result = run_boundary(root / name, baseline=baseline, candidate=candidate, sdk_root=sdk, messages=messages)
        independent = {}
        for side, variant in (("baseline", baseline), ("candidate", candidate)):
            output = result["executions"].get(side, {}).get("output")
            independent[side] = output == messages if messages is not None else inventory_oracle(output) == (variant == "reviewed-patch")
            independent[side] = independent[side] and result["executions"].get(side, {}).get("status") == "EXECUTED"
        rows.append({"name": name, "expected": expected, "actual": result["status"],
                     "independent_checks": independent,
                     "verified": result["status"] == expected and all(independent.values()), "run_id": result["run_id"]})
    status = "PASS" if all(row["verified"] for row in rows) else "FAIL"
    write_json(root / "matrix.json", {"status": status, "created_at": now(), "rows": rows, "provider_requests": 0,
                                      "scope": "Two reviewed serializer variants; expected fixture assertions are independent of semantic comparator. Not a version-upgrade or model benchmark."})
    print(json.dumps({"status": status, "scenarios": len(rows), "output": str(root.resolve()), "provider_requests": 0}))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
