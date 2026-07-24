"""Enable/disable + custom model CRUD for the Models page."""

from __future__ import annotations

from agent.config import OPENAI_COMPATIBLE_PROVIDERS, Config
from agent.doctor.model_provider_http import supports_llm_key_probe
from agent.model_catalog import cloud_catalog_models, format_discovered_model_label
from agent_server.models import AgentModel, CreateAgentModelRequest, UpdateAgentModelRequest
from agent_server.models_service.catalog_discovery import _discover_models_enabled


def disable_models_for_provider(cfg: Config, provider: str) -> list[str]:
    """Hide catalog + custom models for an LLM provider. Returns ids newly hidden."""
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
    for model_id in ids:
        if cfg.is_model_hidden(model_id):
            continue
        cfg.set_model_hidden(model_id, True)
        newly_hidden.append(model_id)
    return newly_hidden


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
    return bool(cfg.llm_api_key(provider))


def sync_models_for_unconfigured_providers(cfg: Config) -> bool:
    """Hide models for LLM providers with no key. Returns True if config changed."""
    changed = False
    providers = ("anthropic", "openai", *OPENAI_COMPATIBLE_PROVIDERS.keys())
    for provider in providers:
        if _cloud_provider_key_present(cfg, provider):
            continue
        if disable_models_for_provider(cfg, provider):
            changed = True
    return changed


def set_model_enabled(model_id: str, enabled: bool) -> AgentModel:
    cfg = Config.load()
    target = str(model_id or "").strip()
    if not target:
        raise ValueError("model_id is required.")
    cfg.set_model_hidden(target, hidden=not enabled)
    cfg.save()

    # Return a compact representation without rediscovering endpoints.
    catalog = {item["id"]: item for item in cloud_catalog_models()}
    if target in catalog:
        entry = catalog[target]
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
    custom = next((item for item in cfg.custom_models() if item["id"] == target), None)
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
    # Discovered cloud proxy models (e.g. OpenCode Go) are not in the static
    # catalog — attribute them to the discoverable provider that has a key.
    for provider, meta in OPENAI_COMPATIBLE_PROVIDERS.items():
        if not _discover_models_enabled(meta):
            continue
        if not cfg.llm_api_key(provider):
            continue
        return AgentModel(
            id=target,
            label=format_discovered_model_label(target),
            description=f"{meta.get('label') or provider} (discovered)",
            provider=provider,
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
        provider="local",
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
        enabled=record["id"] not in set(cfg.hidden_models()),
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
    return set_model_enabled(model_id, bool(payload.enabled))
