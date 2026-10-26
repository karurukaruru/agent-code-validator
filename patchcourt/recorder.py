"""Explicit opt-in boundary recording. No global framework monkeypatch."""
from copy import deepcopy
from uuid import uuid4
from .evidence import canonical, now, sanitize, validate_shape
from .semantic import compare_messages

STAGES = {"framework_input", "adapter_output", "outbound_payload", "stream_event", "provider_response"}


def _json_payload(value):
    """Reject Python-only types before json.dumps can coerce or hide them."""
    validate_shape(value)
    pending = [value]
    while pending:
        item = pending.pop()
        if item is None or type(item) in (str, bool, int, float):
            continue
        if type(item) is list:
            pending.extend(item)
        elif type(item) is dict and all(type(key) is str for key in item):
            pending.extend(item.values())
        else:
            raise ValueError("Recorder accepts JSON types only; tuples, sets and custom objects are unsupported")


class BoundaryRecorder:
    def __init__(self, adapter_name, version):
        self.adapter_name, self.version = adapter_name, version
        self.events = []
        self._captured_bytes = 0

    def record(self, stage, payload, request_id=None):
        if stage not in STAGES:
            raise ValueError("Unknown boundary stage")
        if len(self.events) >= 10000:
            raise ValueError("Recorder event budget exhausted")
        if request_id is not None:
            from .recording import validate_request_id
            validate_request_id(request_id)
        _json_payload(payload)
        cleaned = sanitize(payload)
        original, captured = canonical(payload), canonical(cleaned)
        if len(captured.encode("utf-8")) > 1_000_000:
            raise ValueError("Recorder payload exceeds 1 MB")
        size = len(captured.encode("utf-8"))
        if self._captured_bytes + size > 4_000_000:
            raise ValueError("Recorder aggregate payload exceeds 4 MB")
        self.events.append({"stage": stage, "timestamp": now(), "request_id": request_id,
                            "payload": cleaned, "payload_redacted": original != captured})
        self._captured_bytes += size

    def transform(self, messages, adapter, request_id=None):
        request_id = request_id if request_id is not None else uuid4().hex
        self.record("framework_input", messages, request_id)
        original = deepcopy(messages)
        output = adapter(messages)
        self.record("adapter_output", output, request_id)
        return output, compare_messages(original, output)

    def save(self, path):
        import json
        from pathlib import Path
        recording = {"schema_version": "1.0", "kind": "boundary-recording",
                     "adapter": self.adapter_name, "version": self.version, "events": deepcopy(self.events)}
        _json_payload(recording)
        # Credentials can be loaded after capture. Freeze one final sanitized
        # snapshot and propagate every payload change before serialization.
        cleaned = sanitize(recording)
        if canonical({k: v for k, v in recording.items() if k != "events"}) != canonical({k: v for k, v in cleaned.items() if k != "events"}):
            raise ValueError("Credential redaction would change recording identity; choose non-sensitive adapter and version labels")
        for original, captured in zip(recording["events"], cleaned["events"]):
            if set(original) != set(captured) or canonical({k: v for k, v in original.items() if k not in {"payload", "payload_redacted"}}) != canonical({k: v for k, v in captured.items() if k not in {"payload", "payload_redacted"}}):
                raise ValueError("Credential redaction would change event identity; choose non-sensitive request IDs")
            captured["payload_redacted"] = original["payload_redacted"] or canonical(original["payload"]) != canonical(captured["payload"])
        encoded = (json.dumps(cleaned, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
        if len(encoded) > 8_000_000:
            raise ValueError("Recorder file exceeds 8 MB")
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(encoded)  # No second sanitizer can silently erase flags.
        self.events[:] = deepcopy(cleaned["events"])
        return cleaned
