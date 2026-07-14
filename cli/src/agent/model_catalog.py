"""Shared cloud model catalog for CLI /model and agent-server /v1/models."""

from __future__ import annotations

from typing import TypedDict


class CatalogModel(TypedDict):
    id: str
    label: str
    description: str
    provider: str


# Static Anthropic + OpenAI cloud catalog (excludes OpenAI-compatible profile entry).
# New-generation models come first (enabled by default); legacy models remain in
# the catalog but are disabled by default (see DEFAULT_DISABLED_MODELS).
AVAILABLE_MODELS: dict[str, list[tuple[str, str, str]]] = {
    "anthropic": [
        ("claude-opus-4-8", "Opus 4.8", "Most capable Anthropic model for complex reasoning"),
        ("claude-sonnet-5", "Sonnet 5", "Flagship Sonnet for everyday coding and reasoning"),
        ("claude-sonnet-4-6", "Sonnet 4.6", "Fast, balanced Sonnet for most tasks"),
        ("claude-fable-5", "Fable 5", "Creative Anthropic model for writing and ideation"),
        # Legacy (disabled by default)
        ("claude-sonnet-4-5-20250929", "Sonnet 4.5", "Previous-generation Sonnet"),
        ("claude-haiku-4-5-20251001", "Haiku 4.5", "Fastest previous-generation Anthropic option"),
        ("claude-opus-4-6", "Opus 4.6", "Previous-generation Opus"),
    ],
    "openai": [
        ("gpt-5.6-sol", "GPT-5.6 Sol", "High-speed frontier model for coding"),
        ("gpt-5.6-terra", "GPT-5.6 Terra", "Balanced GPT-5.6 for general professional work"),
        ("gpt-5.5", "GPT-5.5", "Frontier model for coding and professional work"),
        ("gpt-5.3-codex", "Codex 5.3", "Specialized OpenAI coding model (Responses API)"),
        # Legacy (disabled by default)
        ("gpt-5.5-pro", "GPT-5.5 Pro", "Smarter, more precise GPT-5.5 variant"),
        ("gpt-5.4", "GPT-5.4", "Previous-generation model for coding and professional work"),
        ("gpt-5.4-pro", "GPT-5.4 Pro", "Smarter, more precise GPT-5.4 variant"),
        ("gpt-5.4-mini", "GPT-5.4 Mini", "Strong mini model for coding, computer use, and subagents"),
        ("gpt-5.4-nano", "GPT-5.4 Nano", "Cheapest GPT-5.4-class model for high-volume simple tasks"),
        ("gpt-5-mini", "GPT-5 Mini", "Near-frontier model for cost-sensitive low-latency workloads"),
        ("gpt-5-nano", "GPT-5 Nano", "Cheapest GPT-5-class model for simple high-volume tasks"),
    ],
    "xai": [
        ("grok-4.5", "Grok 4.5", "Most intelligent and fastest xAI model"),
        ("grok-4.3", "Grok 4.3", "Fast general-purpose xAI model with 1M context"),
        ("grok-4.20", "Grok 4.20", "Reasoning-capable xAI model"),
    ],
    "google": [
        (
            "gemini-3.1-pro-preview",
            "Gemini 3.1 Pro",
            "Most intelligent Gemini for multimodal reasoning",
        ),
        ("gemini-3.5-flash", "Gemini 3.5 Flash", "Frontier-class Gemini at a fraction of the cost"),
        ("gemini-3.1-flash-lite", "Gemini 3.1 Flash-Lite", "High-volume, cost-sensitive Gemini model"),
    ],
    "nvidia": [
        (
            "nvidia/nemotron-3-ultra-550b-a55b",
            "Nemotron 3 Ultra 550B",
            "NVIDIA flagship reasoning model (NIM endpoint)",
        ),
    ],
}

# Bump when the default-enabled set changes so existing configs get migrated once.
CATALOG_DEFAULTS_VERSION = 2

# Models present in the catalog but hidden by default. Users can re-enable them
# from Dashboard → Models; toggling simply removes them from the hidden list.
DEFAULT_DISABLED_MODELS: frozenset[str] = frozenset(
    {
        "claude-sonnet-4-5-20250929",
        "claude-haiku-4-5-20251001",
        "claude-opus-4-6",
        "gpt-5.5-pro",
        "gpt-5.4",
        "gpt-5.4-pro",
        "gpt-5.4-mini",
        "gpt-5.4-nano",
        "gpt-5-mini",
        "gpt-5-nano",
    }
)

CUSTOM_OPENAI_COMPATIBLE_ENTRY = (
    "__custom_openai_compatible__",
    "OpenAI-compatible profiles",
    "Use, add, or edit Ollama/Unsloth/oMLX/custom OpenAI-compatible profiles",
)

