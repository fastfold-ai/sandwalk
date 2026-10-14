"""OpenAI Responses API via a ChatGPT plan OAuth token (Sign in with ChatGPT)."""

from __future__ import annotations

from typing import Any

from agent.config import chatgpt_auth

# OpenAI requires store:false for plan-backed Responses requests so nothing is
# retained server-side under the user's consumer account.
_PLAN_EXTRA_BODY: dict[str, Any] = {"store": False}


def build_chatgpt_chat_model(config: Any, *, temperature: float) -> Any:
    """Same wire shape as cloud OpenAI, but the bearer is the user's OAuth token.

    Differences from ``build_openai_chat_model``:
    - ``api_key`` is the short-lived access token from ``chatgpt_auth``;
      the store refreshes it under a lock when it is about to expire.
    - Always ``use_responses_api=True`` and ``store=False`` (plan requirement).
    - No ``base_url`` override: plan usage is only valid against api.openai.com.
    """
    from langchain.chat_models import init_chat_model

    from agent.deepagents_runtime.chat_model_openai import STREAM_CHUNK_TIMEOUT_S
    from agent.model_catalog import (
        effective_reasoning_effort,
        get_model_reasoning,
        model_supports_reasoning_effort,
    )
    from agent.model_catalog.param_heal import apply_effort_floor, get_param_heal

    model = str(config.get("llm.model") or "gpt-5.6-sol")
    token = chatgpt_auth.access_token()
    heal = get_param_heal(config.get("llm.param_heals"), chatgpt_auth.PROVIDER_KEY, model)

    kwargs: dict[str, Any] = {
        "api_key": token,
        "use_responses_api": True,
        "stream_usage": True,
        "stream_chunk_timeout": STREAM_CHUNK_TIMEOUT_S,
        "max_retries": 5,
        "extra_body": dict(_PLAN_EXTRA_BODY),
    }
    model_l = model.lower()
    if not (heal["omit_temperature"] or model_l.startswith(("gpt-5", "gpt-6"))):
        kwargs["temperature"] = temperature
    if not heal["omit_reasoning"] and model_supports_reasoning_effort("openai", model):
        effort, fast = get_model_reasoning(
            config.get("llm.model_reasoning"),
            chatgpt_auth.PROVIDER_KEY,
            model,
            default_effort=str(config.get("llm.reasoning_effort") or "medium"),
            default_fast=bool(config.get("llm.reasoning_fast", False)),
        )
        kwargs["reasoning_effort"] = apply_effort_floor(
            effective_reasoning_effort(effort=effort, fast=fast, model_id=model),
            heal,
        )
    return init_chat_model(f"openai:{model}", **kwargs)
