"""Configuration and OpenAI-compatible chat-completion client."""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ConfigurationError(ValueError):
    """Raised when LLM configuration is missing or invalid."""


class LLMError(RuntimeError):
    """Raised when a model request fails or returns an unusable response."""


OPENAI_COMPATIBLE_PROVIDER = "openai-compatible"
VOLCENGINE_CODING_PLAN_PROVIDER = "volcengine-coding-plan"
VOLCENGINE_AGENT_PLAN_PROVIDER = "volcengine-agent-plan"
DEFAULT_REPORT_LANGUAGE = "zh-CN"

_REPORT_LANGUAGE_ALIASES = {
    "zh": "zh-CN",
    "zh-cn": "zh-CN",
    "chinese": "zh-CN",
    "simplified-chinese": "zh-CN",
    "en": "en",
    "en-us": "en",
    "english": "en",
}

_PROVIDER_ALIASES = {
    "openai": OPENAI_COMPATIBLE_PROVIDER,
    "openai-compatible": OPENAI_COMPATIBLE_PROVIDER,
    "volcengine-coding": VOLCENGINE_CODING_PLAN_PROVIDER,
    "volcengine-coding-plan": VOLCENGINE_CODING_PLAN_PROVIDER,
    "ark-coding-plan": VOLCENGINE_CODING_PLAN_PROVIDER,
    "volcengine-agent": VOLCENGINE_AGENT_PLAN_PROVIDER,
    "volcengine-agent-plan": VOLCENGINE_AGENT_PLAN_PROVIDER,
    "ark-agent-plan": VOLCENGINE_AGENT_PLAN_PROVIDER,
}

_VOLCENGINE_PLAN_DEFAULTS = {
    VOLCENGINE_CODING_PLAN_PROVIDER: {
        "base_url": "https://ark.cn-beijing.volces.com/api/coding/v3",
        "anthropic_base_url": "https://ark.cn-beijing.volces.com/api/coding",
        "model": "ark-code-latest",
        "key_env": "ARK_CODING_PLAN_API_KEY",
        "label": "Volcengine Ark Coding Plan",
    },
    VOLCENGINE_AGENT_PLAN_PROVIDER: {
        "base_url": "https://ark.cn-beijing.volces.com/api/plan/v3",
        "anthropic_base_url": "https://ark.cn-beijing.volces.com/api/plan",
        "model": "",
        "key_env": "ARK_AGENT_PLAN_API_KEY",
        "label": "Volcengine Ark Agent Plan",
    },
}


@dataclass(frozen=True)
class LLMConfig:
    api_key: str
    model: str
    base_url: str | None = None
    timeout: float = 120.0
    provider: str = OPENAI_COMPATIBLE_PROVIDER
    report_language: str = DEFAULT_REPORT_LANGUAGE


def normalize_report_language(value: object) -> str:
    raw = str(value or DEFAULT_REPORT_LANGUAGE).strip()
    language = _REPORT_LANGUAGE_ALIASES.get(raw.lower().replace("_", "-"))
    if language is None:
        raise ConfigurationError(
            f"Unsupported report_language {raw!r}. Use 'zh-CN' or 'en'."
        )
    return language


