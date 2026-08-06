"""Apply reasoning-effort/fast updates, mirroring onto legacy globals."""

from __future__ import annotations

from agent.config import Config
from agent.model_catalog import (
    get_model_reasoning,
    model_supports_reasoning_fast,
    upsert_model_reasoning,
)
from agent_server.models import UpdateRuntimeSettingsRequest


def apply_reasoning_update(config: Config, payload: UpdateRuntimeSettingsRequest) -> None:
    if payload.reasoning_effort is None and payload.reasoning_fast is None:
        return
    target_provider = str(
        payload.provider if payload.provider is not None else (config.get("llm.provider") or "openai")
    ).strip().lower()
    target_model = str(
        payload.model if payload.model is not None else (config.get("llm.model") or "")
    ).strip()
    fast = payload.reasoning_fast
    if fast and not model_supports_reasoning_fast(target_provider, target_model):
        fast = False
    store = upsert_model_reasoning(
        config.get("llm.model_reasoning"),
        target_provider,
        target_model,
        effort=payload.reasoning_effort,
        fast=fast,
    )
    config.set("llm.model_reasoning", store)
    effort, fast = get_model_reasoning(store, target_provider, target_model)
    # Mirror onto legacy globals when updating the active (or about-to-be) model.
    next_provider = str(
        payload.provider if payload.provider is not None else (config.get("llm.provider") or "openai")
    ).strip().lower()
    next_model = str(
        payload.model if payload.model is not None else (config.get("llm.model") or "")
    ).strip()
    if target_provider == next_provider and target_model == next_model:
        config.set("llm.reasoning_effort", effort)
        config.set("llm.reasoning_fast", fast)