# OpenCode Zen models that speak the Anthropic Messages API
# (https://opencode.ai/zen/v1/messages). GPT models use Responses API;
# open models (Kimi, GLM, DeepSeek, MiniMax, …) use chat completions.
_OPENCODE_ANTHROPIC_PREFIXES = ("claude-", "qwen")

# Discovered OpenCode Zen ids that fail end-to-end (upstream 400 / unsupported
# format). Filtered out of /v1/models so they never appear in the UI.
OPENCODE_UNSUPPORTED_MODELS: frozenset[str] = frozenset(
    {
        "claude-sonnet-4",  # not on Zen full model list
        "gemini-3-flash",  # Zen Gemini path: missing contents
        "gemini-3.1-pro",  # Zen Gemini path: missing contents
        "gpt-5",  # upstream request failed
        "gpt-5-codex",  # upstream request failed
        "gpt-5.1-codex",  # upstream request failed
        "gpt-5.1-codex-max",  # upstream request failed
        "gpt-5.1-codex-mini",  # upstream request failed
        "gpt-5.2-codex",  # upstream request failed
        "gpt-5.3-codex-spark",  # not supported for openai format
    }
)


def opencode_model_is_supported(model_id: str | None) -> bool:
    """Return False when a discovered OpenCode Zen id is denylisted."""
    value = str(model_id or "").strip()
    if not value:
        return False
    return value not in OPENCODE_UNSUPPORTED_MODELS


def format_discovered_model_label(model_id: str) -> str:
    """Turn a raw model id like ``kimi-k2.7-code`` into ``Kimi K2.7 Code``.

    Known product acronyms (``gpt``, ``glm``, …) stay fully uppercase.
    """
    raw = str(model_id or "").strip()
    if not raw:
        return raw
    # Tokens that should stay ALL CAPS in UI labels (GPT 5.1, GLM 5, …).
    acronyms = {"gpt", "glm", "aws", "api", "llm", "ml"}
    parts = raw.replace("_", "-").split("-")
    out: list[str] = []
    for part in parts:
        if not part:
            continue
        lower = part.lower()
        if lower in acronyms:
            out.append(lower.upper())
            continue
        # Keep version-like tokens readable (k2.7 -> K2.7, v4 -> V4).
        out.append(part[:1].upper() + part[1:])
    return " ".join(out) or raw


def opencode_model_uses_anthropic(model_id: str) -> bool:
    """Return True when an OpenCode Zen model must use the Anthropic Messages API."""
    normalized = str(model_id or "").strip().lower()
    return any(normalized.startswith(prefix) for prefix in _OPENCODE_ANTHROPIC_PREFIXES)


def opencode_model_uses_responses_api(model_id: str) -> bool:
    """Return True when an OpenCode Zen model must use OpenAI ``/v1/responses``."""
    normalized = str(model_id or "").strip().lower()
    return normalized.startswith("gpt-")


def opencode_anthropic_base_url(openai_base_url: str) -> str:
    """Convert OpenAI-compatible Zen base URL to Anthropic SDK base URL.

    OpenAI SDK expects ``.../zen/v1`` (appends ``/chat/completions`` or ``/responses``).
    Anthropic SDK expects ``.../zen`` (appends ``/v1/messages``).
    """
    base = str(openai_base_url or "").strip().rstrip("/")
    if base.endswith("/v1"):
        return base[:-3]
    return base


def openai_model_requires_responses_api(model_id: str) -> bool:
    """Return True when an OpenAI cloud model should use ``/v1/responses``.

    Codex models reject chat completions entirely. GPT-5 / o-series reject
    function tools + non-none reasoning_effort on chat completions — agent
    runs always use tools, so route those through Responses as well.
    """
    value = str(model_id or "").strip().lower()
    if not value:
        return False
    if value.startswith("o1") or value.startswith("o3") or value.startswith("o4"):
        return True
    if not value.startswith("gpt-"):
        return False
    if "codex" in value:
        return True
    # GPT-5 family (incl. 5.4 / 5.5 / 5.6 and -pro/-mini/-nano/-sol/…)
    if value.startswith("gpt-5"):
        # Chat-only / non-reasoning GPT-5 variants stay on chat completions.
        if "chat" in value and "latest" in value:
            return False
        return True
    return False


REASONING_EFFORT_LEVELS = ("low", "medium", "high")
REASONING_EFFORT_VALUES = ("none", "low", "medium", "high")


def model_supports_reasoning_effort(
    provider: str | None,
    model_id: str | None,
) -> bool:
    """Return True when the UI should expose Effort / Fast for this model."""
    provider_norm = str(provider or "").strip().lower()
    value = str(model_id or "").strip().lower()
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


