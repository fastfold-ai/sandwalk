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


def _drop_unconfirmed_curated(items: list[AgentModel]) -> list[AgentModel]:
    """Drop hardcoded OpenAI/Anthropic rows the provider did not return.

    Live /v1/models is the source of truth once a fetch succeeds. Curated
    names that are not in that list (and therefore cannot be called) stay
    out of the composer. A failed fetch leaves the curated list alone.
    """
    from agent_server.models_service.first_party_discovery import confirmed_live_ids

    live = {
        "openai": confirmed_live_ids("openai"),
        "anthropic": confirmed_live_ids("anthropic"),
    }
    if live["openai"] is None and live["anthropic"] is None:
        return items
    kept: list[AgentModel] = []
    for item in items:
        provider = item.provider
        catalog = live.get("openai" if provider == "openai-chatgpt" else provider)
        if item.source == "cloud" and catalog is not None and item.id not in catalog:
            continue
        kept.append(item)
    return kept


def list_models(
    cfg: Config, *, enabled_only: bool = False, discover: bool = True
) -> AgentModelList:
    # Keep toggles aligned with API Keys: no key ⇒ models off.
    from agent_server.models_service.mutate import (
        sync_models_for_unconfigured_providers,
    )

    if sync_models_for_unconfigured_providers(cfg):
        cfg.save()

    hidden = set(cfg.hidden_models())
    # Bare ids already present in the static/custom catalog. Used only for
    # OpenRouter "fresh discovery → start hidden" seeding — not to suppress
    # the same id under another provider (OpenCode Zen, Qwen, …).
    known_ids: set[str] = set()

    items: list[AgentModel] = []
    items.extend(_cloud_catalog_items(cfg, hidden, known_ids, enabled_only=enabled_only))
    items.extend(_custom_model_items(cfg, hidden, known_ids, enabled_only=enabled_only))
    if discover:
        # OpenAI + Anthropic: anything their /v1/models lists that the curated
        # catalog does not, so a new family appears without a Sandwalk release.
        from agent_server.models_service.first_party_discovery import (
            first_party_discovered_items,
        )

        items.extend(
            first_party_discovered_items(cfg, hidden, known_ids, enabled_only=enabled_only)
        )
        items = _drop_unconfirmed_curated(items)
        items.extend(
            _provider_discovered_items(cfg, hidden, known_ids, enabled_only=enabled_only)
        )
    items.extend(
        _profile_discovered_items(cfg, hidden, enabled_only=enabled_only, discover=discover)
    )

    # De-dupe by (provider, id, profile_id) so the same bare id can appear
    # under Moonshot and OpenCode Zen (e.g. kimi-k3) without collapsing.
    seen: set[tuple[str, str, str | None]] = set()
    unique: list[AgentModel] = []
    for item in items:
        key = (item.provider, item.id, item.profile_id)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return AgentModelList(data=unique, count=len(unique))
