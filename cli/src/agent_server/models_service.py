"""Model catalog + OpenAI-compatible profile management for the agent server."""

from __future__ import annotations

from typing import Any

from agent.config import (
    OPENAI_COMPATIBLE_PROVIDERS,
    OPENAI_PROFILE_BACKENDS,
    OPENAI_PROFILE_DEFAULTS,
    Config,
    _UNSET,
)
from agent.model_catalog import cloud_catalog_models, format_discovered_model_label
from agent.model_discovery import probe_compatible_profile
from agent_server.models import (
    AgentModel,
    AgentModelList,
    CreateAgentModelRequest,
    ModelProfile,
    ModelProfileList,
    ModelProfileProbeResult,
    UpsertModelProfileRequest,
    UpdateAgentModelRequest,
)


def _masked_preview(value: str | None) -> str | None:
    normalized = str(value or "").strip()
    if not normalized:
        return None
    if len(normalized) <= 8:
        return "••••••••"
    return f"{normalized[:4]}…{normalized[-4:]}"


class ModelsService:
    def list_models(
        self,
        *,
        enabled_only: bool = False,
        discover: bool = True,
    ) -> AgentModelList:
        cfg = Config.load()
        hidden = set(cfg.hidden_models())
        items: list[AgentModel] = []
        # Track static/custom ids so discovered entries don't duplicate them.
        known_ids: set[str] = set()

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
                    enabled=enabled,
                    health=None,
                )
            )

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
                    enabled=enabled,
                    health=None,
                )
            )

        # First-party proxy providers (e.g. OpenCode Go) that advertise
        # discover_models=true: fetch live catalog from /v1/models when a key
        # is configured. Discovered models are enabled by default.
        if discover:
            for provider, meta in OPENAI_COMPATIBLE_PROVIDERS.items():
                if str(meta.get("discover_models") or "").strip().lower() not in {
                    "1",
                    "true",
                    "yes",
                }:
                    continue
                api_key = cfg.llm_api_key(provider)
                if not api_key:
                    continue
                base_url = str(meta.get("base_url") or "").strip()
                if not base_url:
                    continue
                label = str(meta.get("label") or provider)
                probe = probe_compatible_profile(
                    base_url=base_url,
                    backend="other",
                    api_key=api_key,
                )
                discovered = list(probe.get("models") or [])
                health = str(probe.get("health") or "") or None
                if not discovered:
                    fallback = str(meta.get("default_model") or "").strip()
                    if fallback:
                        discovered = [fallback]
                for model_id in discovered:
                    if model_id in known_ids:
                        continue
                    known_ids.add(model_id)
                    enabled = model_id not in hidden
                    if enabled_only and not enabled:
                        continue
                    items.append(
                        AgentModel(
                            id=model_id,
                            label=format_discovered_model_label(model_id),
                            description=f"{label} (discovered)",
                            provider=provider,
                            source="cloud",
                            profile_id=None,
                            enabled=enabled,
                            health=health,
                        )
                    )

        for profile_id, profile in cfg.openai_profiles(include_cloud=False).items():
            label = str(profile.get("label") or profile_id)
            backend = str(profile.get("backend") or "other")
            base_url = str(profile.get("base_url") or "").strip()
            api_key = str(profile.get("api_key") or "").strip() or None
            default_model = str(profile.get("default_model") or "").strip() or None
            discovered: list[str] = []
            health: str | None = None
            if discover and base_url:
                probe = probe_compatible_profile(
                    base_url=base_url,
                    backend=backend,
                    api_key=api_key,
                )
                discovered = list(probe.get("models") or [])
                health = str(probe.get("health") or "") or None
            if not discovered and default_model:
                discovered = [default_model]

            for model_id in discovered:
                enabled = model_id not in hidden
                if enabled_only and not enabled:
                    continue
                items.append(
                    AgentModel(
                        id=model_id,
                        label=model_id,
                        description=f"{label} ({backend})",
                        provider="local",
                        source="profile",
                        profile_id=profile_id,
                        enabled=enabled,
                        health=health,
                    )
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

    def set_model_enabled(self, model_id: str, enabled: bool) -> AgentModel:
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
                enabled=enabled,
                health=None,
            )
        # Discovered cloud proxy models (e.g. OpenCode Go) are not in the static
        # catalog — attribute them to the discoverable provider that has a key.
        for provider, meta in OPENAI_COMPATIBLE_PROVIDERS.items():
            if str(meta.get("discover_models") or "").strip().lower() not in {
                "1",
                "true",
                "yes",
            }:
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
            enabled=enabled,
            health=None,
        )

    def create_custom_model(self, payload: CreateAgentModelRequest) -> AgentModel:
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
            enabled=record["id"] not in set(cfg.hidden_models()),
            health=None,
        )

    def delete_custom_model(self, model_id: str) -> bool:
        cfg = Config.load()
        removed = cfg.remove_custom_model(model_id)
        if not removed:
            return False
        cfg.save()
        return True

    def update_model(self, model_id: str, payload: UpdateAgentModelRequest) -> AgentModel:
        if payload.enabled is None:
            raise ValueError("enabled is required.")
        return self.set_model_enabled(model_id, bool(payload.enabled))

    def list_profiles(self, *, include_cloud: bool = True) -> ModelProfileList:
        cfg = Config.load()
        active = cfg.active_openai_profile_id()
        default = cfg.default_openai_profile_id()
        items: list[ModelProfile] = []
        for profile_id, profile in cfg.openai_profiles(include_cloud=include_cloud).items():
            items.append(self._to_profile(profile_id, profile, active=active, default=default))
        items.sort(key=lambda item: (0 if item.id == "openai_cloud" else 1, item.label.lower()))
        return ModelProfileList(data=items, count=len(items))

    def get_profile(self, profile_id: str) -> ModelProfile | None:
        cfg = Config.load()
        profile = cfg.get_openai_profile(profile_id)
        if profile is None:
            return None
        return self._to_profile(
            str(profile["id"]),
            profile,
            active=cfg.active_openai_profile_id(),
            default=cfg.default_openai_profile_id(),
        )

    def upsert_profile(self, payload: UpsertModelProfileRequest) -> ModelProfile:
        cfg = Config.load()
        backend = str(payload.backend or "").strip().lower() or None
        if backend and backend not in OPENAI_PROFILE_BACKENDS:
            raise ValueError(f"Unsupported backend '{payload.backend}'.")
        if payload.id and str(payload.id).strip().lower() == "openai_cloud":
            # Allow editing label/default_model/api_key for cloud, but keep backend/url fixed.
            backend = "openai"
            base_url = str(OPENAI_PROFILE_DEFAULTS["openai"]["base_url"])
        else:
            base_url = payload.base_url

        api_key: Any = _UNSET
        if payload.api_key is not None:
            api_key = payload.api_key

        profile_id = cfg.upsert_openai_profile(
            profile_id=payload.id,
            label=payload.label,
            backend=backend,
            base_url=base_url,
            api_key=api_key,
            default_model=payload.default_model,
            discovery=payload.discovery,
            set_active=bool(payload.set_active),
            set_default=bool(payload.set_default),
        )
        cfg.save()
        profile = cfg.get_openai_profile(profile_id)
        if profile is None:
            raise RuntimeError(f"Failed to persist profile '{profile_id}'.")
        return self._to_profile(
            profile_id,
            profile,
            active=cfg.active_openai_profile_id(),
            default=cfg.default_openai_profile_id(),
        )

    def delete_profile(self, profile_id: str) -> bool:
        cfg = Config.load()
        selected = str(profile_id or "").strip()
        if not selected:
            raise ValueError("profile_id is required.")
        existing = cfg.get_openai_profile(selected)
        if existing and str(existing.get("id")) == "openai_cloud":
            raise ValueError("The OpenAI cloud profile cannot be deleted.")
        removed = cfg.remove_openai_profile(selected)
        if not removed:
            return False
        cfg.save()
        return True

    def probe_profile(self, profile_id: str) -> ModelProfileProbeResult:
        cfg = Config.load()
        profile = cfg.get_openai_profile(profile_id)
        if profile is None:
            raise KeyError(profile_id)
        base_url = str(profile.get("base_url") or "").strip()
        backend = str(profile.get("backend") or "other")
        api_key = str(profile.get("api_key") or "").strip() or None
        if not base_url:
            return ModelProfileProbeResult(
                profile_id=str(profile["id"]),
                health="error",
                models=[],
                models_source=None,
                error="Profile has no base URL.",
            )
        probe = probe_compatible_profile(
            base_url=base_url,
            backend=backend,
            api_key=api_key,
        )
        return ModelProfileProbeResult(
            profile_id=str(profile["id"]),
            health=str(probe.get("health") or "error"),
            models=list(probe.get("models") or []),
            models_source=str(probe.get("models_source") or "") or None,
            error=str(probe.get("error") or "") or None,
        )

    @staticmethod
    def _to_profile(
        profile_id: str,
        profile: dict[str, Any],
        *,
        active: str | None,
        default: str | None,
    ) -> ModelProfile:
        api_key = str(profile.get("api_key") or "").strip() or None
        return ModelProfile(
            id=profile_id,
            label=str(profile.get("label") or profile_id),
            backend=str(profile.get("backend") or "other"),
            base_url=str(profile.get("base_url") or "") or None,
            default_model=str(profile.get("default_model") or "") or None,
            discovery=[str(item) for item in (profile.get("discovery") or [])],
            has_api_key=bool(api_key),
            api_key_preview=_masked_preview(api_key),
            is_cloud=profile_id == "openai_cloud",
            is_active=profile_id == active,
            is_default=profile_id == default,
        )
