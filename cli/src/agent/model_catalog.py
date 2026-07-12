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
        ("gemini-3.1-pro", "Gemini 3.1 Pro", "Most intelligent Gemini for multimodal reasoning"),
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


def format_discovered_model_label(model_id: str) -> str:
    """Turn a raw model id like ``kimi-k2.7-code`` into ``Kimi K2.7 Code``."""
    raw = str(model_id or "").strip()
    if not raw:
        return raw
    parts = raw.replace("_", "-").split("-")
    out: list[str] = []
    for part in parts:
        if not part:
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
    """Return True when an OpenAI cloud model only works on ``/v1/responses``.

    Codex models (``gpt-*-codex``) reject ``/v1/chat/completions`` with a 404 and
    must be routed through the Responses API.
    """
    value = str(model_id or "").strip().lower()
    return value.startswith("gpt-") and "codex" in value


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
