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
- OpenRouter: https://openrouter.ai/models (same underlying windows; ids are
  ``vendor/slug``, e.g. ``qwen/qwen3.7-max``, ``deepseek/deepseek-v4-pro``)

As of July 2026:
- Anthropic 1M context is GA (default, no beta header) on Opus 5, Fable 5,
  Sonnet 5, Opus 4.8/4.7/4.6, and Sonnet 4.6. The ``context-1m-2025-08-07``
  beta was retired 2026-04-30; Sonnet 4.5 and older remain 200k.
- OpenAI GPT-5.6 (Sol/Terra/Luna) has a 1.05M window; earlier GPT-5.x are 400k.
- Qwen3.8 / Qwen3.7 / most Qwen3.5–3.6 Plus/Flash flagships are 1M; legacy
  ``qwen3-max`` is 256k (see QwenCloud text-generation models table).
- DeepSeek V4 Flash/Pro (native, Qwen Cloud, and OpenRouter) are 1M.
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
    "moonshotai/kimi-k3": 1_000_000,
    "kimi-k2.6": 256_000,
    "moonshotai/kimi-k2.6": 256_000,
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
    # Haiku 5.5 is the first 1M Haiku (Models API: max_input_tokens 1,000,000).
    ("claude-haiku-5", 1_000_000),
    ("claude-fable-5-1", 1_000_000),
    ("claude-fable-5", 1_000_000),
    ("claude-mythos", 1_000_000),
    # Older Anthropic models (Sonnet 4.5, Haiku 4.5, …) keep the 200k window.
    ("claude-", 200_000),
    # OpenAI — GPT-5.6 family is 1.05M; earlier GPT-5.x are 400k total.
    ("gpt-6", 1_050_000),
    ("gpt-5.6", 1_050_000),
    ("gpt-5", 400_000),
    # Google Gemini — 1M input window (1,048,576 on Gemini 4 Argon / 3.x).
    ("gemini-4", 1_048_576),
    ("gemini-3", 1_048_576),
    ("gemini-", 1_048_576),
    # Meta Muse (Model API) — 1,048,576 tokens on Muse Wonder & Muse Spark.
    ("muse-wonder", 1_048_576),
    ("muse-spark", 1_048_576),
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
    """Best-known context window for a catalog model id, or None if unknown.

    OpenRouter and similar catalogs use ``vendor/slug`` ids
    (``qwen/qwen3.7-max``). After an exact full-id miss we also match the
    bare slug so the same Qwen/DeepSeek prefix table covers both native and
    OpenRouter listings.
    """
    normalized = str(model_id or "").strip()
    if not normalized:
        return None
    lowered = normalized.lower()
    for key in (normalized, lowered):
        exact = _EXACT_CONTEXT_WINDOWS.get(key)
        if exact is not None:
            return exact
    # ``qwen/qwen3.7-max`` → also try ``qwen3.7-max``.
    # Bedrock ``us.anthropic.claude-sonnet-4-6`` → ``claude-sonnet-4-6``.
    from agent.model_catalog.bedrock import bedrock_bare_model_id

    bedrock_bare = bedrock_bare_model_id(lowered)
    bare = lowered.rsplit("/", 1)[-1]
    if bedrock_bare and bedrock_bare != lowered and bedrock_bare != bare:
        exact = _EXACT_CONTEXT_WINDOWS.get(bedrock_bare)
        if exact is not None:
            return exact
    if bare != lowered:
        exact = _EXACT_CONTEXT_WINDOWS.get(bare)
        if exact is not None:
            return exact
    extra = tuple(
        item
        for item in (bare, bedrock_bare)
        if item and item != lowered
    )
    candidates = (lowered, *extra)
    best: int | None = None
    best_len = -1
    for candidate in candidates:
        for prefix, window in _PREFIX_CONTEXT_WINDOWS:
            if candidate.startswith(prefix) and len(prefix) > best_len:
                best = window
                best_len = len(prefix)
    return best
