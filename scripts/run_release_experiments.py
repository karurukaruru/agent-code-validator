"""Explicit, budgeted release experiments. Never print or persist credentials."""
import argparse
import json
from pathlib import Path

from patchcourt.budget import RequestBudget
from patchcourt.credentials import load_local_credentials
from patchcourt.evidence import now, sanitize, write_json


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("live", "evaluation", "lab", "reason"))
    parser.add_argument("--provider", choices=("deepseek", "nebius"), required=True)
    parser.add_argument("--model")
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--budget", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--knowledge-dir", type=Path)
    parser.add_argument("--trials", type=int, default=2)
    parser.add_argument("--tavily", action="store_true")
    args = parser.parse_args(argv)
    output_available = False
    try:
        if args.output.exists() and (not args.output.is_dir() or any(args.output.iterdir())):
            raise ValueError("Use a new experiment output directory; prior records must be preserved")
        output_available = True
        load_local_credentials(args.env_file)
        budget = RequestBudget(args.budget)
        with budget.applied():
            result = execute(args)
    except (ValueError, OSError, TypeError, KeyError, IndexError, AttributeError) as exc:
        failure = sanitize({"status": "ERROR", "kind": "experiment runner failure", "created_at": now(),
                            "mode": args.mode, "provider": args.provider,
                            "reason": type(exc).__name__ + ": " + str(exc),
                            "scope": "Runner stopped; inspect any preserved child records. No success is inferred."})
        if output_available:
            try:
                write_json(args.output / "experiment-failure.json", failure)
            except OSError:
                failure["failure_record"] = "Could not persist runner failure; prior request reservations remain in the budget ledger"
        print(json.dumps(failure))
        return 2
    counts = {kind: sum(row["kind"] == kind for row in budget.state["reservations"])
              for kind in budget.state["limits"]}
    print(json.dumps({"status": result.get("status"), "provider": args.provider,
                      "output": str(args.output.resolve()), "budget_reservations": counts,
                      "total_reported_tokens": result.get("total_reported_tokens")}))
    return 0 if result.get("status") in {"PASS", "COMPLETE"} else 2


def execute(args):
    if args.mode == "live":
        from patchcourt.live_workflow import run_live_workflow
        return run_live_workflow(args.output, provider=args.provider, model=args.model,
                                 use_tavily=args.tavily, knowledge_dir=args.knowledge_dir)
    if args.mode == "evaluation":
        from patchcourt.release_evaluation import run_evaluation
        return run_evaluation(args.output, provider=args.provider, model=args.model, trials=args.trials, use_tavily=args.tavily)
    if args.mode == "lab":
        if args.provider != "nebius":
            raise ValueError("Competition reliability lab requires actual Nebius access")
        from patchcourt.lab import run_lab
        return run_lab(args.output, model=args.model, trials=args.trials)
    from patchcourt.reasoning import run_reasoning
    from patchcourt.reproductions import source
    from patchcourt.counterexamples import tool_conversation
    args.output.mkdir(parents=True, exist_ok=True)
    result = run_reasoning(source("nvidia"), {"original_input": tool_conversation(),
                                             "question": "Inspect the adapter for semantic loss; propose supported controls and counterexamples."},
                           provider=args.provider, model=args.model, use_tavily=args.tavily)
    write_json(args.output / "reasoning.json", result)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
