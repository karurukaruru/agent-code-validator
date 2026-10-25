"""Pinned installed-SDK serializer regression; no provider credentials or calls.

Install once into the ignored target with:
python -m pip install --target .sdk-nvidia --index-url https://pypi.org/simple langchain-nvidia-ai-endpoints==1.4.3
Run this reviewed script with the repository's Python interpreter. The original
SDK is never modified. A deterministic patched _utils.py copy is imported with
the real installed SDK's LangChain classes in a clean child process.
"""
from __future__ import annotations

import difflib
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
SDK = ROOT / ".sdk-nvidia"
OUT = ROOT / "evidence" / "full-sdk"
PIN = "1.4.3"
SOURCE_HASH = "ec8d2ef813a184d37a347f493242124319dbe3c6f6926124ba2f8a3560ed2531"
SOURCE = SDK / "langchain_nvidia_ai_endpoints" / "_utils.py"
PATCHED = OUT / "nvidia_utils_patched.py"
OLD = '        if "tool_calls" in message.additional_kwargs:\n            message_dict["tool_calls"] = message.additional_kwargs["tool_calls"]'
NEW = '''        if message.tool_calls:
            message_dict["tool_calls"] = [
                {"id": call["id"], "type": "function", "function": {
                    "name": call["name"],
                    "arguments": json.dumps(call["args"], ensure_ascii=False)
                }} for call in message.tool_calls
            ]
            if message_dict["content"] == "":
                message_dict["content"] = None
        elif "tool_calls" in message.additional_kwargs:
            message_dict["tool_calls"] = message.additional_kwargs["tool_calls"]'''


def reviewed_source():
    raw = SOURCE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_HASH:
        raise ValueError("Installed source hash differs from reviewed 1.4.3 wheel")
    text = raw.decode("utf-8")
    if text.count(OLD) != 1 or text.count("import logging") != 1:
        raise ValueError("Reviewed patch preconditions failed")
    return text, text.replace("import logging", "import json\nimport logging", 1).replace(OLD, NEW, 1)


