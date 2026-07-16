"""Anthropic-specific chat/stream implementations for LLMClient."""

from __future__ import annotations

from collections.abc import Generator

from models.llm.helpers import _anthropic_temperature_kwargs, logger
from models.llm.response import LLMResponse


def call(client, model, system, messages, temperature, max_tokens, tools=None) -> LLMResponse:
    kwargs = {
        "model": model,
        "system": system,
        "messages": messages,
        "max_tokens": max_tokens,
        **_anthropic_temperature_kwargs(model or "", temperature),
    }
    if tools:
        kwargs["tools"] = tools
    response = client.messages.create(**kwargs)
    # Guard against empty content array (e.g., content filtering)
    if not response.content:
        content_text = ""
    else:
        # Extract text parts only (skip tool_use blocks)
        text_parts = [b.text for b in response.content if hasattr(b, "text")]
        content_text = "\n".join(text_parts) if text_parts else ""
    return LLMResponse(
        content=content_text,
        model=model,
        usage={"input": response.usage.input_tokens, "output": response.usage.output_tokens},
        raw=response,
        content_blocks=list(response.content) if response.content else [],
    )


def stream(client, model, system, messages, temperature, max_tokens, usage_tracker) -> Generator[str, None, None]:
    """Stream from Anthropic API, yielding text deltas."""
    with client.messages.stream(
        model=model,
        system=system,
        messages=messages,
        max_tokens=max_tokens,
        **_anthropic_temperature_kwargs(model or "", temperature),
    ) as text_stream:
        try:
            yield from text_stream.text_stream
        finally:
            # Record usage even if stream is interrupted (Ctrl+C)
            try:
                response = text_stream.get_final_message()
                usage = {"input": response.usage.input_tokens, "output": response.usage.output_tokens}
                usage_tracker.record(model, usage)
            except Exception:
                logger.debug("Could not record usage after stream interrupt")
