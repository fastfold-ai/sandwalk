"""OpenRouter chat model construction for the deepagents runtime."""

from __future__ import annotations

from typing import Any

from agent.deepagents_runtime.openrouter_attribution import (
    OPENROUTER_APP_CATEGORIES,
    OPENROUTER_APP_TITLE,
    OPENROUTER_APP_URL,
)


def build_openrouter_chat_model(config, *, temperature: float):
    """Build a native ``ChatOpenRouter`` with Sandwalk app attribution."""
    from langchain_openrouter import ChatOpenRouter

    from agent.config import OPENAI_COMPATIBLE_PROVIDERS
    from agent.model_catalog import (
        effective_openrouter_reasoning,
        get_model_reasoning,
        model_supports_reasoning_effort,
        openrouter_model_omits_temperature,
        resolve_catalog_model_id,
    )

    meta = OPENAI_COMPATIBLE_PROVIDERS.get("openrouter", {})
    model = resolve_catalog_model_id(
        config.get("llm.model")
        or str(meta.get("default_model") or "anthropic/claude-sonnet-5")
    )

    kwargs: dict[str, Any] = {
        "model": model,
        "app_url": OPENROUTER_APP_URL,
        "app_title": OPENROUTER_APP_TITLE,
        "app_categories": list(OPENROUTER_APP_CATEGORIES),
        # Sandwalk always sends tools — only route to endpoints that accept them.
        "openrouter_provider": {"require_parameters": True},
        "max_retries": 2,
    }
    if not openrouter_model_omits_temperature(model):
        kwargs["temperature"] = temperature
    api_key = config.llm_api_key("openrouter")
    if api_key:
        kwargs["api_key"] = api_key

    if model_supports_reasoning_effort("openrouter", model):
        effort, fast = get_model_reasoning(
            config.get("llm.model_reasoning"),
            "openrouter",
            model,
            default_effort=str(config.get("llm.reasoning_effort") or "medium"),
            default_fast=bool(config.get("llm.reasoning_fast", False)),
        )
        kwargs["reasoning"] = effective_openrouter_reasoning(
            effort=effort,
            fast=fast,
            model_id=model,
        )

    return ChatOpenRouter(**kwargs)
