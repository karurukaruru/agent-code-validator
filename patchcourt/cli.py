"""Practical CLI, offline by default. Exit 1 means regression, 2 means uncertainty."""
import argparse
import json
import sys
from pathlib import Path
from .evidence import read_json, write_json


def main(argv=None):
    parser = argparse.ArgumentParser(prog="patchcourt", description="Catch silent AI agent compatibility regressions with executable evidence.")
    parser.add_argument("--version", action="version", version="PatchCourt 0.3.0")
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="Execute pinned source cases, repairs, controls and export the dashboard")
    demo.add_argument("--output", default="outputs/patchcourt")
    demo.add_argument("--knowledge-dir")
    check = commands.add_parser("check", help="Compare two captured message-array JSON files")
    check.add_argument("baseline"); check.add_argument("candidate")
    check.add_argument("--output", default="outputs/check")
    inspect = commands.add_parser("inspect", help="Find candidate adapter boundaries without executing repository code")
    inspect.add_argument("repository"); inspect.add_argument("--dependency", required=True)
    inspect.add_argument("--from-version", required=True); inspect.add_argument("--to-version", required=True)
    inspect.add_argument("--output", default="outputs/inspection.json")
    bench = commands.add_parser("benchmark", help="Record every scheduled ablation outcome")
    bench.add_argument("--output", default="outputs/benchmark")
    verify = commands.add_parser("verify", help="Check exported report integrity; does not certify truth")
    verify.add_argument("directory")
    feedback = commands.add_parser("feedback", help="Build a reviewable feedback draft from lab evidence; never infer platform defects")
    feedback.add_argument("run_directory")
    feedback.add_argument("--output", default="outputs/feedback")
    feedback.add_argument("--max-chars", type=int, default=2000)
    lab = commands.add_parser("lab", help="Run bounded real Nebius/Tavily trials; missing keys produce BLOCKED evidence")
    lab.add_argument("--output", default="outputs/lab"); lab.add_argument("--model"); lab.add_argument("--trials", type=int, default=3)
    reasoning = commands.add_parser("reason", help="Ask real Nemotron for declarative tests and a repair proposal")
    reasoning.add_argument("source"); reasoning.add_argument("evidence")
    reasoning.add_argument("--model"); reasoning.add_argument("--tavily", action="store_true"); reasoning.add_argument("--output", default="outputs/reasoning.json")
    serve = commands.add_parser("serve", help="Serve only exported static evidence on loopback; no code-execution endpoint")
    serve.add_argument("directory", nargs="?", default="outputs/patchcourt"); serve.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    try:
        if args.command == "demo":
            from .runner import demo
            report = demo(args.output, args.knowledge_dir)
            print(json.dumps({"output": str(Path(args.output).resolve()), "summary": report["summary"], "live_inference": False}))
            return 0 if all(c.get("expected_status", "FAIL") == c["status"] for c in report["cases"]) and all(c.get("repair", {}).get("status", "VERIFIED") == "VERIFIED" for c in report["cases"]) else 1
        if args.command == "check":
            from .sentinel import check_trace_pair
            from .runner import make_report, export_report
            case = check_trace_pair(read_json(args.baseline), read_json(args.candidate))
            export_report(make_report([case]), args.output)
            print(case["status"])
            return {"PASS": 0, "FAIL": 1}.get(case["status"], 2)
        if args.command == "inspect":
            from .sentinel import inspect_repository
            result = inspect_repository(args.repository, args.dependency, args.from_version, args.to_version)
            write_json(args.output, result)
            print("NEEDS_REVIEW: source boundaries recorded; execute and compare traces for a verdict")
            return 2
        if args.command == "benchmark":
            from .runner import benchmark
            result = benchmark(args.output)
            print(json.dumps(result["metrics"]))
            return 0
        if args.command == "verify":
            from .evidence import digest
            root = Path(args.directory)
            report, manifest = read_json(root / "report.json"), read_json(root / "manifest.json")
            valid = digest(report) == manifest.get("report_sha256") and report.get("run_id") == manifest.get("run_id")
            print("PASS: report integrity matches; provenance is not authenticated" if valid else "FAIL: report integrity mismatch")
            return 0 if valid else 1
        if args.command == "feedback":
            from .feedback import render_feedback
            result = render_feedback(args.run_directory, args.output, args.max_chars)
            print(json.dumps({"status": result["status"], "output": args.output}))
            return 2 if result["status"] == "BLOCKED" else 0
        if args.command == "lab":
            from .lab import run_lab
            result = run_lab(args.output, model=args.model, trials=args.trials)
            print(json.dumps({"status": result["status"], "output": args.output}))
            return {"PASS": 0, "FAIL": 1}.get(result["status"], 2)
        if args.command == "reason":
            from .reasoning import run_reasoning
            source = Path(args.source)
            if source.stat().st_size > 60_000:
                raise ValueError("Reasoning source is limited to 60 KB; pass only the relevant boundary")
            result = run_reasoning(source.read_text(encoding="utf-8"), read_json(args.evidence), use_tavily=args.tavily, model=args.model)
            write_json(args.output, result)
            print(json.dumps({"status": result["status"], "output": args.output}))
            return {"PASS": 0, "FAIL": 1}.get(result["status"], 2)
        if args.command == "serve":
            return serve_static(args.directory, args.port)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        from .evidence import sanitize
        print("PatchCourt: " + sanitize(str(exc)), file=sys.stderr)
        return 2


def serve_static(directory, port):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from urllib.parse import urlsplit
    root = Path(directory).resolve()
    if not (root / "index.html").is_file() or not (root / "report.json").is_file():
        raise ValueError("Run patchcourt demo first, or point serve at an exported report")
    # Explicit file allowlist; no directory traversal, source browsing, symlink reads or POSTs.
    allowed = {"/": ("index.html", "text/html; charset=utf-8"), "/index.html": ("index.html", "text/html; charset=utf-8"), "/report.json": ("report.json", "application/json"), "/report.md": ("report.md", "text/plain; charset=utf-8")}
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.headers.get("Host", "").lower() not in {f"127.0.0.1:{port}", f"localhost:{port}"}:
                self.send_error(403); return
            item = allowed.get(urlsplit(self.path).path)
            if not item:
                self.send_error(404); return
            path = root / item[0]
            if path.is_symlink() or not path.is_file() or path.resolve().parent != root or path.stat().st_size > 10_000_000:
                self.send_error(404); return
            data = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", item[1]); self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers(); self.wfile.write(data)
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"PatchCourt evidence viewer: http://127.0.0.1:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
