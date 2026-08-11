"""Per-model reasoning (effort, fast) persisted in ``llm.model_reasoning``."""

from __future__ import annotations

from agent.model_catalog.lookup import resolve_catalog_model_id
from agent.model_catalog.reasoning_support import normalize_reasoning_effort


def reasoning_settings_key(provider: str | None, model_id: str | None) -> str:
    """Stable per-model key: ``provider:model``."""
    prov = str(provider or "").strip().lower() or "openai"
    mid = resolve_catalog_model_id(model_id)
    return f"{prov}:{mid}"


def read_model_reasoning_store(raw: object) -> dict[str, dict[str, object]]:
    """Normalize ``llm.model_reasoning`` into a plain dict."""
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, object]] = {}
    for key, value in raw.items():
        k = str(key or "").strip()
        if not k or not isinstance(value, dict):
            continue
        out[k] = {
            "effort": normalize_reasoning_effort(
                str(value.get("effort") or "medium"),
                allow_none=False,
            ),
            "fast": bool(value.get("fast", False)),
        }
    return out


def get_model_reasoning(
    store: object,
    provider: str | None,
    model_id: str | None,
    *,
    default_effort: str = "medium",
    default_fast: bool = False,
) -> tuple[str, bool]:
    """Return ``(effort, fast)`` for a model from the per-model store."""
    key = reasoning_settings_key(provider, model_id)
    normalized = read_model_reasoning_store(store)
    entry = normalized.get(key)
    if not entry:
        return (
            normalize_reasoning_effort(default_effort, allow_none=False),
            bool(default_fast),
        )
    return (
        normalize_reasoning_effort(str(entry.get("effort") or default_effort), allow_none=False),
        bool(entry.get("fast", default_fast)),
    )


def upsert_model_reasoning(
    store: object,
    provider: str | None,
    model_id: str | None,
    *,
    effort: str | None = None,
    fast: bool | None = None,
) -> dict[str, dict[str, object]]:
    """Return an updated ``llm.model_reasoning`` map with one model patched."""
    normalized = read_model_reasoning_store(store)
    key = reasoning_settings_key(provider, model_id)
    current_effort, current_fast = get_model_reasoning(normalized, provider, model_id)
    next_effort = (
        normalize_reasoning_effort(effort, allow_none=False)
        if effort is not None
        else current_effort
    )
    next_fast = bool(fast) if fast is not None else current_fast
    normalized[key] = {"effort": next_effort, "fast": next_fast}
    return normalized
