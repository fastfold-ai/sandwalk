"""OpenAI-compatible profile CRUD + endpoint discovery for the Models page."""

from __future__ import annotations

from typing import Any

from agent.config import _UNSET, OPENAI_PROFILE_BACKENDS, OPENAI_PROFILE_DEFAULTS, Config
from agent_server.models import (
    ModelProfile,
    ModelProfileList,
    ModelProfileProbeResult,
    UpsertModelProfileRequest,
)
from agent_server.models_service.helpers import _to_profile


def list_profiles(cfg: Config, *, include_cloud: bool = True) -> ModelProfileList:
    active = cfg.active_openai_profile_id()
    default = cfg.default_openai_profile_id()
    items: list[ModelProfile] = []
    for profile_id, profile in cfg.openai_profiles(include_cloud=include_cloud).items():
        items.append(_to_profile(profile_id, profile, active=active, default=default))
    items.sort(key=lambda item: (0 if item.id == "openai_cloud" else 1, item.label.lower()))
    return ModelProfileList(data=items, count=len(items))


def get_profile(cfg: Config, profile_id: str) -> ModelProfile | None:
    profile = cfg.get_openai_profile(profile_id)
    if profile is None:
        return None
    return _to_profile(
        str(profile["id"]),
        profile,
        active=cfg.active_openai_profile_id(),
        default=cfg.default_openai_profile_id(),
    )


def upsert_profile(cfg: Config, payload: UpsertModelProfileRequest) -> ModelProfile:
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
    if payload.set_active:
        from agent.config import sync_process_env_from_config

        # Keep serve-process env aligned with the newly active Local LLM
        # profile so chat does not reuse a stale OPENAI_* key from cloud.
        sync_process_env_from_config(
            cfg,
            only_missing=False,
            config_keys=[
                "llm.openai_base_url",
                "llm.openai_api_key",
            ],
        )
    profile = cfg.get_openai_profile(profile_id)
    if profile is None:
        raise RuntimeError(f"Failed to persist profile '{profile_id}'.")
    return _to_profile(
        profile_id,
        profile,
        active=cfg.active_openai_profile_id(),
        default=cfg.default_openai_profile_id(),
    )


def delete_profile(cfg: Config, profile_id: str) -> bool:
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


def discover_endpoint(
    *,
    backend: str,
    base_url: str,
    api_key: str | None = None,
    profile_id: str = "preview",
) -> ModelProfileProbeResult:
    # Lazy self-lookup so tests that monkeypatch
    # `agent_server.models_service.probe_compatible_profile` are honored.
    from agent_server import models_service

    cleaned_url = str(base_url or "").strip()
    cleaned_backend = str(backend or "other").strip() or "other"
    cleaned_key = str(api_key or "").strip() or None
    if not cleaned_url:
        return ModelProfileProbeResult(
            profile_id=profile_id,
            health="error",
            models=[],
            models_source=None,
            error="Base URL is required.",
        )
    probe = models_service.probe_compatible_profile(
        base_url=cleaned_url,
        backend=cleaned_backend,
        api_key=cleaned_key,
    )
    return ModelProfileProbeResult(
        profile_id=profile_id,
        health=str(probe.get("health") or "error"),
        models=list(probe.get("models") or []),
        models_source=str(probe.get("models_source") or "") or None,
        error=str(probe.get("error") or "") or None,
    )


def probe_profile(cfg: Config, profile_id: str) -> ModelProfileProbeResult:
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
    return discover_endpoint(
        backend=backend,
        base_url=base_url,
        api_key=api_key,
        profile_id=str(profile["id"]),
    )
