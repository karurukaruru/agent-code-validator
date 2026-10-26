"""Strict, offline selection of one opt-in captured adapter transaction.

An observed payload is supplied evidence, never proof that a future SDK ran.
This module and the comparator can be exported without third-party packages.
"""
from copy import deepcopy
from datetime import datetime
from pathlib import Path
import re

from .evidence import read_json, validate_shape

STAGES = {"framework_input", "adapter_output", "outbound_payload", "stream_event", "provider_response"}


def validate_request_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,79}", value):
        raise ValueError("Each event requires a nonempty request_id of at most 80 safe characters")
    return value


def _metadata(value, label, limit=200):
    if (not isinstance(value, str) or not value.strip() or len(value) > limit
            or any(ord(c) < 32 for c in value)):
        raise ValueError("Missing or invalid recording " + label)


def _timestamp(value):
    if not isinstance(value, str):
        raise ValueError("Every event requires an ISO timestamp with timezone")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("Missing timezone")
    except ValueError:
        raise ValueError("Every event requires an ISO timestamp with timezone") from None
    return parsed


def read_recording(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Recording must be an existing regular JSON file")
    return validate_recording(read_json(path))


def validate_recording(recording):
    validate_shape(recording)
    if (not isinstance(recording, dict)
            or set(recording) != {"schema_version", "kind", "adapter", "version", "events"}
            or recording.get("schema_version") != "1.0" or recording.get("kind") != "boundary-recording"):
        raise ValueError("Expected a BoundaryRecorder schema 1.0 recording; legacy captures without request IDs must be captured again")
    _metadata(recording["adapter"], "adapter")
    _metadata(recording["version"], "version", 100)
    events = recording["events"]
    if not isinstance(events, list) or not 1 <= len(events) <= 10000:
        raise ValueError("Recording requires between 1 and 10,000 events")
    for event in events:
        if not isinstance(event, dict) or set(event) != {"stage", "timestamp", "request_id", "payload", "payload_redacted"}:
            raise ValueError("Every captured event requires stage, timestamp, request_id, payload and payload_redacted")
        if not isinstance(event["stage"], str) or event["stage"] not in STAGES:
            raise ValueError("Unknown recording stage")
        validate_request_id(event["request_id"])
        _timestamp(event["timestamp"])
        if type(event["payload_redacted"]) is not bool:
            raise ValueError("payload_redacted must be a boolean")
    return deepcopy(recording)


def select_recording(recording, request_id=None):
    recording = validate_recording(recording)
    candidates = {event["request_id"] for event in recording["events"]
                  if event["stage"] in {"framework_input", "adapter_output"}}
    if request_id is None:
        if len(candidates) != 1:
            raise ValueError("Select --request-id when the recording contains multiple or no adapter transactions")
        request_id = next(iter(candidates))
    validate_request_id(request_id)
    if request_id not in candidates:
        raise ValueError("Selected request_id was not captured")
    selected = [(index, event) for index, event in enumerate(recording["events"])
                if event["request_id"] == request_id and event["stage"] in {"framework_input", "adapter_output"}]
    inputs = [(i, e) for i, e in selected if e["stage"] == "framework_input"]
    outputs = [(i, e) for i, e in selected if e["stage"] == "adapter_output"]
    if len(inputs) != 1 or len(outputs) != 1:
        raise ValueError("Selected transaction must have exactly one framework_input and one adapter_output; incomplete or duplicate pairs are ambiguous")
    (input_index, before), (output_index, after) = inputs[0], outputs[0]
    if input_index >= output_index or _timestamp(before["timestamp"]) > _timestamp(after["timestamp"]):
        raise ValueError("Captured adapter_output must follow its framework_input")
    if not isinstance(before["payload"], list) or not isinstance(after["payload"], list):
        raise ValueError("Selected input and output must be message-array JSON payloads")
    return {"adapter": recording["adapter"], "version": recording["version"], "request_id": request_id,
            "original_input": before["payload"], "candidate": after["payload"],
            "payload_redacted": before["payload_redacted"] or after["payload_redacted"],
            "timestamps": {"input": before["timestamp"], "output": after["timestamp"]},
            "event_indexes": [input_index, output_index], "recording_event_count": len(recording["events"])}
