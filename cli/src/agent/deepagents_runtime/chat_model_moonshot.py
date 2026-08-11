"""Moonshot / Kimi chat model construction for the deepagents runtime."""

from __future__ import annotations

import os
from typing import Any


def build_moonshot_chat_model(config, *, temperature: float):
    """Build a native ``ChatMoonshot`` for first-party Moonshot / Kimi models."""
    from langchain_moonshot import ChatMoonshot

    from agent.config import OPENAI_COMPATIBLE_PROVIDERS
    from agent.model_catalog import (
        effective_moonshot_thinking,
        get_model_reasoning,
        moonshot_model_supports_thinking_toggle,
        resolve_catalog_model_id,
    )

    meta = OPENAI_COMPATIBLE_PROVIDERS.get("moonshot", {})
    model = resolve_catalog_model_id(
        config.get("llm.model") or str(meta.get("default_model") or "kimi-k3")
    )
    model_lower = str(model or "").strip().lower()

    kwargs: dict[str, Any] = {
        "model": model,
        "stream_usage": True,
        "max_retries": 2,
    }
    api_key = config.llm_api_key("moonshot")
    if api_key:
        kwargs["api_key"] = api_key

    base_url = (
        str(os.environ.get("MOONSHOT_API_BASE") or "").strip()
        or str(meta.get("base_url") or "").strip()
        or None
    )
    if base_url:
        kwargs["base_url"] = base_url

    # k3 always reasons; only supported effort is ``max``.
    if model_lower.startswith("kimi-k3"):
        kwargs["reasoning_effort"] = "max"
        # API rejects any temperature other than 1.0 for k3.
        kwargs["temperature"] = 1.0
    elif moonshot_model_supports_thinking_toggle(model):
        effort, fast = get_model_reasoning(
            config.get("llm.model_reasoning"),
            "moonshot",
            model,
            default_effort=str(config.get("llm.reasoning_effort") or "medium"),
            default_fast=bool(config.get("llm.reasoning_fast", False)),
        )
        thinking = effective_moonshot_thinking(effort=effort, fast=fast)
        kwargs["thinking"] = thinking
        # API requires 1.0 with thinking, 0.6 without — omit caller temperature.
        kwargs["temperature"] = 1.0 if thinking else 0.6
    elif model_lower.startswith("kimi-k2.7"):
        # Thinking always on; do not pass thinking=disabled.
        kwargs["thinking"] = True
        kwargs["temperature"] = 1.0
    else:
        kwargs["temperature"] = temperature

    return ChatMoonshot(**kwargs)