def child():
    _, expected_patched = reviewed_source()
    if PATCHED.read_text(encoding="utf-8") != expected_patched:
        raise ValueError("Patched copy differs from exact reviewed patch")

    def block_network(event, args):
        if event in {"socket.connect", "socket.getaddrinfo", "socket.bind"}:
            raise RuntimeError("Network operation forbidden during offline reproduction")

    sys.addaudithook(block_network)
    sys.path.insert(0, str(SDK))
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
    from langchain_nvidia_ai_endpoints._utils import convert_message_to_dict

    spec = importlib.util.spec_from_file_location("reviewed_nvidia_utils_patch", PATCHED)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    repaired_convert = module.convert_message_to_dict
    calls = [
        {"id": "real-a", "name": "inventory", "args": {"sku": "東京", "quantity": 0, "available": False}},
        {"id": "real-b", "name": "price", "args": {"sku": "B", "options": {"currency": "JPY"}}},
    ]
    message = AIMessage(content="", tool_calls=calls)
    before = convert_message_to_dict(message)
    after = repaired_convert(message)

    def signatures(wire):
        for call in wire.get("tool_calls", []):
            if call.get("type") != "function" or set(call) != {"id", "type", "function"} or set(call["function"]) != {"name", "arguments"}:
                raise ValueError("Unexpected serialized tool schema")
        return [{"id": c["id"], "name": c["function"]["name"], "args": json.loads(c["function"]["arguments"])} for c in wire.get("tool_calls", [])]

    def equal(left, right):
        # JSON comparison distinguishes false from 0, unlike Python equality.
        return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(right, sort_keys=True, allow_nan=False)

    # Independent fixed expectations cover both calls, all argument fields,
    # ordering, role, and empty assistant content equivalence.
    original_failed = not equal(signatures(before), calls)
    repaired_passed = equal(signatures(after), calls) and after["role"] == "assistant" and after["content"] in ("", None)
    controls = {}
    for name, control in [
        ("plain_user", HumanMessage(content="hello")),
        ("plain_system", SystemMessage(content="instruction")),
        ("empty_tool_result", ToolMessage(content="", tool_call_id="real-a")),
    ]:
        controls[name] = convert_message_to_dict(control) == repaired_convert(control)
    legacy_wire = [{"id": "legacy-a", "type": "function", "function": {"name": "legacy", "arguments": '{"x":1}'}}]
    legacy = AIMessage(content="", additional_kwargs={"tool_calls": legacy_wire})
    controls["legacy_tool_calls"] = signatures(convert_message_to_dict(legacy)) == signatures(repaired_convert(legacy)) == [{"id": "legacy-a", "name": "legacy", "args": {"x": 1}}]
    damaged = json.loads(json.dumps(after))
    damaged["tool_calls"][1]["function"]["arguments"] = '{"sku":"WRONG"}'
    controls["second_call_mutation_detected"] = not equal(signatures(damaged), calls)
    result = {
        "status": "REPRODUCED_AND_REPAIRED" if original_failed and repaired_passed and all(controls.values()) else "NEEDS_REVIEW",
        "before": {"status": "FAIL" if original_failed else "PASS", "wire": before},
        "after": {"status": "PASS" if repaired_passed else "FAIL", "wire": after},
        "expected_calls": calls, "controls": controls,
        "real_message_class": str(type(message)),
        "original_function_module": convert_message_to_dict.__module__,
        "real_sdk_imported": True, "provider_called": False,
        "scope": "Installed pinned SDK serializer with real LangChain message classes; reviewed patched module copy. No model or provider end-to-end claim.",
        "credential_environment_present": any(any(token in name.upper() for token in ("KEY", "TOKEN", "SECRET", "PASSWORD")) for name in os.environ),
    }
    print(json.dumps(result, ensure_ascii=True))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    original, patched = reviewed_source()
    PATCHED.write_text(patched, encoding="utf-8", newline="\n")
    (OUT / "nvidia_utils_original.py.txt").write_bytes(SOURCE.read_bytes())
    (OUT / "nvidia-1.4.3-repair.diff").write_text("".join(difflib.unified_diff(original.splitlines(True), patched.splitlines(True), fromfile="a/langchain_nvidia_ai_endpoints/_utils.py", tofile="b/langchain_nvidia_ai_endpoints/_utils.py")), encoding="utf-8")
    distinfo = SDK / "langchain_nvidia_ai_endpoints-1.4.3.dist-info"
    for name in ("METADATA", "WHEEL", "RECORD"):
        shutil.copyfile(distinfo / name, OUT / ("nvidia-1.4.3-" + name + ".txt"))
    shutil.copyfile(distinfo / "licenses" / "LICENSE", OUT / "NVIDIA-LICENSE.txt")
    versions = sorted((dist.metadata["Name"], dist.version) for dist in importlib.metadata.distributions(path=[str(SDK)]))
    (OUT / "requirements-resolved.txt").write_text("\n".join(f"{name}=={version}" for name, version in versions) + "\n", encoding="utf-8")
    clean_home = OUT / "isolated-home"
    clean_home.mkdir(exist_ok=True)
    allowed_env = {name: os.environ[name] for name in ("SystemRoot", "WINDIR", "COMSPEC") if name in os.environ}
    allowed_env.update({"HOME": str(clean_home), "USERPROFILE": str(clean_home), "TEMP": str(clean_home), "TMP": str(clean_home), "LANGCHAIN_TRACING_V2": "false", "LANGSMITH_TRACING": "false"})
    proc = subprocess.run([sys.executable, "-I", str(Path(__file__).resolve()), "--child"], cwd=ROOT, env=allowed_env, capture_output=True, text=True, encoding="utf-8", timeout=90)
    result = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "issue": "https://github.com/langchain-ai/langchain-nvidia/issues/387",
        "package": "langchain-nvidia-ai-endpoints", "version": PIN,
        "installation_command": "python -m pip install --target .sdk-nvidia --index-url https://pypi.org/simple langchain-nvidia-ai-endpoints==1.4.3",
        "installation": "Succeeded from official PyPI wheels into isolated local target",
        "source_sha256": SOURCE_HASH,
        "patched_sha256": hashlib.sha256(patched.encode("utf-8")).hexdigest(),
        "python": sys.version, "dependencies": dict(versions),
        "child_environment_allowlist": sorted(allowed_env),
        "network_policy": "Python audit hook rejects socket connect, DNS resolution, and bind; no provider requests. This is not an OS sandbox claim.",
        "returncode": proc.returncode,
        "stderr": proc.stderr,
    }
    if proc.returncode == 0:
        result["result"] = json.loads(proc.stdout)
    else:
        result.update({"status": "INCONCLUSIVE", "stdout": proc.stdout})
    (OUT / "nvidia-1.4.3-result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"evidence": str(OUT / "nvidia-1.4.3-result.json"), "returncode": proc.returncode, "status": result.get("result", {}).get("status", "INCONCLUSIVE")}))
    return proc.returncode


if __name__ == "__main__":
    if sys.argv[1:] == ["--child"]:
        child()
    elif not sys.argv[1:]:
        raise SystemExit(main())
    else:
        raise SystemExit("No external source paths or patches accepted")
