"""OpenAI cloud/compatible chat model construction for the deepagents runtime."""

from __future__ import annotations


def build_openai_chat_model(config, *, temperature: float):
    from langchain.chat_models import init_chat_model

    from agent.config import Config
    from agent.model_catalog import (
        effective_reasoning_effort,
        get_model_reasoning,
        model_supports_reasoning_effort,
        openai_model_requires_responses_api,
    )

    model = config.get("llm.model") or "gpt-5.6-sol"
    kwargs = {}
    # GPT-5 chat models reject a custom temperature; omit it for that family.
    if not str(model).strip().lower().startswith("gpt-5"):
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
    if is_openai_cloud and model_supports_reasoning_effort("openai", model):
        effort, fast = get_model_reasoning(
            config.get("llm.model_reasoning"),
            "openai",
            model,
            default_effort=str(config.get("llm.reasoning_effort") or "medium"),
            default_fast=bool(config.get("llm.reasoning_fast", False)),
        )
        kwargs["reasoning_effort"] = effective_reasoning_effort(
            effort=effort,
            fast=fast,
            model_id=model,
        )
    return init_chat_model(f"openai:{model}", **kwargs)
