"""Catalog lookups: id aliasing, flattening, and provider resolution."""

from __future__ import annotations

from agent.model_catalog.data import AVAILABLE_MODELS, CUSTOM_OPENAI_COMPATIBLE_ENTRY, CatalogModel

# Stale UI/config ids → current provider API ids.
CATALOG_MODEL_ALIASES: dict[str, str] = {
    "gemini-3.1-pro": "gemini-3.1-pro-preview",
    "claude-fable-5.1": "claude-fable-5-1",
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


def catalog_providers_for_model(model_id: str | None) -> list[str]:
    """Return every static-catalog provider that lists ``model_id`` exactly.

    The same bare id can appear under multiple providers (e.g. ``kimi-k3`` on
    Moonshot while also discoverable on OpenCode Zen). Callers that know the
    active ``llm.provider`` must prefer that over a single heuristic owner.
    """
    value = str(model_id or "").strip()
    if not value:
        return []
    found: list[str] = []
    for provider, rows in AVAILABLE_MODELS.items():
        for mid, _label, _description in rows:
            if mid == value:
                found.append(provider)
                break
    return found


def catalog_label_for_model(
    model_id: str | None, *, provider: str | None = None
) -> str | None:
    """Return a catalog display label, preferring ``provider`` when it lists the id."""
    value = str(model_id or "").strip()
    if not value:
        return None
    provider_norm = str(provider or "").strip().lower()
    if provider_norm:
        for mid, label, _description in AVAILABLE_MODELS.get(provider_norm, []):
            if mid == value and label:
                return str(label)
    for _provider, rows in AVAILABLE_MODELS.items():
        for mid, label, _description in rows:
            if mid == value and label:
                return str(label)
    return None


def catalog_provider_for_model(model_id: str | None) -> str | None:
    """Return a cloud catalog provider for a model id, if known.

    Exact catalog matches win (first provider in ``AVAILABLE_MODELS`` order).
    The same bare id can be offered by multiple providers (e.g. ``kimi-k3``
    on Moonshot and OpenCode Zen) — callers that know the active provider
    should prefer ``llm.provider`` / ``catalog_providers_for_model`` over this
    heuristic. Prefix rules cover unlisted Gemini/Claude/Grok variants.
    """
    owners = catalog_providers_for_model(model_id)
    if owners:
        return owners[0]
    value = str(model_id or "").strip()
    if not value:
        return None
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
    # Qwen Cloud Token Plan dated DeepSeek flash id (not native DeepSeek API).
    if lower == "deepseek-v4-flash-0731":
        return "qwen"
    # Bare DeepSeek API ids (deepseek-v4-*); reseller paths use deepseek-ai/.
    if lower.startswith("deepseek") and not lower.startswith("deepseek-ai/"):
        return "deepseek"
    # Bare Zhipu GLM ids served on Qwen Cloud (Together uses zai-org/…).
    if lower.startswith("glm-"):
        return "qwen"
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
    if lower.startswith("accounts/fireworks/"):
        return "fireworks"
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
        or lower.startswith("gpt-6")
        or lower.startswith("o1")
        or lower.startswith("o3")
        or lower.startswith("chatgpt")
    ) and not lower.startswith("gpt-oss"):
        return "openai"
    return None


def terminal_available_models() -> dict[str, list[tuple[str, str, str]]]:
    """Catalog shape used by the interactive terminal `/models` command.

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
