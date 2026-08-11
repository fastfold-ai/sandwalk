"""Google Gemini chat model construction for the deepagents runtime."""

from __future__ import annotations

from typing import Any


def build_google_chat_model(config, *, temperature: float):
    """Google Gemini must use the native GenAI SDK.

    Gemini 3+ requires thought_signature to be echoed on tool-call turns; the
    OpenAI-compatible Generative Language endpoint drops those and returns
    HTTP 400.
    """
    from langchain.chat_models import init_chat_model

    from agent.config import OPENAI_COMPATIBLE_PROVIDERS
    from agent.model_catalog import (
        effective_gemini_thinking_level,
        get_model_reasoning,
        google_model_supports_thinking_level,
        model_supports_reasoning_effort,
        resolve_catalog_model_id,
    )

    meta = OPENAI_COMPATIBLE_PROVIDERS.get("google", {})
    model = resolve_catalog_model_id(
        config.get("llm.model") or str(meta.get("default_model") or "gemini-3.5-flash")
    )
    kwargs: dict[str, Any] = {"temperature": temperature}
    api_key = config.llm_api_key("google")
    if api_key:
        kwargs["api_key"] = api_key
    if model_supports_reasoning_effort("google", model) or google_model_supports_thinking_level(
        model
    ):
        effort, fast = get_model_reasoning(
            config.get("llm.model_reasoning"),
            "google",
            model,
            default_effort=str(config.get("llm.reasoning_effort") or "medium"),
            default_fast=bool(config.get("llm.reasoning_fast", False)),
        )
        kwargs["thinking_level"] = effective_gemini_thinking_level(
            effort=effort, fast=fast
        )
    return init_chat_model(f"google_genai:{model}", **kwargs)
