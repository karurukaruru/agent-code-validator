import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from acv.llm_client import ConfigurationError, LLMClient, LLMConfig, LLMError, load_config


def test_load_config_from_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ACV_MODEL", raising=False)
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "api_key": "secret",
                "base_url": "https://provider.example/v1",
                "model": "review-model",
                "timeout": 30,
            }
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.api_key == "secret"
    assert config.base_url == "https://provider.example/v1"
    assert config.model == "review-model"
    assert config.timeout == 30


def test_load_config_uses_environment_without_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "env-secret")
    monkeypatch.setenv("ACV_MODEL", "env-model")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://env.example/v1")

    config = load_config(tmp_path / "missing.json")

    assert config.api_key == "env-secret"
    assert config.model == "env-model"
    assert config.base_url == "https://env.example/v1"


def test_load_config_accepts_utf8_bom(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        '{"api_key":"secret","model":"review-model"}',
        encoding="utf-8-sig",
    )

    config = load_config(config_path)

    assert config.api_key == "secret"
    assert config.model == "review-model"


def test_load_config_rejects_missing_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ACV_MODEL", raising=False)

    with pytest.raises(ConfigurationError, match="Missing API key"):
        load_config(tmp_path / "missing.json")


def test_completion_does_not_set_output_token_limit() -> None:
    captured: dict[str, object] = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            message = SimpleNamespace(content="[]")
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    client = object.__new__(LLMClient)
    client.config = LLMConfig(api_key="secret", model="model")
    client._client = SimpleNamespace(
        chat=SimpleNamespace(completions=FakeCompletions())
    )

    assert client.complete("system", "user") == "[]"
    assert "max_tokens" not in captured
    assert "max_completion_tokens" not in captured
    assert "temperature" not in captured


def test_load_config_rejects_non_finite_timeout(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        '{"api_key":"secret","model":"model","timeout":"NaN"}',
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError, match="finite number"):
        load_config(config_path)


def test_completion_rejects_non_text_content() -> None:
    class FakeCompletions:
        def create(self, **kwargs):
            message = SimpleNamespace(content=[{"type": "text", "text": "[]"}])
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    client = object.__new__(LLMClient)
    client.config = LLMConfig(api_key="secret", model="model")
    client._client = SimpleNamespace(
        chat=SimpleNamespace(completions=FakeCompletions())
    )

    with pytest.raises(LLMError, match="non-text"):
        client.complete("system", "user")


def test_completion_explains_not_found_error() -> None:
    class NotFoundError(Exception):
        status_code = 404

    class FakeCompletions:
        def create(self, **kwargs):
            raise NotFoundError("not found")

    client = object.__new__(LLMClient)
    client.config = LLMConfig(api_key="secret", model="model")
    client._client = SimpleNamespace(
        chat=SimpleNamespace(completions=FakeCompletions())
    )

    with pytest.raises(LLMError, match="API root"):
        client.complete("system", "user")
