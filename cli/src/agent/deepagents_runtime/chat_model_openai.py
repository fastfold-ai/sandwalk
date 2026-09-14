"""OpenAI cloud/compatible chat model construction for the deepagents runtime."""

from __future__ import annotations

# LangChain's openai default is 120s between parsed stream chunks. Reasoning
# models (Grok, etc.) often pause longer mid-response while TCP stayalives
# still look healthy — 300s keeps the stall guard without failing healthy runs.
STREAM_CHUNK_TIMEOUT_S = 300.0


def _active_compatible_backend(config) -> str | None:
    """Return the active OpenAI-compatible profile backend, if any."""
    try:
        profile = config.get_openai_profile()
    except Exception:  # noqa: BLE001
        profile = None
    if not isinstance(profile, dict):
        return None
    backend = str(profile.get("backend") or "").strip().lower() or None
    if backend in {None, "", "openai"}:
        return None
    return backend


def build_openai_chat_model(config, *, temperature: float):
    from langchain.chat_models import init_chat_model

    from agent.config import Config
    from agent.model_catalog import (
        compatible_profile_supports_thinking,
        effective_reasoning_effort,
        effective_unsloth_enable_thinking,
        get_model_reasoning,
        model_supports_reasoning_effort,
        openai_model_requires_responses_api,
    )
    from agent.model_catalog.param_heal import apply_effort_floor, get_param_heal

    model = config.get("llm.model") or "gpt-5.6-sol"
    heal = get_param_heal(config.get("llm.param_heals"), "openai", model)
    kwargs = {}
    # GPT-5 / GPT-6 reject a custom temperature; learned heals do the same.
    model_l = str(model).strip().lower()
    omits_temp = (
        heal["omit_temperature"]
        or model_l.startswith("gpt-5")
        or model_l.startswith("gpt-6")
    )
    if not omits_temp:
        kwargs["temperature"] = temperature
    api_key = config.llm_api_key("openai")
    if api_key:
        kwargs["api_key"] = api_key
    base_url = config.llm_openai_base_url()
    if base_url:
        kwargs["base_url"] = base_url
    # Default to chat completions for OpenAI-compatible local endpoints
    # (Ollama, LM Studio, vLLM, ...). Codex + GPT-5.6 on OpenAI cloud need
    # Responses (tools + reasoning_effort are rejected on chat completions).
    is_openai_cloud = (not base_url) or Config._is_openai_managed_base_url(base_url)
    use_responses = bool(
        is_openai_cloud and openai_model_requires_responses_api(model)
    )
    kwargs["use_responses_api"] = use_responses
    # Ask OpenAI-compatible servers (oMLX, Ollama, Unsloth, …) to include
    # usage on the final stream chunk so local models don't report 0 tokens.
    kwargs["stream_usage"] = True
    kwargs["stream_chunk_timeout"] = STREAM_CHUNK_TIMEOUT_S
    kwargs["max_retries"] = 5
    if (
        is_openai_cloud
        and not heal["omit_reasoning"]
        and model_supports_reasoning_effort("openai", model)
    ):
        effort, fast = get_model_reasoning(
            config.get("llm.model_reasoning"),
            "openai",
            model,
            default_effort=str(config.get("llm.reasoning_effort") or "medium"),
            default_fast=bool(config.get("llm.reasoning_fast", False)),
        )
        kwargs["reasoning_effort"] = apply_effort_floor(
            effective_reasoning_effort(
                effort=effort,
                fast=fast,
                model_id=model,
            ),
            heal,
        )
    elif not is_openai_cloud:
        backend = _active_compatible_backend(config)
        if compatible_profile_supports_thinking(backend):
            effort, fast = get_model_reasoning(
                config.get("llm.model_reasoning"),
                "local",
                model,
                default_effort=str(config.get("llm.reasoning_effort") or "medium"),
                default_fast=bool(config.get("llm.reasoning_fast", False)),
            )
            enable_thinking = effective_unsloth_enable_thinking(
                effort=effort, fast=fast
            )
            kwargs["extra_body"] = {"enable_thinking": enable_thinking}
    return init_chat_model(f"openai:{model}", **kwargs)