def load_config(config_path: str | Path = "config.json") -> LLMConfig:
    """Load JSON configuration, with environment variables as safe fallbacks."""
    path = Path(config_path).expanduser()
    data: dict[str, Any] = {}
    if path.exists():
        if not path.is_file():
            raise ConfigurationError(f"Configuration path is not a file: {path}")
        try:
            # utf-8-sig accepts ordinary UTF-8 as well as files saved by some
            # Windows editors with a byte-order mark.
            loaded = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigurationError(f"Could not read configuration {path}: {exc}") from exc
        if not isinstance(loaded, dict):
            raise ConfigurationError("Configuration must be a JSON object")
        data = loaded

    configured_provider = data.get("provider") or os.getenv("ACV_PROVIDER")
    configured_base_url = str(data.get("base_url") or "").strip().rstrip("/")
    if not configured_provider and configured_base_url:
        for candidate_provider, defaults in _VOLCENGINE_PLAN_DEFAULTS.items():
            if configured_base_url in {
                str(defaults["base_url"]),
                str(defaults["anthropic_base_url"]),
            }:
                configured_provider = candidate_provider
                break
    raw_provider = str(configured_provider or OPENAI_COMPATIBLE_PROVIDER).strip()
    provider_key = raw_provider.lower().replace("_", "-")
    provider = _PROVIDER_ALIASES.get(provider_key)
    if provider is None:
        supported = ", ".join(
            (
                OPENAI_COMPATIBLE_PROVIDER,
                VOLCENGINE_CODING_PLAN_PROVIDER,
                VOLCENGINE_AGENT_PLAN_PROVIDER,
            )
        )
        raise ConfigurationError(
            f"Unsupported provider {raw_provider!r}. Supported providers: {supported}."
        )

    plan_defaults = _VOLCENGINE_PLAN_DEFAULTS.get(provider)
    provider_key_env = str(plan_defaults["key_env"]) if plan_defaults else ""
    api_key = str(
        data.get("api_key")
        or (os.getenv(provider_key_env) if provider_key_env else None)
        or (os.getenv("ARK_API_KEY") if plan_defaults else None)
        or os.getenv("OPENAI_API_KEY")
        or ""
    ).strip()
    default_model = str(plan_defaults["model"]) if plan_defaults else ""
    model = str(data.get("model") or os.getenv("ACV_MODEL") or default_model).strip()
    if data.get("base_url"):
        base_url_value = data["base_url"]
    elif plan_defaults:
        base_url_value = plan_defaults["base_url"]
    else:
        base_url_value = os.getenv("OPENAI_BASE_URL")
    base_url = str(base_url_value).strip() if base_url_value else None
    report_language = normalize_report_language(
        data.get("report_language") or os.getenv("ACV_REPORT_LANGUAGE")
    )

    if plan_defaults:
        expected_base_url = str(plan_defaults["base_url"])
        anthropic_base_url = str(plan_defaults["anthropic_base_url"])
        normalized_base_url = (base_url or "").rstrip("/")
        if normalized_base_url == anthropic_base_url:
            normalized_base_url = expected_base_url
        if normalized_base_url != expected_base_url:
            raise ConfigurationError(
                f"{plan_defaults['label']} requires base_url {expected_base_url!r} "
                "so requests use the subscribed plan quota. Remove base_url to use this default."
            )
        base_url = expected_base_url

    if not api_key:
        key_hint = (
            f", {provider_key_env}, or ARK_API_KEY"
            if plan_defaults
            else " or OPENAI_API_KEY"
        )
        raise ConfigurationError(
            f"Missing API key. Set api_key in {path}{key_hint}."
        )
    if api_key.upper().startswith("REPLACE_WITH_"):
        raise ConfigurationError(
            f"API key in {path} is still a template placeholder. Replace it with the real key."
        )
    if not model:
        model_hint = (
            " Use a model ID currently enabled in the Agent Plan console."
            if provider == VOLCENGINE_AGENT_PLAN_PROVIDER
            else ""
        )
        raise ConfigurationError(
            f"Missing model. Set model in {path} or the ACV_MODEL environment variable."
            + model_hint
        )
    if model.upper().startswith("REPLACE_WITH_"):
        raise ConfigurationError(
            f"Model in {path} is still a template placeholder. Replace it with a real model ID."
        )

    try:
        timeout = float(data.get("timeout", 120.0))
    except (TypeError, ValueError) as exc:
        raise ConfigurationError("timeout must be numeric") from exc
    if not math.isfinite(timeout) or timeout <= 0:
        raise ConfigurationError("timeout must be a finite number greater than zero")

    return LLMConfig(
        api_key=api_key,
        model=model,
        base_url=base_url,
        timeout=timeout,
        provider=provider,
        report_language=report_language,
    )