def reasoning_effort_options(
    provider: str | None,
    model_id: str | None,
) -> list[str]:
    """Effort choices shown in the Cursor-style selector (Low/Medium/High)."""
    if not model_supports_reasoning_effort(provider, model_id):
        return []
    return list(REASONING_EFFORT_LEVELS)


def normalize_reasoning_effort(value: str | None, *, allow_none: bool = True) -> str:
    """Clamp effort to a supported value; default medium."""
    raw = str(value or "").strip().lower()
    allowed = REASONING_EFFORT_VALUES if allow_none else REASONING_EFFORT_LEVELS
    if raw in allowed:
        return raw
    return "medium"


def openai_reasoning_effort_floor(model_id: str | None) -> str:
    """Lowest ``reasoning_effort`` accepted by a given OpenAI model.

    Most GPT-5 models accept ``none``. Pro variants only allow medium+;
    classic ``gpt-5-mini`` / ``gpt-5-nano`` allow ``minimal`` but not ``none``.
    """
    value = str(model_id or "").strip().lower()
    if not value:
        return "none"
    if "pro" in value:
        return "medium"
    # Bare gpt-5-mini / gpt-5-nano (not gpt-5.4-mini / gpt-5.4-nano).
    if value in {"gpt-5-mini", "gpt-5-nano"} or value.startswith(
        ("gpt-5-mini-", "gpt-5-nano-")
    ):
        return "minimal"
    return "none"


_OPENAI_EFFORT_RANK = {
    "none": 0,
    "minimal": 1,
    "low": 2,
    "medium": 3,
    "high": 4,
    "xhigh": 5,
}


def clamp_openai_reasoning_effort(model_id: str | None, effort: str) -> str:
    """Raise effort up to the model floor when the requested level is too low."""
    floor = openai_reasoning_effort_floor(model_id)
    raw = str(effort or "").strip().lower() or floor
    if _OPENAI_EFFORT_RANK.get(raw, 3) < _OPENAI_EFFORT_RANK.get(floor, 0):
        return floor
    return raw


def effective_reasoning_effort(
    *,
    effort: str | None,
    fast: bool = False,
    model_id: str | None = None,
) -> str:
    """Resolve stored effort + Fast toggle to the API reasoning_effort value."""
    if fast:
        return openai_reasoning_effort_floor(model_id)
    return clamp_openai_reasoning_effort(model_id, normalize_reasoning_effort(effort))


def effective_anthropic_effort(
    *,
    effort: str | None,
    fast: bool = False,
) -> str:
    """Map UI effort/Fast onto Anthropic ``effort`` (no ``none`` level)."""
    if fast:
        return "low"
    raw = normalize_reasoning_effort(effort)
    if raw == "none":
        return "low"
    return raw


def effective_gemini_thinking_level(
    *,
    effort: str | None,
    fast: bool = False,
) -> str:
    """Map UI effort/Fast onto Gemini 3+ ``thinking_level``."""
    if fast:
        return "minimal"
    raw = normalize_reasoning_effort(effort)
    if raw in {"none", "low"}:
        return "low" if raw == "low" else "minimal"
    if raw == "high":
        return "high"
    return "medium"


def effective_xai_reasoning_effort(
    *,
    effort: str | None,
    fast: bool = False,
    model_id: str | None = None,
) -> str:
    """Map UI effort/Fast onto xAI ``reasoning_effort``.

    ``grok-4.5`` accepts only low/medium/high (cannot disable). ``grok-4.3``
    also accepts ``none``. Fast maps to the lowest allowed level.
    """
    value = str(model_id or "").strip().lower()
    # 4.5 cannot disable reasoning; 4.3 / 4.20 accept none.
    allows_none = "4.5" not in value
    if fast:
        return "none" if allows_none else "low"
    raw = normalize_reasoning_effort(effort)
    if raw == "none" and not allows_none:
        return "low"
    return raw


def reasoning_settings_key(provider: str | None, model_id: str | None) -> str:
    """Stable per-model key: ``provider:model``."""
    prov = str(provider or "").strip().lower() or "openai"
    mid = resolve_catalog_model_id(model_id)
    return f"{prov}:{mid}"


def read_model_reasoning_store(raw: object) -> dict[str, dict[str, object]]:
    """Normalize ``llm.model_reasoning`` into a plain dict."""
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, object]] = {}
    for key, value in raw.items():
        k = str(key or "").strip()
        if not k or not isinstance(value, dict):
            continue
        out[k] = {
            "effort": normalize_reasoning_effort(
                str(value.get("effort") or "medium"),
                allow_none=False,
            ),
            "fast": bool(value.get("fast", False)),
        }
    return out


