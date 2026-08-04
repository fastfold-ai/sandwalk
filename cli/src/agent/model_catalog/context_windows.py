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
- Moonshot:  https://platform.kimi.ai/docs/models
- Qwen:      https://docs.qwencloud.com/developer-guides/getting-started/text-generation-models

As of July 2026:
- Anthropic 1M context is GA (default, no beta header) on Opus 5, Fable 5,
  Sonnet 5, Opus 4.8/4.7/4.6, and Sonnet 4.6. The ``context-1m-2025-08-07``
  beta was retired 2026-04-30; Sonnet 4.5 and older remain 200k.
- OpenAI GPT-5.6 (Sol/Terra/Luna) has a 1.05M window; earlier GPT-5.x are 400k.
- Qwen3.8 / Qwen3.7 / most Qwen3.5–3.6 Plus/Flash flagships are 1M; legacy
  ``qwen3-max`` is 256k (see QwenCloud text-generation models table).
"""

from __future__ import annotations

# Exact model-id matches take precedence over prefix rules.
_EXACT_CONTEXT_WINDOWS: dict[str, int] = {
    # xAI (per docs.x.ai)
    "grok-4.5": 256_000,
    "grok-4.3": 1_000_000,
    "grok-4.20": 256_000,
    # Moonshot / Kimi (per platform.kimi.ai)
    "kimi-k3": 1_000_000,
    "kimi-k2.6": 256_000,
    "kimi-k2.5": 256_000,
    "kimi-k2.7-code": 256_000,
    "kimi-k2.7-code-highspeed": 256_000,
    # NVIDIA NIM
    "nvidia/nemotron-3-ultra-550b-a55b": 262_144,
    # Qwen Cloud specialized / long-context (per docs.qwencloud.com)
    "qwen-long": 10_000_000,
}

# Longest-prefix rules for model families (checked after exact matches).
_PREFIX_CONTEXT_WINDOWS: list[tuple[str, int]] = [
    # Anthropic — 1M GA (default, no beta header) on modern models.
    ("claude-opus-5", 1_000_000),
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
    # Moonshot / Kimi — k3 is 1M; other kimi-* are 256k.
    ("kimi-k3", 1_000_000),
    ("kimi-", 256_000),
    # Qwen Cloud — https://docs.qwencloud.com/.../text-generation-models
    # Longest-prefix wins: pin 1M Plus/Flash before denser 256k siblings.
    ("qwen3.8", 1_000_000),
    ("qwen3.7", 1_000_000),
    ("qwen3.6-flash", 1_000_000),
    ("qwen3.6-plus", 1_000_000),
    ("qwen3.6", 256_000),
    ("qwen3.5-plus", 1_000_000),
    ("qwen3.5-flash", 1_000_000),
    ("qwen3.5", 256_000),
    ("qwen3-coder-plus", 1_000_000),
    ("qwen3-coder-flash", 1_000_000),
    ("qwen3-coder", 256_000),
    ("qwen3-max", 256_000),
    ("qwen3-", 128_000),
    ("qwen-plus", 1_000_000),
    ("qwen-flash", 1_000_000),
    ("qwen-turbo", 128_000),
    ("qwen-max", 32_000),
    ("qwen-mt", 16_000),
    # Third-party models resold on Qwen Cloud (same docs / marketplace cards).
    ("deepseek-v4", 1_000_000),
    ("glm-5.2", 1_000_000),
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
