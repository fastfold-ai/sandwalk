"""First-party OpenAI-compatible provider (xAI, NVIDIA, OpenCode Zen) chat models."""

from __future__ import annotations


def build_compatible_chat_model(config, provider: str, *, temperature: float):
    """Route xAI / NVIDIA / OpenCode Zen through a fixed base URL + key.

    OpenCode Zen routes GPT -> Responses API, Claude/Qwen -> Anthropic
    Messages, others -> chat completions.
    """
    from langchain.chat_models import init_chat_model

    from agent.config import OPENAI_COMPATIBLE_PROVIDERS
    from agent.model_catalog import (
        effective_reasoning_effort,
        effective_xai_reasoning_effort,
        get_model_reasoning,
        model_supports_reasoning_effort,
        opencode_anthropic_base_url,
        opencode_model_uses_anthropic,
        opencode_model_uses_responses_api,
    )

    model = config.get("llm.model")
    base_url = config.llm_provider_base_url(provider)
    if not base_url:
        raise ValueError(
            f"deepagents runtime does not support llm.provider '{provider}'. "
            "Use 'anthropic', 'openai', 'xai', 'google', 'nvidia', or 'opencode'."
        )

    meta = OPENAI_COMPATIBLE_PROVIDERS.get(provider, {})
    model = model or str(meta.get("default_model") or "")
    api_key = config.llm_api_key(provider)
    if provider == "opencode" and opencode_model_uses_anthropic(model):
        from agent.model_catalog import (
            anthropic_model_omits_temperature,
            effective_anthropic_effort,
        )

        kwargs = {}
        if not anthropic_model_omits_temperature(model):
            kwargs["temperature"] = temperature
        if api_key:
            kwargs["api_key"] = api_key
        kwargs["base_url"] = opencode_anthropic_base_url(base_url)
        if model_supports_reasoning_effort("opencode", model):
            effort, fast = get_model_reasoning(
                config.get("llm.model_reasoning"),
                "opencode",
                model,
                default_effort=str(config.get("llm.reasoning_effort") or "medium"),
                default_fast=bool(config.get("llm.reasoning_fast", False)),
            )
            kwargs["effort"] = effective_anthropic_effort(
                effort=effort, fast=fast
            )
        return init_chat_model(f"anthropic:{model}", **kwargs)

    kwargs = {}
    if not (
        provider == "opencode" and str(model).strip().lower().startswith("gpt-")
    ):
        kwargs["temperature"] = temperature
    if api_key:
        kwargs["api_key"] = api_key
    kwargs["base_url"] = base_url
    kwargs["use_responses_api"] = bool(
        provider == "opencode" and opencode_model_uses_responses_api(model)
    )
    if model_supports_reasoning_effort(provider, model):
        effort, fast = get_model_reasoning(
            config.get("llm.model_reasoning"),
            provider,
            model,
            default_effort=str(config.get("llm.reasoning_effort") or "medium"),
            default_fast=bool(config.get("llm.reasoning_fast", False)),
        )
        if provider == "xai":
            kwargs["reasoning_effort"] = effective_xai_reasoning_effort(
                effort=effort,
                fast=fast,
                model_id=model,
            )
        else:
            kwargs["reasoning_effort"] = effective_reasoning_effort(
                effort=effort,
                fast=fast,
                model_id=model,
            )
    return init_chat_model(f"openai:{model}", **kwargs)
