"""Reproduce CrewAI #8434 with installed SDK classes and its real base formatter.

Install reviewed dependencies into a dedicated target (never the project venv):
python -m pip install --target .sdk-crewai 'crewai[google-genai]==1.15.28'
python examples/reproductions/full_sdk_crewai.py --output outputs/crewai-sdk

No client is constructed and no inference is sent. The reviewed repair overrides
only the hash-checked formatter on a subclass; installed packages stay unchanged.
"""
from __future__ import annotations

import argparse
import ast
import base64
import copy
import difflib
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
SOURCE_HASH = "41ebd52a6f468f5fc71f5c147e3768f0b755d4a1ff0703b0293b9e3d69348fe4"
PIN = "1.15.28"
MODULE = Path("crewai/llms/providers/gemini/completion.py")


def checked_source(sdk):
    raw = (sdk / MODULE).read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_HASH:
        raise ValueError("Installed CrewAI module differs from reviewed 1.15.28 wheel")
    versions = {d.metadata["Name"].lower().replace("_", "-"): d.version
                for d in importlib.metadata.distributions(path=[str(sdk)])}
    if versions.get("crewai") != PIN or versions.get("crewai-core") != PIN:
        raise ValueError("CrewAI and crewai-core must both be 1.15.28")
    return raw.decode("utf-8"), versions


