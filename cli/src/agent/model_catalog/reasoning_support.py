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
    # OpenAI cloud GPT-5 / o-series reasoning models (also via ChatGPT plan OAuth).
    if provider_norm in {"openai", "openai-chatgpt", "opencode", ""}:
        if value.startswith("o1") or value.startswith("o3") or value.startswith("o4"):
            return True
        if value.startswith("gpt-5") or value.startswith("gpt-6"):
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
    # Meta Model API — Muse Wonder & Muse Spark accept reasoning_effort (low/medium/high; no none).
    if provider_norm == "meta":
        return value.startswith(("muse-wonder", "muse-spark"))
    # Moonshot Kimi — only models with a real thinking toggle.
    if provider_norm == "moonshot":
        return moonshot_model_supports_thinking_toggle(value)
    # OpenRouter — unified ``reasoning.effort`` for models that advertise it.
    if provider_norm == "openrouter":
        return openrouter_model_supports_reasoning(value)
    if provider_norm == "bedrock":
        from agent.model_catalog.bedrock import bedrock_bare_model_id

        bare = bedrock_bare_model_id(value)
        if "claude" in bare or bare.startswith("claude"):
            return anthropic_model_supports_effort(bare)
        if "nova" in bare:
            return True
        return False
    # Local / compatible profiles: Unsloth via ``compatible_backend``.
    if provider_norm in {"local", "compatible", "openai-compatible"}:
        return compatible_profile_supports_thinking(compatible_backend)
    return False


def _openrouter_slug(model_id: str | None) -> tuple[str, str]:
    """Return ``(vendor, slug)`` for an OpenRouter-style ``vendor/model`` id."""
    value = str(model_id or "").strip().lower()
    if "/" in value:
        vendor, slug = value.split("/", 1)
        return vendor, slug
    return "", value


def openrouter_model_supports_reasoning(model_id: str | None) -> bool:
    """Return True when OpenRouter accepts a ``reasoning`` / effort control.

    Based on OpenRouter ``supported_parameters`` / ``reasoning`` metadata for
    Sandwalk's curated catalog (and close relatives). Models without a
    reasoning control (GPT-4o Mini, Kimi K2, Qwen3 Max, Mistral Large) stay
    out so Effort/Fast is not shown.
    """
    vendor, slug = _openrouter_slug(model_id)
    if not slug:
        return False

    # OpenAI GPT-5 / GPT-6 / o-series (not chat-only variants).
    if vendor == "openai" or slug.startswith(("gpt-", "o1", "o3", "o4")):
        if slug.startswith(("o1", "o3", "o4")):
            return True
        if slug.startswith(("gpt-5", "gpt-6")) or "astra" in slug:
            if "chat" in slug and "latest" in slug:
                return False
            return True
        return False

    # Anthropic — Sonnet/Haiku 4.5+, Opus 4.5+/5+, plus native effort models.
    if vendor == "anthropic" or slug.startswith("claude-"):
        import re

        if re.search(r"haiku-4[.-]5", slug):
            return True
        if re.search(r"sonnet-4[.-][56]", slug):
            return True
        if re.search(r"opus-4[.-][5678]", slug):
            return True
        return anthropic_model_supports_effort(slug)

    # Google — Gemini 2.5+ / 3+ / 4+ expose OpenRouter reasoning (native Google
    # only wires Gemini 3+ / 4+ thinking_level).
    if vendor == "google" or slug.startswith("gemini-"):
        return slug.startswith(("gemini-2.5", "gemini-3", "gemini-4"))

    # xAI Grok 4.x
    if vendor in {"x-ai", "xai"} or slug.startswith("grok-"):
        return xai_model_supports_reasoning_effort(slug)

    # DeepSeek V3.1+ / V4 / R1 / reasoner variants.
    if "deepseek" in vendor or "deepseek" in slug:
        return any(
            token in slug
            for token in ("v3.1", "v3-1", "v3.2", "v4", "r1", "reasoner", "thinking")
        )

    # Qwen3.7+ hybrid thinking models (Qwen Cloud / OpenRouter).
    if vendor == "qwen" or slug.startswith("qwen"):
        return any(
            token in slug
            for token in (
                "qwen3.8",
                "qwen3.7",
                "qwen3-7",
                "qwen3.6",
                "qwen3.5",
                "thinking",
                "qwq",
            )
        )

    # Thinking Machines Inkling.
    if "thinkingmachines" in vendor or "inkling" in slug:
        return "inkling" in slug

    # Meta Muse Spark.
    if vendor == "meta" or "muse" in slug:
        return "muse" in slug

    # Newer Kimi on OpenRouter (k2.5+ / k3 advertise reasoning).
    if "moonshot" in vendor or slug.startswith("kimi-"):
        return any(
            token in slug
            for token in ("kimi-k2.5", "kimi-k2.6", "kimi-k2.7", "kimi-k3")
        )

    # NVIDIA Nemotron (incl. :free) on OpenRouter.
    if vendor == "nvidia" or "nemotron" in slug:
        return "nemotron" in slug

    # Z.ai GLM on OpenRouter.
    if vendor in {"z-ai", "zai"} or slug.startswith("glm-"):
        return slug.startswith("glm-")

    # Xiaomi MiMo on OpenRouter.
    if vendor == "xiaomi" or slug.startswith("mimo-"):
        return "mimo-" in slug

    return False


