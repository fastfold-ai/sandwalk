"""OpenRouter chat model construction for the deepagents runtime."""

from __future__ import annotations

from typing import Any

from agent.deepagents_runtime.openrouter_attribution import (
    OPENROUTER_APP_CATEGORIES,
    OPENROUTER_APP_TITLE,
    OPENROUTER_APP_URL,
)

# Same budget as the OpenAI / Anthropic paths (300 s). Without this the
# OpenRouter SDK builds its httpx client with the library default of **5 s**.
# A chat with ~300 tool schemas in the request routinely takes longer than
# that to first byte, so every attempt hit ReadTimeout and the SDK's retry
# loop (max_retries × 150 s) kept the run "Planning next moves" for up to
# twelve minutes with no error. Milliseconds: that is what `timeout_ms` takes.
OPENROUTER_REQUEST_TIMEOUT_MS = 300_000
# Two retries cover a flaky connect; five made a real outage look like a hang.
OPENROUTER_MAX_RETRIES = 2


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
    from agent.model_catalog.param_heal import apply_effort_floor, get_param_heal

    meta = OPENAI_COMPATIBLE_PROVIDERS.get("openrouter", {})
    model = resolve_catalog_model_id(
        config.get("llm.model")
        or str(meta.get("default_model") or "anthropic/claude-sonnet-5")
    )

    heal = get_param_heal(config.get("llm.param_heals"), "openrouter", model)
    kwargs: dict[str, Any] = {
        "model": model,
        "app_url": OPENROUTER_APP_URL,
        "app_title": OPENROUTER_APP_TITLE,
        "app_categories": list(OPENROUTER_APP_CATEGORIES),
        "max_retries": OPENROUTER_MAX_RETRIES,
        "timeout": OPENROUTER_REQUEST_TIMEOUT_MS,
    }
    if not heal["omit_require_parameters"]:
        # Prefer endpoints that accept tools + the params we actually send.
        kwargs["openrouter_provider"] = {"require_parameters": True}
    if not heal["omit_temperature"] and not openrouter_model_omits_temperature(model):
        kwargs["temperature"] = temperature
    api_key = config.llm_api_key("openrouter")
    if api_key:
        kwargs["api_key"] = api_key

    if (
        not heal["omit_reasoning"]
        and model_supports_reasoning_effort("openrouter", model)
    ):
        effort, fast = get_model_reasoning(
            config.get("llm.model_reasoning"),
            "openrouter",
            model,
            default_effort=str(config.get("llm.reasoning_effort") or "medium"),
            default_fast=bool(config.get("llm.reasoning_fast", False)),
        )
        reasoning = effective_openrouter_reasoning(
            effort=effort,
            fast=fast,
            model_id=model,
        )
        reasoning["effort"] = apply_effort_floor(str(reasoning.get("effort") or "medium"), heal)
        kwargs["reasoning"] = reasoning

    return ChatOpenRouter(**kwargs)
