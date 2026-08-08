"""Cloud catalog + custom model entries for the models list."""

from __future__ import annotations

from agent.config import Config
from agent.doctor.model_provider_http import supports_llm_key_probe
from agent.model_catalog import cloud_catalog_models, context_window_for_model
from agent_server.models import AgentModel
from agent_server.models_service.helpers import _reasoning_fields


def _provider_ready_for_enabled_list(cfg: Config, provider: str) -> bool:
    """When listing enabled models, require a configured cloud API key."""
    from agent_server.models_service.mutate import _cloud_provider_key_present

    if not supports_llm_key_probe(provider):
        return True
    return _cloud_provider_key_present(cfg, provider)


def _cloud_catalog_items(
    cfg: Config, hidden: set[str], known_ids: set[str], *, enabled_only: bool
) -> list[AgentModel]:
    items: list[AgentModel] = []
    for entry in cloud_catalog_models():
        model_id = entry["id"]
        provider = entry["provider"]
        known_ids.add(model_id)
        if enabled_only and not _provider_ready_for_enabled_list(cfg, provider):
            continue
        enabled = not cfg.is_model_hidden(model_id, provider)
        if enabled_only and not enabled:
            continue
        items.append(
            AgentModel(
                id=model_id,
                label=entry["label"],
                description=entry["description"],
                provider=provider,
                source="cloud",
                profile_id=None,
                backend=None,
                enabled=enabled,
                health=None,
                context_window=context_window_for_model(model_id),
                **_reasoning_fields(cfg, provider, model_id),
            )
        )
    return items


def _custom_model_items(
    cfg: Config, hidden: set[str], known_ids: set[str], *, enabled_only: bool
) -> list[AgentModel]:
    items: list[AgentModel] = []
    for entry in cfg.custom_models():
        model_id = entry["id"]
        provider = entry["provider"]
        known_ids.add(model_id)
        if enabled_only and not _provider_ready_for_enabled_list(cfg, provider):
            continue
        enabled = not cfg.is_model_hidden(model_id, provider)
        if enabled_only and not enabled:
            continue
        items.append(
            AgentModel(
                id=model_id,
                label=entry["label"],
                description=f"Custom {provider} model",
                provider=provider,
                source="custom",
                profile_id=None,
                backend=None,
                enabled=enabled,
                health=None,
                context_window=context_window_for_model(model_id),
                **_reasoning_fields(cfg, provider, model_id),
            )
        )
    return items