class LLMClient:
    """Small wrapper around the OpenAI Python SDK's compatible chat API."""

    def __init__(self, config: LLMConfig):
        self.config = config
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - depends on installation
            raise ConfigurationError(
                "The openai package is not installed. Run: pip install -r requirements.txt"
            ) from exc

        kwargs: dict[str, Any] = {
            "api_key": config.api_key,
            "timeout": config.timeout,
        }
        if config.base_url:
            kwargs["base_url"] = config.base_url
        self._client = OpenAI(**kwargs)
        self._native_tools_supported: bool | None = None

    def _raise_request_error(self, exc: Exception) -> None:
        status_code = getattr(exc, "status_code", None)
        if status_code in (401, 403):
            plan_defaults = _VOLCENGINE_PLAN_DEFAULTS.get(self.config.provider)
            if plan_defaults:
                raise LLMError(
                    f"{plan_defaults['label']} authentication failed ({status_code}). "
                    "Use an API key created for that same plan; Coding Plan, Agent Plan, "
                    "and standard Ark API keys are not interchangeable."
                ) from exc
            raise LLMError(
                f"LLM authentication failed ({status_code}). Check the API key and account permissions."
            ) from exc
        if status_code == 404:
            raise LLMError(
                "LLM endpoint or model was not found (404). Check base_url and model; "
                "base_url should be the API root, not the full /chat/completions URL."
            ) from exc
        if status_code == 429:
            raise LLMError(
                "LLM rate or quota limit reached (429). Check account balance, quota, and retry later."
            ) from exc
        raise LLMError(f"LLM request failed: {exc}") from exc

    def complete(self, system_prompt: str, user_content: str) -> str:
        try:
            response = self._client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
            )
        except Exception as exc:  # SDK/provider exceptions vary by compatible API
            self._raise_request_error(exc)

        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError, TypeError) as exc:
            raise LLMError("LLM returned an unexpected response shape") from exc
        if not isinstance(content, str):
            raise LLMError("LLM returned non-text review content")
        if not content.strip():
            raise LLMError("LLM returned an empty review")
        return content.strip()

    def complete_agent_action(
        self,
        system_prompt: str,
        user_content: str,
        tools: list[dict[str, object]],
    ) -> str:
        """Prefer native tool calling and fall back to the prompt's JSON protocol."""
        if self._native_tools_supported is False:
            return self.complete(system_prompt, user_content)

        try:
            response = self._client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                tools=tools,
                tool_choice="auto",
            )
        except Exception as exc:  # SDK/provider exceptions vary by compatible API
            # OpenAI-compatible providers commonly use 400 or 422 when their
            # selected model/API does not implement the tools parameters.
            if getattr(exc, "status_code", None) in (400, 422):
                self._native_tools_supported = False
                return self.complete(system_prompt, user_content)
            self._raise_request_error(exc)

        try:
            message = response.choices[0].message
        except (AttributeError, IndexError, TypeError) as exc:
            raise LLMError("LLM returned an unexpected agent response shape") from exc

        tool_calls = getattr(message, "tool_calls", None)
        if tool_calls:
            try:
                function = tool_calls[0].function
                name = function.name
                raw_arguments = function.arguments or "{}"
                arguments = json.loads(raw_arguments)
            except (AttributeError, IndexError, TypeError, json.JSONDecodeError) as exc:
                raise LLMError("LLM returned an invalid native tool call") from exc
            if not isinstance(name, str) or not isinstance(arguments, dict):
                raise LLMError("LLM returned an invalid native tool call")
            self._native_tools_supported = True
            return json.dumps(
                {"action": name, "arguments": arguments}, ensure_ascii=False
            )

        content = getattr(message, "content", None)
        if not isinstance(content, str) or not content.strip():
            raise LLMError("LLM returned neither a native tool call nor a JSON action")
        return content.strip()
