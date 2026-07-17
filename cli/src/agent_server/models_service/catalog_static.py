"""Cloud catalog + custom model entries for the models list."""

from __future__ import annotations

from agent.config import Config
from agent.model_catalog import cloud_catalog_models, context_window_for_model
from agent_server.models import AgentModel
from agent_server.models_service.helpers import _reasoning_fields


def _cloud_catalog_items(
    cfg: Config, hidden: set[str], known_ids: set[str], *, enabled_only: bool
) -> list[AgentModel]:
    items: list[AgentModel] = []
    for entry in cloud_catalog_models():
        model_id = entry["id"]
        known_ids.add(model_id)
        enabled = model_id not in hidden
        if enabled_only and not enabled:
            continue
        items.append(
            AgentModel(
                id=model_id,
                label=entry["label"],
                description=entry["description"],
                provider=entry["provider"],
                source="cloud",
                profile_id=None,
                backend=None,
                enabled=enabled,
                health=None,
                context_window=context_window_for_model(model_id),
                **_reasoning_fields(cfg, entry["provider"], model_id),
            )
        )
    return items


def _custom_model_items(
    cfg: Config, hidden: set[str], known_ids: set[str], *, enabled_only: bool
) -> list[AgentModel]:
    items: list[AgentModel] = []
    for entry in cfg.custom_models():
        model_id = entry["id"]
        known_ids.add(model_id)
        enabled = model_id not in hidden
        if enabled_only and not enabled:
            continue
        items.append(
            AgentModel(
                id=model_id,
                label=entry["label"],
                description=f"Custom {entry['provider']} model",
                provider=entry["provider"],
                source="custom",
                profile_id=None,
                backend=None,
                enabled=enabled,
                health=None,
                context_window=context_window_for_model(model_id),
                **_reasoning_fields(cfg, entry["provider"], model_id),
            )
        )
    return items
