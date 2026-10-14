"""Provider-compatibility kwargs helpers and retry logic for the LLM client."""

from __future__ import annotations

import logging
import time

logger = logging.getLogger("llm")


def _openai_token_limit_kwargs(model: str, max_tokens: int) -> dict[str, int]:
    """Return OpenAI token limit arg compatible with model family."""
    model_name = str(model or "").strip().lower()
    if model_name.startswith(("gpt-5", "gpt-6", "o1", "o3", "o4")):
        return {"max_completion_tokens": int(max_tokens)}
    return {"max_tokens": int(max_tokens)}


def _openai_temperature_kwargs(model: str, temperature: float) -> dict[str, float]:
    """Return OpenAI temperature kwargs compatible with model family."""
    model_name = str(model or "").strip().lower()
    if model_name.startswith(("gpt-5", "gpt-6", "o1", "o3", "o4")):
        return {}
    # Moonshot / Kimi reasoning models reject any temperature other than 1.
    if model_name.startswith("kimi-"):
        return {"temperature": 1.0}
    return {"temperature": float(temperature)}


def _anthropic_temperature_kwargs(model: str, temperature: float) -> dict[str, float]:
    """Omit temperature for Anthropic models that reject sampling params."""
    try:
        from agent.model_catalog import anthropic_model_omits_temperature
    except Exception:
        return {"temperature": float(temperature)}
    if anthropic_model_omits_temperature(model):
        return {}
    return {"temperature": float(temperature)}


def retry_with_backoff(fn, max_retries: int = 3, base_delay: float = 2.0):
    """Retry a function with exponential backoff on transient errors."""
    for attempt in range(1, max_retries + 1):
        try:
            return fn()
        except Exception as e:
            err_str = str(e).lower()
            is_transient = any(w in err_str for w in (
                "rate_limit", "rate limit", "429", "overloaded",
                "529", "500", "502", "503", "connection", "timeout",
            ))
            if is_transient and attempt < max_retries:
                delay = base_delay * (2 ** (attempt - 1))
                logger.warning("LLM call failed (attempt %d/%d): %s — retrying in %.1fs",
                               attempt, max_retries, e, delay)
                time.sleep(delay)
            else:
                raise
