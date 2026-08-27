"""Cerebras chat model construction (langchain-cerebras)."""

from __future__ import annotations

from typing import Any


def build_cerebras_chat_model(config, *, temperature: float):
    """Build a native ``ChatCerebras`` for Cerebras Cloud."""
    from langchain_cerebras import ChatCerebras

    from agent.config import OPENAI_COMPATIBLE_PROVIDERS
    from agent.model_catalog import resolve_catalog_model_id

    meta = OPENAI_COMPATIBLE_PROVIDERS.get("cerebras", {})
    model = resolve_catalog_model_id(
        config.get("llm.model") or str(meta.get("default_model") or "gpt-oss-120b")
    )
    kwargs: dict[str, Any] = {
        "model": model,
        "temperature": temperature,
        "max_retries": 2,
    }
    api_key = config.llm_api_key("cerebras")
    if api_key:
        kwargs["api_key"] = api_key
    return ChatCerebras(**kwargs)
