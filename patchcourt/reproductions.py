"""Execute audited upstream function snapshots against inert protocol stubs.

This is source-boundary reproduction, NOT installation of the complete SDK.
Only two exact source hashes and two reviewed patches are executable here.
"""
from __future__ import annotations

import ast
import base64
import difflib
import hashlib
import json
import time
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from .counterexamples import replay, tool_conversation
from .semantic import compare_messages

ROOT = Path(__file__).parent / "fixtures"
SOURCES = {
    "nvidia": {"file": "nvidia_utils.py.txt", "sha256": "ea569d556ed537e15bf5eea3db555adc9b4fb003a92543c70f1c719a9c47c873", "git_blob": "8c23b708e8511c70e771f48fe71b4309d201f61b", "version": "upstream source blob (not a verified 1.4.3 wheel)", "url": "https://github.com/langchain-ai/langchain-nvidia/issues/387"},
    "crewai": {"file": "crewai_gemini.py.txt", "sha256": "715e68f80b32cbd97011bf8c616b3746149454083a32b163cf2010f136a63383", "git_blob": "1129d411257ce66d199f49ecb230c797374def24", "version": "1.15.28 tag source", "url": "https://github.com/crewAIInc/crewAI/issues/8434"},
}


def source(name):
    spec = SOURCES[name]
    raw = (ROOT / spec["file"]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != spec["sha256"]:
        raise ValueError("Upstream fixture changed; refuse execution until separately reviewed")
    return raw.decode("utf-8")


class Message:
    def __init__(self, content="", **kwargs):
        self.content = content
        self.additional_kwargs = kwargs.pop("additional_kwargs", {})
        self.tool_calls = kwargs.pop("tool_calls", [])
        self.__dict__.update(kwargs)


MESSAGE_TYPES = {name: type(name, (Message,), {}) for name in ("AIMessage", "BaseMessage", "ChatMessage", "FunctionMessage", "HumanMessage", "SystemMessage", "ToolMessage")}


NVIDIA_OLD = '        if "tool_calls" in message.additional_kwargs:\n            message_dict["tool_calls"] = message.additional_kwargs["tool_calls"]'
NVIDIA_NEW = '''        if message.tool_calls:
            message_dict["tool_calls"] = [
                {"id": c["id"], "type": "function", "function": {
                    "name": c["name"], "arguments": json.dumps(c["args"], ensure_ascii=False)
                }} for c in message.tool_calls
            ]
            if message_dict["content"] == "":
                message_dict["content"] = None
        elif "tool_calls" in message.additional_kwargs:
            message_dict["tool_calls"] = message.additional_kwargs["tool_calls"]'''
CREW_OLD = '                        elif "inlineData" in item:'
CREW_NEW = '''                        elif item.get("type") == "image_url":
                            image = item.get("image_url", {})
                            url = image.get("url", "") if isinstance(image, dict) else image
                            if not isinstance(url, str) or not url.startswith("data:image/") or ";base64," not in url:
                                raise ValueError("Unsupported image_url: provide an image data URI")
                            header, encoded = url.split(",", 1)
                            parts.append(types.Part.from_bytes(
                                data=base64.b64decode(encoded, validate=True),
                                mime_type=header[5:].split(";")[0],
                            ))
                        elif "inlineData" in item:'''


def patched_source(name):
    raw = source(name)
    old, new = (NVIDIA_OLD, NVIDIA_NEW) if name == "nvidia" else (CREW_OLD, CREW_NEW)
    if raw.count(old) != 1:
        raise ValueError("Patch precondition mismatch")
    return raw.replace(old, new)


def patch_diff(name):
    return "".join(difflib.unified_diff(source(name).splitlines(True), patched_source(name).splitlines(True), fromfile="a/" + SOURCES[name]["file"], tofile="b/" + SOURCES[name]["file"]))


def load_nvidia(repaired=False):
    # No arbitrary path, code, model-generated Python, imports or user patches accepted.
    raw = patched_source("nvidia") if repaired else source("nvidia")
    tree = ast.parse(raw)
    selected = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in {"_normalize_content", "convert_message_to_dict"}]
    module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)] + selected, type_ignores=[])
    namespace = dict(MESSAGE_TYPES, json=json)
    exec(compile(ast.fix_missing_locations(module), "audited:nvidia", "exec"), namespace)
    return namespace["convert_message_to_dict"]


class Part:
    def __init__(self, **kwargs):
        self.text = self.inline_data = self.file_data = self.function_call = self.function_response = None
        self.__dict__.update(kwargs)

    @classmethod
    def from_text(cls, text):
        return cls(text=text)

    @classmethod
    def from_bytes(cls, data, mime_type):
        return cls(inline_data=SimpleNamespace(data=data, mime_type=mime_type))

    @classmethod
    def from_uri(cls, file_uri, mime_type):
        return cls(file_data=SimpleNamespace(file_uri=file_uri, mime_type=mime_type))

    @classmethod
    def from_function_call(cls, **kwargs):
        return cls(function_call=kwargs)

    @classmethod
    def from_function_response(cls, **kwargs):
        return cls(function_response=kwargs)


class Base:
    def _format_messages(self, messages):
        return deepcopy(messages)


