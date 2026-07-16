"""Text/usage extraction helpers for LangChain message and tool-output payloads."""

from __future__ import annotations

from typing import Any


def _text_from_content(content: Any) -> str:
    """Extract plain text from a LangChain message content (str or blocks)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(str(block.get("text", "")))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return ""


def _tool_output_text(output: Any) -> str:
    """Normalize a tool-end output (ToolMessage / str / list) to text."""
    content = getattr(output, "content", output)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts)
    if content is None:
        return ""
    return str(content)


def _usage_from_message(message: Any) -> dict[str, int] | None:
    """Read LangChain ``usage_metadata`` into the ct token-usage shape."""
    usage = getattr(message, "usage_metadata", None)
    if not isinstance(usage, dict):
        return None
    details = usage.get("input_token_details") or {}
    return {
        "input_tokens": int(usage.get("input_tokens", 0) or 0),
        "output_tokens": int(usage.get("output_tokens", 0) or 0),
        "cache_creation_input_tokens": int(details.get("cache_creation", 0) or 0),
        "cache_read_input_tokens": int(details.get("cache_read", 0) or 0),
    }
