"""Human-readable Effort / Fast labels for CLI and UI surfaces."""

from __future__ import annotations

from typing import Any

from agent.model_catalog.reasoning_store import get_model_reasoning
from agent.model_catalog.reasoning_support import (
    model_supports_reasoning_effort,
    normalize_reasoning_effort,
)


def format_reasoning_effort_label(*, effort: str | None, fast: bool = False) -> str:
    """Format Effort and optional Fast (matches local-web model badge).

    Effort (Low/Medium/High) is always shown. Fast is a separate toggle, so
    when on the label is ``Medium · Fast`` rather than replacing the effort.
    """
    level = normalize_reasoning_effort(effort, allow_none=False).capitalize()
    if fast:
        return f"{level} · Fast"
    return level


def selected_reasoning_effort_label(
    store: object,
    provider: str | None,
    model_id: str | None,
    *,
    default_effort: str = "medium",
    default_fast: bool = False,
    compatible_backend: str | None = None,
) -> str | None:
    """Return the current Effort/Fast label, or None when the model has no control."""
    check_provider = str(provider or "").strip().lower() or "openai"
    if not model_supports_reasoning_effort(
        check_provider,
        model_id,
        compatible_backend=compatible_backend,
    ):
        return None
    effort, fast = get_model_reasoning(
        store,
        check_provider,
        model_id,
        default_effort=default_effort,
        default_fast=default_fast,
    )
    return format_reasoning_effort_label(effort=effort, fast=fast)


def _compatible_backend_from_config(cfg: Any) -> str | None:
    try:
        profile = cfg.get_openai_profile()
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(profile, dict):
        return None
    backend = str(profile.get("backend") or "").strip().lower() or None
    if backend in {None, "", "openai"}:
        return None
    return backend


def config_selected_effort_label(
    cfg: Any,
    *,
    provider: str | None = None,
    model_id: str | None = None,
) -> str | None:
    """Resolve Effort/Fast for a Config-like object (banner, toolbar, etc.)."""
    provider_norm = str(
        provider if provider is not None else cfg.get("llm.provider") or "openai"
    ).strip().lower()
    model = str(
        model_id if model_id is not None else cfg.get("llm.model") or ""
    ).strip()
    if not model:
        return None

    backend: str | None = None
    check_provider = provider_norm
    if provider_norm in {"openai", "local", "compatible", "openai-compatible", ""}:
        backend = _compatible_backend_from_config(cfg)
    if provider_norm == "openai" and backend == "unsloth":
        check_provider = "local"

    return selected_reasoning_effort_label(
        cfg.get("llm.model_reasoning"),
        check_provider,
        model,
        default_effort=str(cfg.get("llm.reasoning_effort") or "medium"),
        default_fast=bool(cfg.get("llm.reasoning_fast", False)),
        compatible_backend=backend,
    )
