from __future__ import annotations


class FakeLLMProvider:
    """Deterministic completion provider for agent tests; never uses a real API."""

    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    def complete(self, system_prompt: str, user_content: str) -> str:
        self.calls.append((system_prompt, user_content))
        if not self.responses:
            raise AssertionError("FakeLLMProvider ran out of configured responses")
        return self.responses.pop(0)
