"""Small formatting helpers shared by the models catalog and profile CRUD."""

from __future__ import annotations

from typing import Any

from agent.config import Config
from agent.model_catalog import (
    get_model_reasoning,
    modality_capability_fields,
    model_supports_reasoning_effort,
    reasoning_effort_options,
)
from agent_server.models import ModelProfile


def _masked_preview(value: str | None) -> str | None:
    normalized = str(value or "").strip()
    if not normalized:
        return None
    if len(normalized) <= 8:
        return "••••••••"
    return f"{normalized[:4]}…{normalized[-4:]}"


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


def _reasoning_fields(
    cfg: Config,
    provider: str,
    model_id: str,
    *,
    compatible_backend: str | None = None,
) -> dict[str, Any]:
    supports = model_supports_reasoning_effort(
        provider, model_id, compatible_backend=compatible_backend
    )
    effort, fast = get_model_reasoning(
        cfg.get("llm.model_reasoning"),
        provider,
        model_id,
    )
    return {
        "supports_reasoning_effort": supports,
        "reasoning_effort_options": (
            reasoning_effort_options(
                provider, model_id, compatible_backend=compatible_backend
            )
            if supports
            else []
        ),
        "reasoning_effort": effort if supports else None,
        "reasoning_fast": bool(fast) if supports else False,
        **modality_capability_fields(provider, model_id),
    }
