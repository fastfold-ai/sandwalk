"""Enable/disable + custom model CRUD for the Models page."""

from __future__ import annotations

from agent.config import OPENAI_COMPATIBLE_PROVIDERS, Config
from agent.doctor.model_provider_http import supports_llm_key_probe
from agent.model_catalog import cloud_catalog_models, format_discovered_model_label
from agent_server.models import AgentModel, CreateAgentModelRequest, UpdateAgentModelRequest
from agent_server.models_service.catalog_discovery import _discover_models_enabled


def disable_models_for_provider(cfg: Config, provider: str) -> list[str]:
    """Hide catalog + custom models for an LLM provider. Returns ids newly hidden.

    Uses provider-scoped keys (``moonshot:kimi-k3``) so auto-hiding an
    unconfigured provider does not disable the same bare id under another
    provider (e.g. OpenCode Zen discovered ``kimi-k3``).
    """
    from agent.model_catalog import DEFAULT_DISABLED_MODELS

    target = str(provider or "").strip()
    if not target or not supports_llm_key_probe(target):
        return []
    ids = [
        str(item["id"])
        for item in cloud_catalog_models()
        if str(item.get("provider") or "") == target
    ]
    for item in cfg.custom_models():
        if str(item.get("provider") or "") == target:
            ids.append(str(item["id"]))
    newly_hidden: list[str] = []
    hidden = set(cfg.hidden_models())
    changed = False
    for model_id in ids:
        scoped = cfg.provider_model_key(target, model_id)
        if scoped not in hidden:
            hidden.add(scoped)
            newly_hidden.append(scoped)
            changed = True
        # Drop legacy bare-id auto-hides so shared ids can surface elsewhere.
        if model_id in hidden and model_id not in DEFAULT_DISABLED_MODELS:
            hidden.discard(model_id)
            changed = True
    if changed:
        cfg.set("llm.hidden_models", sorted(hidden))
    return newly_hidden


def enable_models_for_provider(cfg: Config, provider: str) -> list[str]:
    """Clear provider-scoped auto-hides when a key is present."""
    target = str(provider or "").strip()
    if not target or not supports_llm_key_probe(target):
        return []
    prefix = f"{target}:"
    hidden = set(cfg.hidden_models())
    removed = sorted(item for item in hidden if item.startswith(prefix))
    if not removed:
        return []
    hidden.difference_update(removed)
    cfg.set("llm.hidden_models", sorted(hidden))
    return removed


def _cloud_provider_key_present(cfg: Config, provider: str) -> bool:
    """True when the cloud API-key integration for ``provider`` has a secret."""
    import os

    if provider == "openai":
        return bool(
            cfg._normalized_secret(cfg.get("llm.openai_api_key"))
            or cfg._normalized_secret(os.environ.get("OPENAI_API_KEY"))
        )
    if provider == "anthropic":
        return bool(
            cfg._normalized_secret(cfg.get("llm.anthropic_api_key"))
            or cfg._normalized_secret(cfg.get("llm.api_key"))
            or cfg._normalized_secret(os.environ.get("ANTHROPIC_API_KEY"))
        )
    if provider == "bedrock":
        # IAM default — do not hide the static Bedrock gallery for missing keys.
        return True
    return bool(cfg.llm_api_key(provider))


def sync_models_for_unconfigured_providers(cfg: Config) -> bool:
    """Hide models for LLM providers with no key. Returns True if config changed.

    Does not auto-unhide when a key is present — that would wipe user toggles
    on every Models list. Call ``enable_models_for_provider`` from the
    integrations save path when a key is newly stored.
    """
    changed = False
    providers = ("anthropic", "openai", *OPENAI_COMPATIBLE_PROVIDERS.keys())
    for provider in providers:
        if _cloud_provider_key_present(cfg, provider):
            continue
        if disable_models_for_provider(cfg, provider):
            changed = True
    return changed


def set_model_enabled(
    model_id: str,
    enabled: bool,
    *,
    provider: str | None = None,
) -> AgentModel:
    cfg = Config.load()
    target = str(model_id or "").strip()
    if not target:
        raise ValueError("model_id is required.")
    provider_norm = str(provider or "").strip().lower() or None
    # Prefer provider-scoped keys so toggling OpenCode kimi-k3 does not
    # hide/show the Moonshot row with the same bare id.
    hide_key = (
        cfg.provider_model_key(provider_norm, target)
        if provider_norm
        else target
    )
    cfg.set_model_hidden(hide_key, hidden=not enabled)
    # Clear the opposite form so scoped/bare state cannot fight.
    if provider_norm:
        if target in set(cfg.hidden_models()) and enabled:
            cfg.set_model_hidden(target, hidden=False)
    cfg.save()

    # Return a compact representation without rediscovering endpoints.
    catalog_rows = [
        item
        for item in cloud_catalog_models()
        if item["id"] == target
        and (not provider_norm or item["provider"] == provider_norm)
    ]
    if catalog_rows:
        entry = catalog_rows[0]
        return AgentModel(
            id=target,
            label=entry["label"],
            description=entry["description"],
            provider=entry["provider"],
            source="cloud",
            profile_id=None,
            backend=None,
            enabled=enabled,
            health=None,
        )
    custom = next(
        (
            item
            for item in cfg.custom_models()
            if item["id"] == target
            and (not provider_norm or item.get("provider") == provider_norm)
        ),
        None,
    )
    if custom:
        return AgentModel(
            id=target,
            label=custom["label"],
            description=f"Custom {custom['provider']} model",
            provider=custom["provider"],
            source="custom",
            profile_id=None,
            backend=None,
            enabled=enabled,
            health=None,
        )
    # Discovered cloud proxy models (e.g. OpenCode Zen) are not in the static
    # catalog — attribute them to the requested / configured discover provider.
    for discover_provider, meta in OPENAI_COMPATIBLE_PROVIDERS.items():
        if not _discover_models_enabled(meta):
            continue
        if provider_norm and discover_provider != provider_norm:
            continue
        if not cfg.llm_api_key(discover_provider):
            continue
        return AgentModel(
            id=target,
            label=format_discovered_model_label(target),
            description=f"{meta.get('label') or discover_provider} (discovered)",
            provider=discover_provider,
            source="cloud",
            profile_id=None,
            backend=None,
            enabled=enabled,
            health=None,
        )
    return AgentModel(
        id=target,
        label=target,
        description=None,
        provider=provider_norm or "local",
        source="profile",
        profile_id=None,
        backend=None,
        enabled=enabled,
        health=None,
    )


def create_custom_model(payload: CreateAgentModelRequest) -> AgentModel:
    cfg = Config.load()
    record = cfg.add_custom_model(
        model_id=payload.id,
        provider=payload.provider,
        label=payload.label,
    )
    cfg.save()
    return AgentModel(
        id=record["id"],
        label=record["label"],
        description=f"Custom {record['provider']} model",
        provider=record["provider"],
        source="custom",
        profile_id=None,
        backend=None,
        enabled=not cfg.is_model_hidden(record["id"], record["provider"]),
        health=None,
    )


def delete_custom_model(model_id: str) -> bool:
    cfg = Config.load()
    removed = cfg.remove_custom_model(model_id)
    if not removed:
        return False
    cfg.save()
    return True


def update_model(model_id: str, payload: UpdateAgentModelRequest) -> AgentModel:
    if payload.enabled is None:
        raise ValueError("enabled is required.")
    return set_model_enabled(
        model_id,
        bool(payload.enabled),
        provider=payload.provider,
    )
