import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from acv.llm_client import (
    ConfigurationError,
    LLMClient,
    LLMConfig,
    LLMError,
    VOLCENGINE_AGENT_PLAN_PROVIDER,
    VOLCENGINE_CODING_PLAN_PROVIDER,
    load_config,
)


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


def test_load_config_applies_volcengine_coding_plan_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        '{"provider":"volcengine-coding-plan","api_key":"ark-secret"}',
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.provider == VOLCENGINE_CODING_PLAN_PROVIDER
    assert config.base_url == "https://ark.cn-beijing.volces.com/api/coding/v3"
    assert config.model == "ark-code-latest"


def test_load_config_applies_volcengine_agent_plan_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        '{"provider":"volcengine_agent_plan","model":"doubao-model"}',
        encoding="utf-8",
    )
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setenv("ARK_AGENT_PLAN_API_KEY", "agent-plan-secret")
        config = load_config(config_path)

    assert config.provider == VOLCENGINE_AGENT_PLAN_PROVIDER
    assert config.api_key == "agent-plan-secret"
    assert config.base_url == "https://ark.cn-beijing.volces.com/api/plan/v3"
    assert config.model == "doubao-model"


def test_load_config_rejects_wrong_plan_gateway(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "provider": "volcengine-coding-plan",
                "api_key": "ark-secret",
                "base_url": "https://ark.cn-beijing.volces.com/api/v3",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError, match="subscribed plan quota"):
        load_config(config_path)


def test_load_config_converts_volcengine_anthropic_gateway_to_openai(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "api_key": "ark-secret",
                "base_url": "https://ark.cn-beijing.volces.com/api/coding",
                "model": "ark-code-latest",
            }
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.provider == VOLCENGINE_CODING_PLAN_PROVIDER
    assert config.base_url == "https://ark.cn-beijing.volces.com/api/coding/v3"


def test_load_config_requires_agent_plan_model(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        '{"provider":"volcengine-agent-plan","api_key":"ark-secret"}',
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError, match="Agent Plan console"):
        load_config(config_path)


def test_load_config_rejects_unedited_template_placeholders(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        '{"provider":"volcengine-agent-plan",'
        '"api_key":"REPLACE_WITH_YOUR_AGENT_PLAN_API_KEY",'
        '"model":"REPLACE_WITH_MODEL_ID_FROM_AGENT_PLAN_CONSOLE"}',
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError, match="template placeholder"):
        load_config(config_path)


def test_load_config_normalizes_report_language(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        '{"api_key":"secret","model":"model","report_language":"English"}',
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.report_language == "en"


def test_load_config_rejects_unknown_report_language(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        '{"api_key":"secret","model":"model","report_language":"fr"}',
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError, match="Use 'zh-CN' or 'en'"):
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


def test_volcengine_auth_error_explains_plan_keys_are_distinct() -> None:
    class AuthenticationError(Exception):
        status_code = 401

    class FakeCompletions:
        def create(self, **kwargs):
            raise AuthenticationError("unauthorized")

    client = object.__new__(LLMClient)
    client.config = LLMConfig(
        api_key="secret",
        model="ark-code-latest",
        provider=VOLCENGINE_CODING_PLAN_PROVIDER,
    )
    client._client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))

    with pytest.raises(LLMError, match="not interchangeable"):
        client.complete("system", "user")


def test_agent_action_uses_native_tool_call() -> None:
    class FakeCompletions:
        def create(self, **kwargs):
            function = SimpleNamespace(
                name="read_file",
                arguments='{"path":"app.py","start_line":1,"end_line":20}',
            )
            message = SimpleNamespace(
                content=None,
                tool_calls=[SimpleNamespace(function=function)],
            )
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    client = object.__new__(LLMClient)
    client.config = LLMConfig(api_key="secret", model="model")
    client._native_tools_supported = None
    client._client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))

    raw = client.complete_agent_action("system", "user", [{"type": "function"}])

    assert json.loads(raw) == {
        "action": "read_file",
        "arguments": {"path": "app.py", "start_line": 1, "end_line": 20},
    }
    assert client._native_tools_supported is True


def test_agent_action_falls_back_to_json_when_provider_rejects_tools() -> None:
    captured: list[dict[str, object]] = []

    class UnsupportedToolsError(Exception):
        status_code = 400

    class FakeCompletions:
        def create(self, **kwargs):
            captured.append(kwargs)
            if "tools" in kwargs:
                raise UnsupportedToolsError("tools are unsupported")
            message = SimpleNamespace(
                content='{"action":"finish","reason":"fallback works"}'
            )
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    client = object.__new__(LLMClient)
    client.config = LLMConfig(api_key="secret", model="model")
    client._native_tools_supported = None
    client._client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))

    raw = client.complete_agent_action("system", "user", [{"type": "function"}])

    assert json.loads(raw)["action"] == "finish"
    assert client._native_tools_supported is False
    assert len(captured) == 2
    assert "tools" in captured[0]
    assert "tools" not in captured[1]
