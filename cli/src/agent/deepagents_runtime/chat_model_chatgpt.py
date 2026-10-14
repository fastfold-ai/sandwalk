"""OpenAI Responses API via a ChatGPT plan OAuth token (Sign in with ChatGPT)."""

from __future__ import annotations

from typing import Any

from agent.config import chatgpt_auth


def _message_text(content: Any) -> str:
    """Flatten a Responses message ``content`` value to plain text."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict):
            text = block.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(part for part in parts if part)


def lift_system_messages_to_instructions(payload: dict[str, Any]) -> dict[str, Any]:
    """Move ``role: system`` input items into the top-level ``instructions`` field.

    ChatGPT plan usage accepts a plain system string, then rejects the same
    text once LangChain serializes it as a Responses message item
    (``{"type": "message", "role": "system"}``) with
    ``400 {"detail": "System messages are not allowed"}``. The plan does
    accept that text as ``instructions``.
    """
    payload["store"] = False
    items = payload.get("input")
    if not isinstance(items, list):
        return payload
    kept: list[Any] = []
    lifted: list[str] = []
    for item in items:
        if isinstance(item, dict) and item.get("role") == "system":
            text = _message_text(item.get("content")).strip()
            if text:
                lifted.append(text)
            continue
        kept.append(item)
    if not lifted:
        return payload
    existing = str(payload.get("instructions") or "").strip()
    payload["instructions"] = "\n\n".join([existing, *lifted] if existing else lifted)
    payload["input"] = kept
    return payload


def build_chatgpt_chat_model(config: Any, *, temperature: float) -> Any:
    """Same wire shape as cloud OpenAI, but the bearer is the user's OAuth token.

    Differences from ``build_openai_chat_model``:
    - ``api_key`` is the short-lived access token from ``chatgpt_auth``;
      the store refreshes it under a lock when it is about to expire.
    - Always ``use_responses_api=True`` and ``store=False`` (plan requirement).
    - System prompts are sent as ``instructions``, which the plan accepts.
    - No ``base_url`` override: plan usage is only valid against api.openai.com.
    """
    from langchain_openai import ChatOpenAI

    from agent.deepagents_runtime.chat_model_openai import STREAM_CHUNK_TIMEOUT_S
    from agent.model_catalog import (
        effective_reasoning_effort,
        get_model_reasoning,
        model_supports_reasoning_effort,
    )
    from agent.model_catalog.param_heal import apply_effort_floor, get_param_heal

    class _ChatGPTPlanChatModel(ChatOpenAI):
        def _get_request_payload(self, input_: Any, *, stop: list[str] | None = None, **kwargs: Any) -> dict:
            payload = super()._get_request_payload(input_, stop=stop, **kwargs)
            return lift_system_messages_to_instructions(payload)

    model = str(config.get("llm.model") or "gpt-5.6-sol")
    token = chatgpt_auth.access_token()
    heal = get_param_heal(config.get("llm.param_heals"), chatgpt_auth.PROVIDER_KEY, model)

    kwargs: dict[str, Any] = {
        "model": model,
        "api_key": token,
        "use_responses_api": True,
        "store": False,
        "stream_usage": True,
        "stream_chunk_timeout": STREAM_CHUNK_TIMEOUT_S,
        "max_retries": 5,
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
    return _ChatGPTPlanChatModel(**kwargs)
