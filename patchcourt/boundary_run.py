"""Execute two reviewed serializer variants in separate, credential-free processes.

This is a bounded local boundary harness, not an arbitrary repository executor,
dependency upgrade manager, or OS sandbox. No provider calls are made.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from .evidence import canonical, sanitize, strict_json
from .semantic import compare_messages

VARIANTS = ("upstream", "reviewed-patch")
SDK_HASH = "ec8d2ef813a184d37a347f493242124319dbe3c6f6926124ba2f8a3560ed2531"
INPUT_LIMIT = 128_000
OUTPUT_LIMIT = 2_000_000
TIMEOUT = 45


def validate_input(messages):
    """Do not silently project unsupported fields into the supported protocol."""
    if len(canonical(messages).encode("utf-8")) > INPUT_LIMIT:
        raise ValueError("Boundary input exceeds 128 KB")
    if not isinstance(messages, list) or not 1 <= len(messages) <= 100:
        raise ValueError("Boundary input requires 1 to 100 messages")
    if canonical(sanitize(messages)) != canonical(messages):
        raise ValueError("Input requires secret redaction; abstaining rather than comparing altered evidence")
    verdict = compare_messages(messages, messages)
    if verdict["status"] != "PASS":
        raise ValueError("Invalid or unsupported input: " + canonical(verdict["findings"]))
    for message in messages:
        role = message.get("role")
        if role not in {"system", "user", "assistant", "tool"}:
            raise ValueError("Boundary runner supports explicit system/user/assistant/tool roles")
        allowed = {"role", "content", "name"}
        if role == "assistant":
            allowed.add("tool_calls")
        elif role == "tool":
            allowed.add("tool_call_id")
        if set(message) - allowed:
            raise ValueError("Boundary runner cannot preserve supplied message metadata")
        if not isinstance(message.get("content"), (str, type(None))):
            raise ValueError("This boundary runner supports text and null content only")
        if "name" in message and not isinstance(message["name"], str):
            raise ValueError("Message name must be text")
        for call in message.get("tool_calls", []):
            if (set(call) != {"id", "type", "function"} or call["type"] != "function"
                    or set(call["function"]) != {"name", "arguments"}
                    or not isinstance(call["function"]["arguments"], str)):
                raise ValueError("Supply complete OpenAI function tool calls with JSON argument strings")


def _converter(variant, sdk_root):
    from .reproductions import load_nvidia, MESSAGE_TYPES, SOURCES, NVIDIA_OLD, NVIDIA_NEW, patched_source
    if sdk_root is None:
        raw_hash = SOURCES["nvidia"]["sha256"]
        return load_nvidia(variant == "reviewed-patch"), MESSAGE_TYPES, {
            "backend": "pinned-source", "real_sdk_classes": False,
            "source_sha256": raw_hash,
            "executed_source_sha256": hashlib.sha256(patched_source("nvidia").encode()).hexdigest() if variant == "reviewed-patch" else raw_hash,
            "version": SOURCES["nvidia"]["version"], "dependencies": {},
        }
    sdk = Path(sdk_root).resolve()
    raw = (sdk / "langchain_nvidia_ai_endpoints" / "_utils.py").read_bytes()
    if hashlib.sha256(raw).hexdigest() != SDK_HASH:
        raise ValueError("Installed NVIDIA serializer is not the reviewed 1.4.3 source")
    versions = {d.metadata["Name"]: d.version for d in importlib.metadata.distributions(path=[str(sdk)])}
    if versions.get("langchain-nvidia-ai-endpoints") != "1.4.3":
        raise ValueError("Installed NVIDIA distribution metadata must be version 1.4.3")
    # Explicit trusted local dependency target; -S prevents site/.pth startup.
    sys.path.append(str(sdk))
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
    text = raw.decode("utf-8")
    if variant == "reviewed-patch":
        if text.count(NVIDIA_OLD) != 1 or text.count("import logging") != 1:
            raise ValueError("Reviewed SDK patch precondition mismatch")
        text = text.replace("import logging", "import json\nimport logging", 1).replace(NVIDIA_OLD, NVIDIA_NEW, 1)
    namespace = {"__name__": "patchcourt_reviewed_nvidia_serializer"}
    exec(compile(text, "reviewed:nvidia-1.4.3", "exec"), namespace)
    return namespace["convert_message_to_dict"], {
        "AIMessage": AIMessage, "HumanMessage": HumanMessage,
        "SystemMessage": SystemMessage, "ToolMessage": ToolMessage,
    }, {
        "backend": "installed-sdk", "real_sdk_classes": True,
        "source_sha256": SDK_HASH, "executed_source_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "version": "1.4.3", "dependencies": versions,
    }


def _child(request):
    """Private entry point accepts data and two fixed variants, never source code."""
    from .recorder import BoundaryRecorder
    if request["variant"] not in VARIANTS:
        raise ValueError("Unknown reviewed variant")
    messages = request["messages"]
    validate_input(messages)

    def audit(event, args):
        if event.startswith("socket.") or event in {"subprocess.Popen", "os.system", "os.posix_spawn", "os.fork", "os.exec", "os.spawn"}:
            raise RuntimeError("Network and subprocess operations forbidden by offline boundary policy")

    sys.addaudithook(audit)
    convert, types, provenance = _converter(request["variant"], request["sdk_root"])
    recorder = BoundaryRecorder("convert_message_to_dict", provenance["version"])
    framework = []
    output = []
    for message in messages:
        data = deepcopy(message)
        role = data.pop("role")
        data["content"] = data.get("content") or ""
        if "tool_calls" in data:
            data["tool_calls"] = [
                {"id": c["id"], "name": c["function"]["name"],
                 "args": strict_json(c["function"]["arguments"]), "type": "tool_call"}
                for c in data["tool_calls"]
            ]
        cls = types[{"assistant": "AIMessage", "user": "HumanMessage", "system": "SystemMessage", "tool": "ToolMessage"}[role]]
        instance = cls(**data)
        snapshot = {"role": role, "content": instance.content}
        for field in ("name", "tool_call_id", "tool_calls"):
            if field in data:
                snapshot[field] = deepcopy(getattr(instance, field))
        framework.append(snapshot)
        output.append(convert(instance))
    recorder.record("framework_input", framework)
    recorder.record("adapter_output", output)
    return {
        "status": "EXECUTED", "variant": request["variant"], "pid": os.getpid(),
        "provenance": provenance, "events": recorder.events, "output": output,
        "input_conversion": compare_messages(messages, framework),
        "provider_requests": 0,
    }


def _run_side(messages, variant, sdk_root):
    started = time.perf_counter()
    package_root = str(Path(__file__).resolve().parent.parent)
    bootstrap = "import sys;sys.dont_write_bytecode=True;sys.path.insert(0,sys.argv[1]);from patchcourt.boundary_run import _worker;_worker()"
    request = {"messages": messages, "variant": variant, "sdk_root": str(Path(sdk_root).resolve()) if sdk_root else None}
    # The request travels through stdin, not a credential-bearing environment.
    with tempfile.TemporaryDirectory(prefix="patchcourt-boundary-") as temp:
        env = {k: os.environ[k] for k in ("SystemRoot", "WINDIR") if k in os.environ}
        env.update({"HOME": temp, "USERPROFILE": temp, "TEMP": temp, "TMP": temp,
                    "LANGCHAIN_TRACING_V2": "false", "LANGSMITH_TRACING": "false"})
        with tempfile.TemporaryFile() as stdin, tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
            stdin.write(canonical(request).encode("utf-8")); stdin.seek(0)
            proc = subprocess.Popen([sys.executable, "-I", "-S", "-c", bootstrap, package_root],
                                    cwd=temp, env=env, stdin=stdin, stdout=stdout, stderr=stderr)
            failure = None
            while True:
                try:
                    proc.wait(timeout=0.1)
                    break
                except subprocess.TimeoutExpired:
                    if time.perf_counter() - started > TIMEOUT:
                        failure = "Child exceeded 45-second execution deadline"
                    if os.fstat(stdout.fileno()).st_size + os.fstat(stderr.fileno()).st_size > OUTPUT_LIMIT:
                        failure = "Child exceeded 2 MB output budget"
                    if failure:
                        proc.kill(); proc.wait(); break
            stdout.seek(0); stderr.seek(0)
            raw, error = stdout.read(OUTPUT_LIMIT + 1), stderr.read(OUTPUT_LIMIT + 1)
            if len(raw) + len(error) > OUTPUT_LIMIT:
                failure = "Child exceeded 2 MB output budget"
            metadata = {"variant": variant, "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                        "exit_code": proc.returncode, "environment_allowlist": sorted(env), "stderr": error.decode("utf-8", errors="replace")[:4000]}
            if failure or proc.returncode:
                return {**metadata, "status": "INCONCLUSIVE", "error": failure or "Child process failed"}
            try:
                result = strict_json(raw.decode("utf-8"))
                if not isinstance(result, dict) or result.get("variant") != variant:
                    raise ValueError("Unexpected child result")
            except (UnicodeError, ValueError) as exc:
                return {**metadata, "status": "INCONCLUSIVE", "error": str(exc)}
            return {**result, **metadata}


def _worker():
    try:
        request = strict_json(sys.stdin.buffer.read(INPUT_LIMIT + 4096).decode("utf-8"))
        result = _child(request)
    except Exception as exc:
        result = {"status": "INCONCLUSIVE", "variant": locals().get("request", {}).get("variant"),
                  "error": type(exc).__name__ + ": " + str(exc)}
    print(json.dumps(sanitize(result), ensure_ascii=True, allow_nan=False))


def run_boundary(output, *, baseline="reviewed-patch", candidate="upstream", messages=None, sdk_root=None):
    from .counterexamples import tool_conversation, replay
    from .runner import make_report, export_report
    if baseline not in VARIANTS or candidate not in VARIANTS:
        raise ValueError("Only upstream and reviewed-patch variants are executable")
    root = Path(output)
    root.mkdir(parents=True, exist_ok=False)
    default_task = messages is None
    messages = tool_conversation() if default_task else messages
    case = {"id": "nvidia-boundary-pair", "title": "Executed NVIDIA serializer boundary pair",
            "status": "INCONCLUSIVE", "execution": False, "findings": [],
            "provenance": {"baseline_variant": baseline, "candidate_variant": candidate,
                           "kind": "reviewed local serializer execution; no model inference"}}
    report = make_report([case])
    report.update({"mode": "boundary-run", "status": "INCONCLUSIVE", "input": messages, "executions": {},
                   "limitations": [
                       "Two reviewed implementations of one serializer; not an automatic dependency upgrade or arbitrary repository runner.",
                       "Supports text and OpenAI function-call inputs only; unsupported metadata and content abstain.",
                       "Separate -I -S processes, clean environment, timeout, output budget and Python audit hook; not an OS security sandbox. Installed dependencies must be trusted.",
                       "Input is checked against each output. An unhealthy baseline cannot establish a regression verdict, even when both outputs match.",
                       "No model, search, or provider requests. Hash checks provide integrity, not independent authentication.",
                   ]})
    try:
        validate_input(messages)
    except (ValueError, TypeError, KeyError) as exc:
        case["findings"] = [{"code": "UNSUPPORTED_INPUT", "message": str(exc)}]
        return export_report(report, root)
    for side, variant in (("baseline", baseline), ("candidate", candidate)):
        try:
            report["executions"][side] = _run_side(messages, variant, sdk_root)
        except OSError as exc:
            report["executions"][side] = {"status": "INCONCLUSIVE", "error": str(exc), "variant": variant}
    runs = report["executions"]
    case["duration_ms"] = round(sum(r.get("duration_ms", 0) for r in runs.values()), 3)
    if any(r["status"] != "EXECUTED" or r["input_conversion"]["status"] != "PASS" for r in runs.values()):
        case["findings"] = [{"code": "EXECUTION_UNCERTAIN", "message": "A worker or its input conversion did not complete successfully; see executions"}]
    else:
        a, b = runs["baseline"]["output"], runs["candidate"]["output"]
        contracts = {"baseline": compare_messages(messages, a), "candidate": compare_messages(messages, b),
                     "difference": compare_messages(a, b)}
        case.update({"execution": True, "baseline": a, "candidate": b, "contracts": contracts})
        if default_task:
            case["task_replay"] = {"before": replay(a), "after": replay(b)}
        if contracts["baseline"]["status"] != "PASS":
            case.update({"status": "NEEDS_REVIEW", "findings": [{"code": "UNHEALTHY_BASELINE", "message": "Baseline already violates the input contract; cannot certify compatibility from this baseline"}],
                         "direction": "candidate_restores_contract" if contracts["candidate"]["status"] == "PASS" else "baseline_and_candidate_unhealthy" if contracts["candidate"]["status"] == "FAIL" else "candidate_uncertain"})
        else:
            case.update(contracts["candidate"])
            case["direction"] = "regression" if case["status"] == "FAIL" else "unchanged" if case["status"] == "PASS" else "uncertain"
    report["status"] = case["status"]
    report["summary"] = {s: int(case["status"].lower() == s) for s in ("pass", "fail", "inconclusive", "needs_review")}
    return export_report(report, root)
