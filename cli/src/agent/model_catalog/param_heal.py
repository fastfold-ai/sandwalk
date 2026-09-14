"""Persist and apply per-model request-parameter heals.

Providers reject different optional fields (temperature, reasoning.effort,
OpenRouter ``require_parameters``). Instead of enumerating every combo, we
learn from the first failure and reuse the working shape on later turns.
"""

from __future__ import annotations

import logging
from typing import Any

from agent.model_catalog.lookup import resolve_catalog_model_id

logger = logging.getLogger("agent.param_heal")

_HEAL_MARKERS = (
    "no endpoints found",
    "requested parameters",
    "unsupported parameter",
    "unsupported value",
    "unknown parameter",
    "does not support",
    "not a valid",
    "invalid effort",
    "effort: none",
    "effort none",
    "reasoning.effort",
    "reasoning_effort",
    "temperature",
)

_NON_HEAL_MARKERS = (
    "invalid api key",
    "incorrect api key",
    "unauthorized",
    "401",
    "403",
    "429",
    "rate limit",
    "quota",
    "insufficient",
    "billing",
    "context length",
    "context_length",
    "maximum context",
)


def param_heal_key(provider: str | None, model_id: str | None) -> str:
    prov = str(provider or "").strip().lower() or "openai"
    mid = resolve_catalog_model_id(model_id)
    return f"{prov}:{mid}"


def empty_heal() -> dict[str, Any]:
    return {
        "omit_temperature": False,
        "omit_reasoning": False,
        "omit_require_parameters": False,
        "effort_min": None,
    }


def read_param_heals(raw: object) -> dict[str, dict[str, Any]]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for key, value in raw.items():
        k = str(key or "").strip()
        if not k or not isinstance(value, dict):
            continue
        base = empty_heal()
        base["omit_temperature"] = bool(value.get("omit_temperature"))
        base["omit_reasoning"] = bool(value.get("omit_reasoning"))
        base["omit_require_parameters"] = bool(value.get("omit_require_parameters"))
        effort_min = value.get("effort_min")
        base["effort_min"] = str(effort_min).strip().lower() if effort_min else None
        out[k] = base
    return out


def get_param_heal(
    store: object, provider: str | None, model_id: str | None
) -> dict[str, Any]:
    key = param_heal_key(provider, model_id)
    return dict(read_param_heals(store).get(key) or empty_heal())


def _error_text(exc: BaseException) -> str:
    parts = [str(exc)]
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        parts.append(str(body))
    elif isinstance(body, str):
        parts.append(body)
    cause = getattr(exc, "__cause__", None) or getattr(exc, "__context__", None)
    if isinstance(cause, BaseException):
        parts.append(str(cause))
    return " ".join(" ".join(part.split()) for part in parts if part)


def is_param_healable_error(exc: BaseException) -> bool:
    text = _error_text(exc).lower()
    if any(marker in text for marker in _NON_HEAL_MARKERS):
        if "no endpoints found" not in text:
            return False
    return any(marker in text for marker in _HEAL_MARKERS)


def next_param_heal(current: dict[str, Any]) -> dict[str, Any] | None:
    """Advance one step on the heal ladder. ``None`` means already maxed."""
    nxt = dict(empty_heal())
    nxt.update(current)
    if not nxt["omit_temperature"]:
        nxt["omit_temperature"] = True
        return nxt
    if not nxt["omit_require_parameters"]:
        nxt["omit_require_parameters"] = True
        return nxt
    if nxt.get("effort_min") != "low":
        nxt["effort_min"] = "low"
        return nxt
    if not nxt["omit_reasoning"]:
        nxt["omit_reasoning"] = True
        return nxt
    return None


def apply_effort_floor(effort: str, heal: dict[str, Any]) -> str:
    floor = str(heal.get("effort_min") or "").strip().lower()
    if floor == "low" and effort in {"none", "minimal"}:
        return "low"
    return effort


def persist_param_heal(config: Any, provider: str | None, model_id: str | None, heal: dict[str, Any]) -> None:
    store = read_param_heals(config.get("llm.param_heals"))
    store[param_heal_key(provider, model_id)] = heal
    config.set("llm.param_heals", store)
    try:
        config.save()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to persist param heal: %s", exc)


def apply_param_heal_from_error(config: Any, exc: BaseException) -> bool:
    """Persist the next heal for the active model. True when a retry is useful."""
    if not is_param_healable_error(exc):
        return False
    provider = str(config.get("llm.provider") or "openai").strip().lower()
    model_id = str(config.get("llm.model") or "").strip()
    current = get_param_heal(config.get("llm.param_heals"), provider, model_id)
    nxt = next_param_heal(current)
    if nxt is None:
        return False
    persist_param_heal(config, provider, model_id, nxt)
    logger.warning(
        "Healed request params for %s:%s → %s",
        provider,
        model_id,
        nxt,
    )
    return True
