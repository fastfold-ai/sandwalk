"""Work around langchain-anthropic dropping empty adaptive-thinking text.

Anthropic Opus 5 / Sonnet 5 adaptive thinking can stream a thinking block with
empty text (signature_delta only). langchain-anthropic then aggregates a block
missing the required ``thinking`` key; the next agent turn (after tools) fails:

  400 messages.N.content.M.thinking.thinking: Field required

See https://github.com/langchain-ai/langchain/issues/38639
"""

from __future__ import annotations

_APPLIED = False


def _ensure_thinking_key(block: object) -> object:
    if not isinstance(block, dict) or block.get("type") != "thinking":
        return block
    if "thinking" in block:
        return block
    return {**block, "thinking": ""}


def apply_anthropic_empty_thinking_patch() -> None:
    """Idempotent patch of langchain-anthropic streaming + message formatting."""
    global _APPLIED
    if _APPLIED:
        return

    import langchain_anthropic.chat_models as mod
    from langchain_anthropic.chat_models import ChatAnthropic

    original_chunk = ChatAnthropic._make_message_chunk_from_anthropic_event

    def patched_chunk(
        self,
        event,
        *,
        stream_usage: bool = True,
        coerce_content_to_string: bool,
        block_start_event=None,
    ):
        chunk, next_start = original_chunk(
            self,
            event,
            stream_usage=stream_usage,
            coerce_content_to_string=coerce_content_to_string,
            block_start_event=block_start_event,
        )
        delta_type = getattr(getattr(event, "delta", None), "type", None)
        if (
            chunk is not None
            and getattr(event, "type", None) == "content_block_delta"
            and delta_type == "signature_delta"
            and isinstance(chunk.content, list)
        ):
            chunk.content = [_ensure_thinking_key(block) for block in chunk.content]
        return chunk, next_start

    ChatAnthropic._make_message_chunk_from_anthropic_event = patched_chunk

    original_format = mod._format_messages

    def patched_format(messages):
        system, formatted = original_format(messages)
        for message in formatted:
            content = message.get("content")
            if not isinstance(content, list):
                continue
            message["content"] = [_ensure_thinking_key(block) for block in content]
        return system, formatted

    mod._format_messages = patched_format
    _APPLIED = True
