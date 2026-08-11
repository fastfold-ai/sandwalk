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


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number < 0:
        return None
    return number


def _usage_dict_from_mapping(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict) or not raw:
        return None
    input_tokens = _as_int(
        raw.get("input_tokens")
        if raw.get("input_tokens") is not None
        else raw.get("prompt_tokens")
        if raw.get("prompt_tokens") is not None
        else raw.get("input")
    )
    output_tokens = _as_int(
        raw.get("output_tokens")
        if raw.get("output_tokens") is not None
        else raw.get("completion_tokens")
        if raw.get("completion_tokens") is not None
        else raw.get("output")
    )
    details = raw.get("input_token_details") or raw.get("prompt_tokens_details") or {}
    if not isinstance(details, dict):
        details = {}
    cache_read = _as_int(
        details.get("cache_read")
        if details.get("cache_read") is not None
        else details.get("cached_tokens")
        if details.get("cached_tokens") is not None
        else raw.get("cache_read_input_tokens")
        if raw.get("cache_read_input_tokens") is not None
        else raw.get("cached_tokens")
    )
    cache_creation = _as_int(
        details.get("cache_creation")
        if details.get("cache_creation") is not None
        else raw.get("cache_creation_input_tokens")
    )
    if input_tokens <= 0 and output_tokens <= 0 and cache_read <= 0:
        return None
    result: dict[str, Any] = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_creation_input_tokens": cache_creation,
        "cache_read_input_tokens": cache_read,
    }
    tokens_per_second = _as_float(
        raw.get("generation_tokens_per_second")
        if raw.get("generation_tokens_per_second") is not None
        else raw.get("predicted_per_second")
        if raw.get("predicted_per_second") is not None
        else raw.get("tokens_per_second")
    )
    prompt_tokens_per_second = _as_float(
        raw.get("prompt_tokens_per_second")
        if raw.get("prompt_tokens_per_second") is not None
        else raw.get("prompt_per_second")
    )
    prompt_eval_seconds = _as_float(raw.get("prompt_eval_duration"))
    if prompt_eval_seconds is None and raw.get("prompt_ms") is not None:
        prompt_ms = _as_float(raw.get("prompt_ms"))
        if prompt_ms is not None:
            prompt_eval_seconds = prompt_ms / 1000.0
    generation_seconds = _as_float(raw.get("generation_duration"))
    if generation_seconds is None and raw.get("predicted_ms") is not None:
        predicted_ms = _as_float(raw.get("predicted_ms"))
        if predicted_ms is not None:
            generation_seconds = predicted_ms / 1000.0
    time_to_first_token = _as_float(raw.get("time_to_first_token"))
    if tokens_per_second is not None:
        result["tokens_per_second"] = tokens_per_second
    if prompt_tokens_per_second is not None:
        result["prompt_tokens_per_second"] = prompt_tokens_per_second
    if prompt_eval_seconds is not None:
        result["prompt_eval_seconds"] = prompt_eval_seconds
    if generation_seconds is not None:
        result["generation_seconds"] = generation_seconds
    if time_to_first_token is not None:
        result["time_to_first_token"] = time_to_first_token
    return result


def _usage_from_message(message: Any) -> dict[str, Any] | None:
    """Read token usage (+ optional local timing) from a LangChain message."""
    candidates: list[Any] = [
        getattr(message, "usage_metadata", None),
        getattr(message, "usage", None),
    ]
    meta = getattr(message, "response_metadata", None)
    if isinstance(meta, dict):
        candidates.extend(
            [
                meta.get("usage"),
                meta.get("token_usage"),
                meta.get("tokenUsage"),
                meta,
            ]
        )
        # oMLX / llama.cpp sometimes nest timings beside usage.
        timings = meta.get("timings")
        if isinstance(timings, dict):
            candidates.append(timings)

    for candidate in candidates:
        if isinstance(candidate, dict):
            parsed = _usage_dict_from_mapping(candidate)
            if parsed:
                return parsed
        if candidate is not None and not isinstance(candidate, dict):
            parsed = _usage_dict_from_mapping(
                {
                    "input_tokens": getattr(candidate, "input_tokens", None)
                    or getattr(candidate, "prompt_tokens", None),
                    "output_tokens": getattr(candidate, "output_tokens", None)
                    or getattr(candidate, "completion_tokens", None),
                    "cache_read_input_tokens": getattr(
                        candidate, "cache_read_input_tokens", None
                    ),
                    "generation_tokens_per_second": getattr(
                        candidate, "generation_tokens_per_second", None
                    ),
                    "prompt_tokens_per_second": getattr(
                        candidate, "prompt_tokens_per_second", None
                    ),
                    "prompt_eval_duration": getattr(
                        candidate, "prompt_eval_duration", None
                    ),
                    "generation_duration": getattr(
                        candidate, "generation_duration", None
                    ),
                    "time_to_first_token": getattr(
                        candidate, "time_to_first_token", None
                    ),
                }
            )
            if parsed:
                return parsed

    # Last resort for local servers that omit usage entirely.
    text = _text_from_content(getattr(message, "content", ""))
    if not text.strip():
        return None
    return {
        "input_tokens": 0,
        "output_tokens": max(1, (len(text) + 3) // 4),
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "estimated": True,
    }
