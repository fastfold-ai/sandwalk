"""Live-discovered models from OpenAI-compatible providers and local profiles."""

from __future__ import annotations

from agent.config import OPENAI_COMPATIBLE_PROVIDERS, Config
from agent.model_catalog import (
    context_window_for_model,
    format_discovered_model_label,
    opencode_model_is_supported,
)
from agent_server.models import AgentModel
from agent_server.models_service.helpers import _reasoning_fields


def _discover_models_enabled(meta: dict) -> bool:
    return str(meta.get("discover_models") or "").strip().lower() in {"1", "true", "yes"}


def _openrouter_seen_models(cfg: Config) -> set[str]:
    raw = cfg.get("llm.openrouter_seen_models", [])
    if not isinstance(raw, list):
        return set()
    return {
        str(item).strip()
        for item in raw
        if str(item or "").strip()
    }


def _seed_openrouter_discovered_hidden(
    cfg: Config, discovered: list[str], known_ids: set[str]
) -> set[str]:
    """Default-disable newly discovered OpenRouter models (opt-in).

    Curated catalog ids are already in ``known_ids`` and keep their own
    DEFAULT_DISABLED / hidden migration. Only brand-new live ids are seeded
    into ``llm.hidden_models`` the first time we see them; later user enables
    stick because we never re-hide a previously seen id.
    """
    seen = _openrouter_seen_models(cfg)
    fresh = [
        model_id
        for model_id in discovered
        if model_id not in known_ids and model_id not in seen
    ]
    if not fresh:
        return set(cfg.hidden_models())

    hidden = set(cfg.hidden_models())
    hidden.update(fresh)
    seen.update(fresh)
    cfg.set("llm.hidden_models", sorted(hidden))
    cfg.set("llm.openrouter_seen_models", sorted(seen))
    try:
        cfg.save()
    except Exception:  # noqa: BLE001 — listing must still return models
        pass
    return hidden


def _provider_discovered_items(
    cfg: Config, hidden: set[str], known_ids: set[str], *, enabled_only: bool
) -> list[AgentModel]:
    # Lazy self-lookup so tests that monkeypatch
    # `agent_server.models_service.probe_compatible_profile` are honored.
    from agent_server import models_service

    items: list[AgentModel] = []
    # First-party proxy providers (e.g. OpenCode Go) that advertise
    # discover_models=true: fetch live catalog from /v1/models when a key
    # is configured. Discovered models are enabled by default — except
    # OpenRouter, where new discoveries start disabled (opt-in).
    for provider, meta in OPENAI_COMPATIBLE_PROVIDERS.items():
        if not _discover_models_enabled(meta):
            continue
        api_key = cfg.llm_api_key(provider)
        if not api_key:
            continue
        base_url = str(meta.get("base_url") or "").strip()
        if not base_url:
            continue
        label = str(meta.get("label") or provider)
        probe = models_service.probe_compatible_profile(
            base_url=base_url,
            backend="other",
            api_key=api_key,
        )
        discovered = list(probe.get("models") or [])
        context_windows = dict(probe.get("context_windows") or {})
        health = str(probe.get("health") or "") or None
        if not discovered:
            fallback = str(meta.get("default_model") or "").strip()
            if fallback:
                discovered = [fallback]
        active_hidden = hidden
        if provider == "openrouter":
            active_hidden = _seed_openrouter_discovered_hidden(
                cfg, discovered, known_ids
            )
            hidden.clear()
            hidden.update(active_hidden)
        for model_id in discovered:
            if model_id in known_ids:
                continue
            if provider == "opencode" and not opencode_model_is_supported(model_id):
                continue
            known_ids.add(model_id)
            enabled = model_id not in active_hidden
            if enabled_only and not enabled:
                continue
            context_window = context_windows.get(model_id)
            items.append(
                AgentModel(
                    id=model_id,
                    label=format_discovered_model_label(model_id),
                    description=f"{label} (discovered)",
                    provider=provider,
                    source="cloud",
                    profile_id=None,
                    backend=None,
                    enabled=enabled,
                    health=health,
                    context_window=(
                        int(context_window)
                        if context_window
                        else context_window_for_model(model_id)
                    ),
                    **_reasoning_fields(cfg, provider, model_id),
                )
            )
    return items


def _profile_discovered_items(
    cfg: Config, hidden: set[str], *, enabled_only: bool, discover: bool
) -> list[AgentModel]:
    from agent_server import models_service

    items: list[AgentModel] = []
    for profile_id, profile in cfg.openai_profiles(include_cloud=False).items():
        label = str(profile.get("label") or profile_id)
        backend = str(profile.get("backend") or "other")
        base_url = str(profile.get("base_url") or "").strip()
        api_key = str(profile.get("api_key") or "").strip() or None
        default_model = str(profile.get("default_model") or "").strip() or None
        discovered: list[str] = []
        health: str | None = None
        if discover and base_url:
            probe = models_service.probe_compatible_profile(
                base_url=base_url,
                backend=backend,
                api_key=api_key,
            )
            discovered = list(probe.get("models") or [])
            context_windows = dict(probe.get("context_windows") or {})
            health = str(probe.get("health") or "") or None
        else:
            context_windows = {}
        if not discovered and default_model:
            discovered = [default_model]

        for model_id in discovered:
            enabled = model_id not in hidden
            if enabled_only and not enabled:
                continue
            context_window = context_windows.get(model_id)
            items.append(
                AgentModel(
                    id=model_id,
                    label=format_discovered_model_label(model_id),
                    description=f"{label} ({backend})",
                    provider="local",
                    source="profile",
                    profile_id=profile_id,
                    backend=backend,
                    enabled=enabled,
                    health=health,
                    context_window=int(context_window) if context_window else None,
                    **_reasoning_fields(
                        cfg, "local", model_id, compatible_backend=backend
                    ),
                )
            )
    return items