def child(sdk):
    # Native extension diagnostics can use the Windows console code page. Keep
    # Python output UTF-8 and preserve undecodable native stderr in the parent.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    raw, versions = checked_source(sdk)
    def audit(event, args):
        # platform.system() calls gethostname() on Windows; reading the local
        # hostname sends no traffic. Socket construction, DNS and I/O stay blocked.
        if (event.startswith("socket.") and event != "socket.gethostname") or event in {"subprocess.Popen", "os.system", "os.posix_spawn", "os.fork", "os.exec", "os.spawn"}:
            raise RuntimeError("Network and subprocess operations forbidden in offline reproduction")
    sys.addaudithook(audit)
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(sdk))
    if os.name == "nt":
        # -S deliberately disables .pth startup. Add only the reviewed wheel's
        # native module paths instead of executing arbitrary .pth statements.
        sys.path.extend(str(sdk / name) for name in ("win32", "win32/lib", "pythonwin"))
        dll_directory = os.add_dll_directory(str(sdk / "pywin32_system32"))
    sys.path.append(str(ROOT))
    from crewai.llms.providers.gemini.completion import GeminiCompletion
    from google.genai import types
    from patchcourt.reproductions import CREW_OLD, CREW_NEW, source

    # Wheel and historical tag modules differ; verify the actual method is the
    # same reviewed AST before applying the exact, fixed source replacement.
    def method(text):
        tree = ast.parse(text)
        return next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_format_messages_for_gemini")
    if ast.dump(method(raw), include_attributes=False) != ast.dump(method(source("crewai")), include_attributes=False):
        raise ValueError("Installed formatter differs from reviewed historical method")
    if raw.count(CREW_OLD) != 1:
        raise ValueError("Reviewed CrewAI patch precondition mismatch")
    patched = raw.replace(CREW_OLD, CREW_NEW)
    wrapper = ast.ClassDef(name="ReviewedGeminiCompletion", bases=[ast.Name(id="GeminiCompletion", ctx=ast.Load())],
                           keywords=[], body=[method(patched)], decorator_list=[])
    tree = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), wrapper], type_ignores=[])
    namespace = {"__name__": GeminiCompletion.__module__, "GeminiCompletion": GeminiCompletion,
                 "types": types, "base64": base64, "json": json}
    exec(compile(ast.fix_missing_locations(tree), "reviewed:crewai-1.15.28-formatter", "exec"), namespace)
    # model_construct bypasses credential/client initialization, not the real
    # BaseLLM._format_messages or google.genai Part/Content implementations.
    original = GeminiCompletion.model_construct()
    repaired = namespace["ReviewedGeminiCompletion"].model_construct()
    png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jS9sAAAAASUVORK5CYII=")
    jpeg = b"\xff\xd8\xff\xe0\x00\x02\xff\xd9"
    images = [(png, "image/png"), (jpeg, "image/jpeg")]
    messages = [{"role": "user", "content": [{"type": "text", "text": "Compare these images"}] + [
        {"type": "image_url", "image_url": {"url": "data:" + mime + ";base64," + base64.b64encode(data).decode()}}
        for data, mime in images]}]
    untouched = copy.deepcopy(messages)
    before, _ = original._format_messages_for_gemini(messages)
    after, _ = repaired._format_messages_for_gemini(messages)
    def observed(contents):
        return [(p.inline_data.data, p.inline_data.mime_type) for content in contents for p in (content.parts or []) if p.inline_data is not None]
    controls = {}
    for label, value in (("plain_text", [{"role": "user", "content": "hello"}]),
                         ("system_instruction", [{"role": "system", "content": "Be concise"}, {"role": "user", "content": "hello"}]),
                         ("legacy_inline_data", [{"role": "user", "content": [{"inlineData": {"data": base64.b64encode(png).decode(), "mimeType": "image/png"}}]}])):
        old_contents, old_system = original._format_messages_for_gemini(value)
        new_contents, new_system = repaired._format_messages_for_gemini(value)
        controls[label] = old_contents == new_contents and old_system == new_system
    controls["caller_input_unchanged"] = messages == untouched
    controls["real_google_types"] = all(isinstance(c, types.Content) and all(isinstance(p, types.Part) for p in c.parts) for c in after)
    for label, url in (("remote_url_rejected", "https://example.invalid/image.png"), ("invalid_base64_rejected", "data:image/png;base64,%%%")):
        try:
            repaired._format_messages_for_gemini([{"role": "user", "content": [{"type": "image_url", "image_url": url}]}])
        except ValueError:
            controls[label] = True
        else:
            controls[label] = False
    mutated = copy.deepcopy(after)
    mutated[0].parts[-1].inline_data.data = b"corrupted"
    controls["second_image_mutation_rejected"] = observed(mutated) != images
    original_failed = not observed(before)
    repaired_passed = observed(after) == images
    return {"status": "REPRODUCED_AND_REPAIRED" if original_failed and repaired_passed and all(controls.values()) else "NEEDS_REVIEW",
            "before": {"image_count": len(observed(before)), "status": "FAIL" if original_failed else "INCONCLUSIVE"},
            "after": {"image_count": len(observed(after)), "status": "PASS" if repaired_passed else "FAIL",
                      "images": [{"mime_type": mime, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()} for data, mime in observed(after)]},
            "controls": controls, "dependencies": versions, "provider_requests": 0,
            "real_sdk_imported": True, "real_base_formatter": True,
            "constructor": "Pydantic model_construct; API clients and credential validation intentionally bypassed",
            "scope": "Installed SDK formatter with real BaseLLM and google.genai types. No client, inference, image decoding or vision-task success claim."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk-root", type=Path, default=ROOT / ".sdk-crewai")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs" / "crewai-sdk")
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    sdk = args.sdk_root.resolve()
    if args.child:
        print(json.dumps(child(sdk), ensure_ascii=True, allow_nan=False))
        return 0
    raw, versions = checked_source(sdk)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="patchcourt-crewai-") as home:
        local_appdata = Path(home) / "AppData" / "Local"
        roaming_appdata = Path(home) / "AppData" / "Roaming"
        local_appdata.mkdir(parents=True)
        roaming_appdata.mkdir(parents=True)
        env = {k: os.environ[k] for k in ("SystemRoot", "WINDIR") if k in os.environ}
        env.update({"HOME": home, "USERPROFILE": home, "TEMP": home, "TMP": home,
                    "LOCALAPPDATA": str(local_appdata), "APPDATA": str(roaming_appdata),
                    "CREWAI_TELEMETRY_DISABLED": "true", "OTEL_SDK_DISABLED": "true",
                    "DO_NOT_TRACK": "1", "ANONYMIZED_TELEMETRY": "false"})
        proc = subprocess.run([sys.executable, "-I", "-S", str(Path(__file__).resolve()), "--child", "--sdk-root", str(sdk)],
                              cwd=home, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    report = {"recorded_at": datetime.now(timezone.utc).isoformat(), "package": "crewai", "version": PIN,
              "issue": "https://github.com/crewAIInc/crewAI/issues/8434", "source_sha256": SOURCE_HASH,
              "python": sys.version, "dependencies": versions, "child_environment_allowlist": sorted(env),
              "isolation": "Separate -I -S process, clean environment, audit hook; not an OS sandbox",
              "exit_code": proc.returncode, "stderr": proc.stderr, "provider_requests": 0}
    if proc.returncode == 0:
        report["result"] = json.loads(proc.stdout)
    else:
        report.update({"status": "INCONCLUSIVE", "stdout": proc.stdout})
    (output / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output / "requirements-resolved.txt").write_text("\n".join(f"{k}=={v}" for k, v in sorted(versions.items())) + "\n", encoding="utf-8")
    print(json.dumps({"status": report.get("result", {}).get("status", "INCONCLUSIVE"), "output": str(output)}))
    return 0 if report.get("result", {}).get("status") == "REPRODUCED_AND_REPAIRED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