def openrouter_model_reasoning_mandatory(model_id: str | None) -> bool:
    """Return True when OpenRouter rejects ``reasoning.effort: none``.

    Matches curated models whose OpenRouter ``reasoning.mandatory`` is true
    (e.g. Gemini 2.5 Pro, Grok 4.5, Meta Muse Spark).
    """
    _, slug = _openrouter_slug(model_id)
    if not slug:
        return False
    if "gemini-2.5-pro" in slug or "gemini-2-5-pro" in slug:
        return True
    if "grok-4.5" in slug or "grok-4-5" in slug:
        return True
    # Muse Wonder / Muse Spark require thinking; Fast (effort none) returns HTTP 400.
    if (
        "muse-spark" in slug
        or "muse-wonder" in slug
        or ("muse" in slug and ("spark" in slug or "wonder" in slug))
    ):
        return True
    return False


def model_supports_reasoning_fast(
    provider: str | None,
    model_id: str | None,
    *,
    compatible_backend: str | None = None,
) -> bool:
    """Return False when Fast (thinking off) is not allowed for this model.

    Models with mandatory reasoning still expose Effort (Low/Medium/High) but
    must not offer Fast, which maps to ``effort: none``.
    """
    if not model_supports_reasoning_effort(
        provider, model_id, compatible_backend=compatible_backend
    ):
        return False
    prov = str(provider or "").strip().lower()
    if prov in {"openrouter", "meta"} and openrouter_model_reasoning_mandatory(model_id):
        return False
    return True


def openrouter_model_omits_temperature(model_id: str | None) -> bool:
    """Return True when OpenRouter rejects ``temperature`` for this model.

    GPT-5 / GPT-6 / Astra list no ``temperature`` in ``supported_parameters``.
    Combined with ``provider.require_parameters``, sending it 404s the request.
    Anthropic Opus/Sonnet 5 on OpenRouter match the native no-sampling rule.
    """
    vendor, slug = _openrouter_slug(model_id)
    if slug.startswith(("gpt-5", "gpt-6", "o1", "o3", "o4")) or "astra" in slug:
        return True
    if vendor == "anthropic" or slug.startswith("claude-"):
        return anthropic_model_omits_temperature(slug)
    return False


def xai_model_supports_reasoning_effort(model_id: str | None) -> bool:
    """Grok 4.x catalog models that accept ``reasoning_effort``."""
    value = str(model_id or "").strip().lower()
    if not value.startswith("grok-4"):
        return False
    # Catalog ids: grok-4.5, grok-4.3, grok-4.20 (+ multi-agent variants).
    return True


def google_model_supports_thinking_level(model_id: str | None) -> bool:
    """Gemini 3+ / 4+ models that accept LangChain ``thinking_level``."""
    value = str(model_id or "").strip().lower()
    if not value.startswith("gemini-"):
        return False
    # Gemini 3 / 3.1 / 3.5 and Gemini 4 (e.g. gemini-4-argon) families.
    if value.startswith(("gemini-3", "gemini-4")):
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
