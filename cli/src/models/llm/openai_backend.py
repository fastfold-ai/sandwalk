"""OpenAI-compatible chat/stream implementations for LLMClient."""

from __future__ import annotations

from collections.abc import Generator

from models.llm.helpers import _openai_temperature_kwargs, _openai_token_limit_kwargs
from models.llm.response import LLMResponse


def call(client, model, system, messages, temperature, max_tokens) -> LLMResponse:
    all_messages = [{"role": "system", "content": system}] + messages
    response = client.chat.completions.create(
        model=model,
        messages=all_messages,
        **_openai_temperature_kwargs(model or "", temperature),
        **_openai_token_limit_kwargs(model or "", max_tokens),
    )
    return LLMResponse(
        content=response.choices[0].message.content,
        model=model,
        usage={"input": response.usage.prompt_tokens, "output": response.usage.completion_tokens},
        raw=response,
    )


def stream(client, model, system, messages, temperature, max_tokens, usage_tracker) -> Generator[str, None, None]:
    """Stream from OpenAI API, yielding text deltas."""
    all_messages = [{"role": "system", "content": system}] + messages
    chat_stream = client.chat.completions.create(
        model=model,
        messages=all_messages,
        **_openai_temperature_kwargs(model or "", temperature),
        **_openai_token_limit_kwargs(model or "", max_tokens),
        stream=True,
        stream_options={"include_usage": True},
    )
    usage = None
    for chunk in chat_stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
        if chunk.usage:
            usage = {"input": chunk.usage.prompt_tokens, "output": chunk.usage.completion_tokens}

    if usage:
        usage_tracker.record(model, usage)