def load_crewai(repaired=False):
    raw = patched_source("crewai") if repaired else source("crewai")
    tree = ast.parse(raw)
    method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_format_messages_for_gemini")
    wrapper = ast.ClassDef(name="AuditedGemini", bases=[ast.Name(id="Base", ctx=ast.Load())], keywords=[], body=[method], decorator_list=[])
    module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), wrapper], type_ignores=[])
    namespace = {"Base": Base, "base64": base64, "json": json, "types": SimpleNamespace(Part=Part, Content=SimpleNamespace)}
    exec(compile(ast.fix_missing_locations(module), "audited:crewai", "exec"), namespace)
    return namespace["AuditedGemini"]()._format_messages_for_gemini


def nvidia_messages(messages, repaired=False):
    convert = load_nvidia(repaired)
    output = []
    for m in messages:
        data = deepcopy(m)
        role = data.pop("role")
        if role == "assistant":
            data["tool_calls"] = [{"id": c["id"], "name": c["function"]["name"], "args": json.loads(c["function"]["arguments"]), "type": "tool_call"} for c in data.get("tool_calls", [])]
        cls = MESSAGE_TYPES[{"assistant": "AIMessage", "tool": "ToolMessage", "user": "HumanMessage", "system": "SystemMessage"}[role]]
        output.append(convert(cls(**data)))
    return output


def run_reproductions():
    results = []
    start = time.perf_counter()
    baseline = tool_conversation()
    candidate = nvidia_messages(baseline)
    repaired = nvidia_messages(baseline, True)
    # Independent concrete expectations, not a model grading its own work.
    repair_ok = compare_messages(baseline, repaired)["status"] == "PASS" and len(repaired[0].get("tool_calls", [])) == 2 and repaired[0]["tool_calls"][0]["id"] == "call_a" and json.loads(repaired[0]["tool_calls"][0]["function"]["arguments"]) == {"sku": "A", "options": {"warehouse": 2}}
    legacy = MESSAGE_TYPES["AIMessage"](additional_kwargs={"tool_calls": baseline[0]["tool_calls"]})
    controls = {"plain_text": load_nvidia() (MESSAGE_TYPES["HumanMessage"]("hello")) == load_nvidia(True)(MESSAGE_TYPES["HumanMessage"]("hello")), "legacy": load_nvidia(True)(legacy)["tool_calls"] == baseline[0]["tool_calls"], "empty_tool_result": load_nvidia(True)(MESSAGE_TYPES["ToolMessage"]("", tool_call_id="a"))["content"] == ""}
    results.append({"id": "langchain-nvidia-387", "title": "Normalized tool calls disappear at the NVIDIA adapter", **compare_messages(baseline, candidate), "baseline": baseline, "candidate": candidate, "provenance": {**SOURCES["nvidia"], "kind": "audited upstream function execution with inert LangChain stubs", "full_sdk_verified": False}, "repair": {"status": "VERIFIED" if repair_ok and all(controls.values()) else "REJECTED", "origin": "reviewed deterministic source patch, not model-generated", "before": candidate, "after": repaired, "controls": controls, "diff": patch_diff("nvidia"), "scope": "source-boundary harness only"}, "task_replay": {"before": replay(candidate), "after": replay(repaired)}, "execution": True, "duration_ms": round((time.perf_counter()-start)*1000, 3)})
    start = time.perf_counter()
    # Valid 1x1 PNG, compared as bytes; no vision model is called.
    encoded = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jS9sAAAAASUVORK5CYII="
    messages = [{"role": "user", "content": [{"type": "text", "text": "Describe this image"}, {"type": "image_url", "image_url": {"url": "data:image/png;base64," + encoded}}]}]
    before, _ = load_crewai()(messages)
    after, _ = load_crewai(True)(messages)
    expected = base64.b64decode(encoded)
    original_count = sum(p.inline_data is not None for p in before[0].parts)
    repaired_parts = [p.inline_data for p in after[0].parts if p.inline_data is not None]
    text_control = load_crewai()([{"role": "user", "content": "hello"}])[0][0].parts[0].text == load_crewai(True)([{"role": "user", "content": "hello"}])[0][0].parts[0].text == "hello"
    rejected = False
    try:
        load_crewai(True)([{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "https://example.com/image.png"}}]}])
    except ValueError:
        rejected = True
    ok = len(repaired_parts) == 1 and repaired_parts[0].data == expected and repaired_parts[0].mime_type == "image/png" and text_control and rejected
    results.append({"id": "crewai-8434", "title": "Gemini formatter silently removes a vision observation", "status": "FAIL" if original_count == 0 else "INCONCLUSIVE", "baseline": messages, "candidate": {"text": before[0].parts[0].text, "image_count": original_count}, "findings": [{"code": "LOST_IMAGE", "path": "/0/content/1", "expected": 1, "actual": original_count, "message": "Upstream formatter lost the input image bytes"}], "provenance": {**SOURCES["crewai"], "kind": "audited upstream method with inert Gemini types and identity base formatter", "full_sdk_verified": False}, "repair": {"status": "VERIFIED" if ok else "REJECTED", "origin": "reviewed deterministic source patch, not model-generated", "before": {"image_count": original_count}, "after": {"image_count": len(repaired_parts), "bytes_preserved": ok}, "controls": {"plain_text": text_control, "remote_url_explicitly_rejected": rejected}, "diff": patch_diff("crewai"), "scope": "source-boundary harness only"}, "task_replay": {"before": {"status": "FAIL", "reason": "No image supplied to vision task"}, "after": {"status": "INCONCLUSIVE", "reason": "Image restored; real vision task requires model inference"}}, "execution": True, "duration_ms": round((time.perf_counter()-start)*1000,3)})
    return results
