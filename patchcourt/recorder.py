"""Explicit opt-in boundary recording. No global framework monkeypatch."""
from .evidence import now, sanitize, write_json
from .semantic import compare_messages


class BoundaryRecorder:
    def __init__(self, adapter_name, version):
        self.adapter_name, self.version = adapter_name, version
        self.events = []

    def record(self, stage, payload):
        if stage not in {"framework_input", "adapter_output", "outbound_payload", "stream_event", "provider_response"}:
            raise ValueError("Unknown boundary stage")
        if len(self.events) >= 10000:
            raise ValueError("Recorder event budget exhausted")
        self.events.append({"stage": stage, "timestamp": now(), "payload": sanitize(payload)})

    def transform(self, messages, adapter):
        self.record("framework_input", messages)
        output = adapter(messages)
        self.record("adapter_output", output)
        return output, compare_messages(messages, output)

    def save(self, path):
        return write_json(path, {"adapter": self.adapter_name, "version": self.version, "events": self.events})
