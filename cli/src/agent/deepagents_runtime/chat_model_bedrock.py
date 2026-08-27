"""Amazon Bedrock chat model construction (LangChain Converse API)."""

from __future__ import annotations

from typing import Any

from agent.config.bedrock_auth import DEFAULT_BEDROCK_MODEL, bedrock_chat_kwargs
from agent.model_catalog import resolve_catalog_model_id


def build_bedrock_chat_model(config, *, temperature: float):
    """Build ``ChatBedrockConverse`` using IAM / profile by default."""
    from langchain_aws import ChatBedrockConverse

    model = resolve_catalog_model_id(
        config.get("llm.model") or DEFAULT_BEDROCK_MODEL
    )
    kwargs: dict[str, Any] = {
        "model": model,
        "temperature": temperature,
        **bedrock_chat_kwargs(config),
    }
    return ChatBedrockConverse(**kwargs)
