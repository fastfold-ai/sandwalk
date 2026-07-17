"""Known context windows for cloud catalog models.

Cloud providers don't expose context limits via API, so we maintain this
mapping from official provider documentation (the same approach Cursor and
other clients use). Local OpenAI-compatible servers (oMLX, vLLM, …) advertise
``max_model_len`` on ``/v1/models`` and take precedence over this table.

Update these values when providers revise their published limits:
- Anthropic: https://platform.claude.com/docs/en/build-with-claude/context-windows
- OpenAI:    https://developers.openai.com/api/docs/models
- Google:    https://ai.google.dev/gemini-api/docs/models
- xAI:       https://docs.x.ai/docs/models

As of July 2026:
- Anthropic 1M context is GA (default, no beta header) on Opus 4.8/4.7/4.6,
  Sonnet 5, Sonnet 4.6, and Fable 5. The ``context-1m-2025-08-07`` beta was
  retired 2026-04-30; Sonnet 4.5 and older remain 200k.
- OpenAI GPT-5.6 (Sol/Terra/Luna) has a 1.05M window; earlier GPT-5.x are 400k.
"""

from __future__ import annotations

# Exact model-id matches take precedence over prefix rules.
_EXACT_CONTEXT_WINDOWS: dict[str, int] = {
    # xAI (per docs.x.ai)
    "grok-4.5": 256_000,
    "grok-4.3": 1_000_000,
    "grok-4.20": 256_000,
    # NVIDIA NIM
    "nvidia/nemotron-3-ultra-550b-a55b": 262_144,
}

# Longest-prefix rules for model families (checked after exact matches).
_PREFIX_CONTEXT_WINDOWS: list[tuple[str, int]] = [
    # Anthropic — 1M GA (default, no beta header) on modern models.
    ("claude-opus-4-8", 1_000_000),
    ("claude-opus-4-7", 1_000_000),
    ("claude-opus-4-6", 1_000_000),
    ("claude-sonnet-5", 1_000_000),
    ("claude-sonnet-4-6", 1_000_000),
    ("claude-fable-5", 1_000_000),
    ("claude-mythos", 1_000_000),
    # Older Anthropic models (Sonnet 4.5, Haiku 4.5, …) keep the 200k window.
    ("claude-", 200_000),
    # OpenAI — GPT-5.6 family is 1.05M; earlier GPT-5.x are 400k total.
    ("gpt-5.6", 1_050_000),
    ("gpt-5", 400_000),
    # Google Gemini — 1M input window.
    ("gemini-3", 1_048_576),
    ("gemini-", 1_048_576),
]


def context_window_for_model(model_id: str) -> int | None:
    """Best-known context window for a catalog model id, or None if unknown."""
    normalized = str(model_id or "").strip()
    if not normalized:
        return None
    exact = _EXACT_CONTEXT_WINDOWS.get(normalized)
    if exact is not None:
        return exact
    lowered = normalized.lower()
    best: int | None = None
    best_len = -1
    for prefix, window in _PREFIX_CONTEXT_WINDOWS:
        if lowered.startswith(prefix) and len(prefix) > best_len:
            best = window
            best_len = len(prefix)
    return best