def get_model_reasoning(
    store: object,
    provider: str | None,
    model_id: str | None,
    *,
    default_effort: str = "medium",
    default_fast: bool = False,
) -> tuple[str, bool]:
    """Return ``(effort, fast)`` for a model from the per-model store."""
    key = reasoning_settings_key(provider, model_id)
    normalized = read_model_reasoning_store(store)
    entry = normalized.get(key)
    if not entry:
        return (
            normalize_reasoning_effort(default_effort, allow_none=False),
            bool(default_fast),
        )
    return (
        normalize_reasoning_effort(str(entry.get("effort") or default_effort), allow_none=False),
        bool(entry.get("fast", default_fast)),
    )


def upsert_model_reasoning(
    store: object,
    provider: str | None,
    model_id: str | None,
    *,
    effort: str | None = None,
    fast: bool | None = None,
) -> dict[str, dict[str, object]]:
    """Return an updated ``llm.model_reasoning`` map with one model patched."""
    normalized = read_model_reasoning_store(store)
    key = reasoning_settings_key(provider, model_id)
    current_effort, current_fast = get_model_reasoning(normalized, provider, model_id)
    next_effort = (
        normalize_reasoning_effort(effort, allow_none=False)
        if effort is not None
        else current_effort
    )
    next_fast = bool(fast) if fast is not None else current_fast
    normalized[key] = {"effort": next_effort, "fast": next_fast}
    return normalized


# Stale UI/config ids → current provider API ids.
CATALOG_MODEL_ALIASES: dict[str, str] = {
    "gemini-3.1-pro": "gemini-3.1-pro-preview",
}


def resolve_catalog_model_id(model_id: str | None) -> str:
    """Map deprecated catalog ids onto the current API model id."""
    value = str(model_id or "").strip()
    if not value:
        return ""
    return CATALOG_MODEL_ALIASES.get(value, value)


def anthropic_model_omits_temperature(model_id: str | None) -> bool:
    """Return True when Anthropic rejects non-default sampling params.

    Opus 4.7+, Sonnet 5, Fable 5, and Mythos 5 return HTTP 400 if
    ``temperature`` / ``top_p`` / ``top_k`` are set to non-default values.
    """
    import re

    value = str(model_id or "").strip().lower()
    if not value:
        return False
    if value.startswith("claude-sonnet-5"):
        return True
    if value.startswith("claude-fable-5") or value.startswith("claude-mythos-5"):
        return True
    # opus-4-7 / opus-4-8 (optional suffix), not opus-4-6 / opus-4-5 / opus-4-80.
    if re.search(r"(?:^|[^0-9])opus-4-[78](?:$|[^0-9])", value):
        return True
    return False


def cloud_catalog_models() -> list[CatalogModel]:
    """Flatten cloud catalog into typed records."""
    items: list[CatalogModel] = []
    for provider, rows in AVAILABLE_MODELS.items():
        for model_id, label, description in rows:
            items.append(
                {
                    "id": model_id,
                    "label": label,
                    "description": description,
                    "provider": provider,
                }
            )
    return items


def catalog_provider_for_model(model_id: str | None) -> str | None:
    """Return the cloud catalog provider for a model id, if known.

    Exact catalog matches win; otherwise use stable id prefixes so unlisted
    Gemini/Claude/Grok variants still map correctly.
    """
    value = str(model_id or "").strip()
    if not value:
        return None
    for provider, rows in AVAILABLE_MODELS.items():
        for mid, _label, _description in rows:
            if mid == value:
                return provider
    lower = value.lower()
    if lower.startswith("gemini-"):
        return "google"
    if lower.startswith("claude-"):
        return "anthropic"
    if lower.startswith("grok-"):
        return "xai"
    if lower.startswith("nvidia/"):
        return "nvidia"
    if (
        lower.startswith("gpt-4")
        or lower.startswith("gpt-5")
        or lower.startswith("o1")
        or lower.startswith("o3")
        or lower.startswith("chatgpt")
    ) and not lower.startswith("gpt-oss"):
        return "openai"
    return None


def terminal_available_models() -> dict[str, list[tuple[str, str, str]]]:
    """Catalog shape used by the interactive terminal `/model` command.

    Mirrors the full cloud catalog (all providers) so the CLI and the web UI
    stay consistent and centralized on AVAILABLE_MODELS.
    """
    openai_rows = list(AVAILABLE_MODELS.get("openai", []))
    openai_rows.append(CUSTOM_OPENAI_COMPATIBLE_ENTRY)
    result: dict[str, list[tuple[str, str, str]]] = {
        "anthropic": list(AVAILABLE_MODELS.get("anthropic", [])),
        "openai": openai_rows,
    }
    for provider, rows in AVAILABLE_MODELS.items():
        if provider in result:
            continue
        result[provider] = list(rows)
    return result
