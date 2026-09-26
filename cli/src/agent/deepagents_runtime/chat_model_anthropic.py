"""Anthropic chat model construction for the deepagents runtime."""

from __future__ import annotations

from typing import Any


def build_anthropic_chat_model(config, *, temperature: float):
    from langchain.chat_models import init_chat_model

    from agent.deepagents_runtime.anthropic_thinking_patch import (
        apply_anthropic_empty_thinking_patch,
    )
    from agent.model_catalog import (
        anthropic_model_omits_temperature,
        effective_anthropic_effort,
        get_model_reasoning,
        model_supports_reasoning_effort,
    )

    apply_anthropic_empty_thinking_patch()

    model = config.get("llm.model") or "claude-sonnet-4-5-20250929"
    kwargs: dict[str, Any] = {"max_retries": 5}
    if not anthropic_model_omits_temperature(model):
        kwargs["temperature"] = temperature
    api_key = config.llm_api_key("anthropic")
    if api_key:
        kwargs["api_key"] = api_key
    if model_supports_reasoning_effort("anthropic", model):
        effort, fast = get_model_reasoning(
            config.get("llm.model_reasoning"),
            "anthropic",
            model,
            default_effort=str(config.get("llm.reasoning_effort") or "medium"),
            default_fast=bool(config.get("llm.reasoning_fast", False)),
        )
        kwargs["effort"] = effective_anthropic_effort(effort=effort, fast=fast)
    return init_chat_model(f"anthropic:{model}", **kwargs)
