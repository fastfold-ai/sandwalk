"""Fireworks AI chat model construction (langchain-fireworks)."""

from __future__ import annotations

from typing import Any


def build_fireworks_chat_model(config, *, temperature: float):
    """Build a native ``ChatFireworks`` for Fireworks AI."""
    from langchain_fireworks import ChatFireworks

    from agent.config import OPENAI_COMPATIBLE_PROVIDERS
    from agent.model_catalog import resolve_catalog_model_id

    meta = OPENAI_COMPATIBLE_PROVIDERS.get("fireworks", {})
    model = resolve_catalog_model_id(
        config.get("llm.model")
        or str(meta.get("default_model") or "accounts/fireworks/models/llama-v3p3-70b-instruct")
    )
    kwargs: dict[str, Any] = {
        "model": model,
        "temperature": temperature,
        "max_retries": 2,
    }
    api_key = config.llm_api_key("fireworks")
    if api_key:
        kwargs["api_key"] = api_key
    return ChatFireworks(**kwargs)
