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


@dataclass(frozen=True)
class LLMConfig:
    api_key: str
    model: str
    base_url: str | None = None
    timeout: float = 120.0


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

    api_key = str(data.get("api_key") or os.getenv("OPENAI_API_KEY") or "").strip()
    model = str(data.get("model") or os.getenv("ACV_MODEL") or "").strip()
    base_url_value = data.get("base_url") or os.getenv("OPENAI_BASE_URL")
    base_url = str(base_url_value).strip() if base_url_value else None

    if not api_key:
        raise ConfigurationError(
            f"Missing API key. Set api_key in {path} or the OPENAI_API_KEY environment variable."
        )
    if not model:
        raise ConfigurationError(
            f"Missing model. Set model in {path} or the ACV_MODEL environment variable."
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
            status_code = getattr(exc, "status_code", None)
            if status_code in (401, 403):
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

        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError, TypeError) as exc:
            raise LLMError("LLM returned an unexpected response shape") from exc
        if not isinstance(content, str):
            raise LLMError("LLM returned non-text review content")
        if not content.strip():
            raise LLMError("LLM returned an empty review")
        return content.strip()
