"""Per-model reasoning-effort capability checks and value normalization."""

from __future__ import annotations

REASONING_EFFORT_LEVELS = ("low", "medium", "high")
REASONING_EFFORT_VALUES = ("none", "low", "medium", "high")


def compatible_profile_supports_thinking(backend: str | None) -> bool:
    """Return True when a local OpenAI-compatible backend accepts a thinking toggle."""
    return str(backend or "").strip().lower() == "unsloth"


def moonshot_model_supports_thinking_toggle(model_id: str | None) -> bool:
    """Kimi models that accept ChatMoonshot ``thinking`` on/off (not always-on)."""
    value = str(model_id or "").strip().lower()
    if not value:
        return False
    # k2.5 / k2.6 support thinking enabled/disabled. k2.7-code* and k3 do not.
    if value.startswith("kimi-k2.7"):
        return False
    if value.startswith("kimi-k2.5") or value.startswith("kimi-k2.6"):
        return True
    return False


def model_supports_reasoning_effort(
    provider: str | None,
    model_id: str | None,
    *,
    compatible_backend: str | None = None,
) -> bool:
    """Return True when the UI should expose Effort / Fast for this model."""
    provider_norm = str(provider or "").strip().lower()
    value = str(model_id or "").strip().lower()
    if compatible_profile_supports_thinking(compatible_backend):
        return True
    if not value:
        return False
    # OpenAI cloud GPT-5 / o-series reasoning models.
    if provider_norm in {"openai", "opencode", ""}:
        if value.startswith("o1") or value.startswith("o3") or value.startswith("o4"):
            return True
        if value.startswith("gpt-5"):
            # Chat-only / non-reasoning GPT-5 variants stay out.
            if "chat" in value and "latest" in value:
                return False
            return True
        # OpenCode may host Claude behind anthropic Messages — treat as Anthropic.
        if provider_norm == "opencode" and value.startswith("claude-"):
            return anthropic_model_supports_effort(value)
    if provider_norm == "anthropic":
        return anthropic_model_supports_effort(value)
    # Gemini 3+ via native GenAI ``thinking_level``.
    if provider_norm == "google":
        return google_model_supports_thinking_level(value)
    # xAI Grok 4.3 / 4.5 / 4.20 support reasoning_effort (see xAI Reasoning docs).
    if provider_norm == "xai":
        return xai_model_supports_reasoning_effort(value)
    # Moonshot Kimi — only models with a real thinking toggle.
    if provider_norm == "moonshot":
        return moonshot_model_supports_thinking_toggle(value)
    # Local / compatible profiles: Unsloth via ``compatible_backend``.
    if provider_norm in {"local", "compatible", "openai-compatible"}:
        return compatible_profile_supports_thinking(compatible_backend)
    return False


def xai_model_supports_reasoning_effort(model_id: str | None) -> bool:
    """Grok 4.x catalog models that accept ``reasoning_effort``."""
    value = str(model_id or "").strip().lower()
    if not value.startswith("grok-4"):
        return False
    # Catalog ids: grok-4.5, grok-4.3, grok-4.20 (+ multi-agent variants).
    return True


def google_model_supports_thinking_level(model_id: str | None) -> bool:
    """Gemini 3+ models that accept LangChain ``thinking_level``."""
    value = str(model_id or "").strip().lower()
    if not value.startswith("gemini-"):
        return False
    # Gemini 3 / 3.1 / 3.5 families.
    if value.startswith("gemini-3"):
        return True
    return False


def anthropic_model_supports_effort(model_id: str | None) -> bool:
    """Claude models that accept ``effort`` / ``output_config.effort``."""
    import re

    value = str(model_id or "").strip().lower()
    if not value:
        return False
    if value.startswith("claude-opus-5"):
        return True
    if value.startswith("claude-sonnet-5"):
        return True
    if value.startswith("claude-fable-5") or value.startswith("claude-mythos-5"):
        return True
    if value.startswith("claude-sonnet-4-6"):
        return True
    # opus-4-5 / 4-6 / 4-7 / 4-8 (not older opus-4-2025… without these suffixes)
    if re.search(r"(?:^|[^0-9])opus-4-[5678](?:$|[^0-9])", value):
        return True
    return False


def anthropic_model_omits_temperature(model_id: str | None) -> bool:
    """Return True when Anthropic rejects non-default sampling params.

    Opus 5, Opus 4.7+, Sonnet 5, Fable 5, and Mythos 5 return HTTP 400 if
    ``temperature`` / ``top_p`` / ``top_k`` are set to non-default values.
    """
    import re

    value = str(model_id or "").strip().lower()
    if not value:
        return False
    if value.startswith("claude-opus-5"):
        return True
    if value.startswith("claude-sonnet-5"):
        return True
    if value.startswith("claude-fable-5") or value.startswith("claude-mythos-5"):
        return True
    # opus-4-7 / opus-4-8 (optional suffix), not opus-4-6 / opus-4-5 / opus-4-80.
    if re.search(r"(?:^|[^0-9])opus-4-[78](?:$|[^0-9])", value):
        return True
    return False


def reasoning_effort_options(
    provider: str | None,
    model_id: str | None,
    *,
    compatible_backend: str | None = None,
) -> list[str]:
    """Effort choices shown in the Cursor-style selector (Low/Medium/High)."""
    if not model_supports_reasoning_effort(
        provider, model_id, compatible_backend=compatible_backend
    ):
        return []
    return list(REASONING_EFFORT_LEVELS)


def normalize_reasoning_effort(value: str | None, *, allow_none: bool = True) -> str:
    """Clamp effort to a supported value; default medium."""
    raw = str(value or "").strip().lower()
    allowed = REASONING_EFFORT_VALUES if allow_none else REASONING_EFFORT_LEVELS
    if raw in allowed:
        return raw
    return "medium"
