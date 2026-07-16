"""Assembled models list (catalog + custom + discovered) for the Models page."""

from __future__ import annotations

from agent.config import Config
from agent_server.models import AgentModel, AgentModelList
from agent_server.models_service.catalog_discovery import (
    _profile_discovered_items,
    _provider_discovered_items,
)
from agent_server.models_service.catalog_static import (
    _cloud_catalog_items,
    _custom_model_items,
)


def list_models(
    cfg: Config, *, enabled_only: bool = False, discover: bool = True
) -> AgentModelList:
    hidden = set(cfg.hidden_models())
    # Track static/custom ids so discovered entries don't duplicate them.
    known_ids: set[str] = set()

    items: list[AgentModel] = []
    items.extend(_cloud_catalog_items(cfg, hidden, known_ids, enabled_only=enabled_only))
    items.extend(_custom_model_items(cfg, hidden, known_ids, enabled_only=enabled_only))
    if discover:
        items.extend(
            _provider_discovered_items(cfg, hidden, known_ids, enabled_only=enabled_only)
        )
    items.extend(
        _profile_discovered_items(cfg, hidden, enabled_only=enabled_only, discover=discover)
    )

    # De-dupe by (id, profile_id) preferring first occurrence.
    seen: set[tuple[str, str | None]] = set()
    unique: list[AgentModel] = []
    for item in items:
        key = (item.id, item.profile_id)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return AgentModelList(data=unique, count=len(unique))
