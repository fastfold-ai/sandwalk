"""Groq chat model construction (langchain-groq)."""

from __future__ import annotations

from typing import Any


def build_groq_chat_model(config, *, temperature: float):
    """Build a native ``ChatGroq`` for Groq Cloud."""
    from langchain_groq import ChatGroq

    from agent.config import OPENAI_COMPATIBLE_PROVIDERS
    from agent.model_catalog import resolve_catalog_model_id

    meta = OPENAI_COMPATIBLE_PROVIDERS.get("groq", {})
    model = resolve_catalog_model_id(
        config.get("llm.model")
        or str(meta.get("default_model") or "llama-3.3-70b-versatile")
    )
    kwargs: dict[str, Any] = {
        "model": model,
        "temperature": temperature,
        "max_retries": 2,
    }
    api_key = config.llm_api_key("groq")
    if api_key:
        kwargs["api_key"] = api_key
    return ChatGroq(**kwargs)
