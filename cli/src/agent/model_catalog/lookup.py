"""Catalog lookups: id aliasing, flattening, and provider resolution."""

from __future__ import annotations

from agent.model_catalog.data import AVAILABLE_MODELS, CUSTOM_OPENAI_COMPATIBLE_ENTRY, CatalogModel

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
    if lower.startswith("kimi-") or lower.startswith("moonshot-"):
        return "moonshot"
    if lower.startswith("nvidia/"):
        return "nvidia"
    # Bare DeepSeek API ids (deepseek-v4-*); reseller paths use deepseek-ai/.
    if lower.startswith("deepseek") and not lower.startswith("deepseek-ai/"):
        return "deepseek"
    if lower.startswith("minimax") or lower.startswith("abab"):
        return "minimax"
    if (
        lower.startswith("mistral")
        or lower.startswith("codestral")
        or lower.startswith("pixtral")
        or lower.startswith("magistral")
    ):
        return "mistral"
    if lower.startswith("qwen"):
        return "qwen"
    if lower.startswith(
        (
            "thinkingmachines/",
            "zai-org/",
            "moonshotai/",
            "deepseek-ai/",
            "meta-llama/",
        )
    ):
        return "together"
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
