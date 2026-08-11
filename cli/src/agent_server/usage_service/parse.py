"""Shared token / surface / day helpers for usage ledger."""

from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from agent_server.store.usage import normalize_surface
from agent_server.store.util import utc_now

# Fallback when pack YAML isn't available (bench short names → registered ids).
_BUILTIN_MODEL_ALIASES: dict[str, str] = {
    "luna-pro": "openai/gpt-5.6-luna-pro",
    "deepseek-pro": "deepseek/deepseek-v4-pro",
    "deepseek-flash": "deepseek/deepseek-v4-flash-0731",
    "qwen-max": "qwen/qwen3.7-max",
    "muse-spark": "meta/muse-spark-1.2",
    "kimi-k3": "moonshotai/kimi-k3",
}

_PATH_PROVIDER_ALIASES: dict[str, str] = {
    "moonshotai": "moonshot",
    "x-ai": "xai",
    "google": "google",
    "meta": "openrouter",
    "meta-llama": "openrouter",
}


def token_int(payload: dict[str, Any] | None, *keys: str) -> int:
    if not isinstance(payload, dict):
        return 0
    for key in keys:
        if key not in payload or payload[key] is None:
            continue
        try:
            return max(0, int(payload[key]))
        except (TypeError, ValueError):
            continue
    return 0


def parse_usage_tokens(payload: dict[str, Any] | None) -> dict[str, int]:
    return {
        "input_tokens": token_int(payload, "input_tokens", "inputTokens"),
        "output_tokens": token_int(payload, "output_tokens", "outputTokens"),
        "cache_read_tokens": token_int(
            payload,
            "cache_read_tokens",
            "cache_read_input_tokens",
            "cacheReadInputTokens",
            "cacheReadTokens",
        ),
        "cache_creation_tokens": token_int(
            payload,
            "cache_creation_tokens",
            "cache_creation_input_tokens",
            "cacheCreationInputTokens",
            "cacheCreationTokens",
        ),
    }


def day_key_from_timestamp(value: object | None) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    raw = str(value or "").strip()
    if not raw:
        return utc_now().date().isoformat()
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
            return raw[:10]
        return utc_now().date().isoformat()


def day_key_from_epoch(value: object | None) -> str:
    try:
        ts = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return utc_now().date().isoformat()
    if ts <= 0:
        return utc_now().date().isoformat()
    return datetime.fromtimestamp(ts).date().isoformat()


def active_model_id() -> str | None:
    try:
        from agent_server.settings_service import SettingsService

        model = str(SettingsService.get().model or "").strip()
        return model or None
    except Exception:
        return None


def active_provider() -> str | None:
    try:
        from agent_server.settings_service import SettingsService

        provider = str(SettingsService.get().provider or "").strip().lower()
        return provider or None
    except Exception:
        return None


def infer_provider(model_id: str | None, provider: str | None = None) -> str:
    """Prefer an explicit provider; else catalog/heuristic from model id."""
    explicit = str(provider or "").strip().lower()
    if explicit and explicit != "unknown":
        return explicit
    try:
        from agent.model_catalog import catalog_provider_for_model

        inferred = catalog_provider_for_model(model_id)
    except Exception:
        inferred = None
    value = str(inferred or "").strip().lower()
    return value or "unknown"


@lru_cache(maxsize=1)
def _bench_model_aliases() -> dict[str, str]:
    """Load short bench aliases from pack YAML ``models:`` maps."""
    out = dict(_BUILTIN_MODEL_ALIASES)
    try:
        import yaml
    except Exception:
        return out
    root = Path(__file__).resolve().parents[3] / "configs" / "benchmarks"
    if not root.is_dir():
        return out
    for path in sorted(root.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue
        if not isinstance(data, dict):
            continue
        models = data.get("models")
        if not isinstance(models, dict):
            continue
        for alias, target in models.items():
            key = str(alias or "").strip().lower()
            value = str(target or "").strip()
            if key and value:
                out[key] = value
    return out


def canonicalize_usage_model(
    model_id: str | None,
    provider: str | None = None,
) -> tuple[str, str]:
    """Map bench aliases / ``provider/model`` paths to registered model ids.

    Returns ``(provider, model_id)``. Unknown / empty models become
    ``("unknown", "unknown")``.
    """
    raw = str(model_id or "").strip()
    if not raw or raw.lower() in {"unknown", "other", "none"}:
        return "unknown", "unknown"

    aliases = _bench_model_aliases()
    mapped = aliases.get(raw.lower())
    if mapped:
        raw = mapped

    path_provider: str | None = None
    if "/" in raw:
        left, right = raw.split("/", 1)
        left = left.strip().lower()
        right = right.strip()
        if left and right:
            path_provider = _PATH_PROVIDER_ALIASES.get(left, left)
            raw = right

    explicit = str(provider or "").strip().lower()
    if explicit in {"", "unknown"}:
        explicit = ""
    # Catalog/heuristic on the bare id wins over path org when known
    # (e.g. deepseek/deepseek-v4-flash-0731 → qwen).
    inferred = infer_provider(raw, None)
    if inferred != "unknown":
        return inferred, raw
    if explicit:
        return explicit, raw
    if path_provider:
        return path_provider, raw
    return "unknown", raw


def surface_for_session(session: object | None) -> str:
    if session is None:
        return "unknown"
    surface = getattr(session, "client_surface", None)
    if surface:
        return normalize_surface(surface)
    source = str(getattr(session, "source", None) or "").strip().lower()
    if source == "slack":
        return "slack"
    return "unknown"


def resolve_client_surface(
    *,
    body: str | None = None,
    header: str | None = None,
    source: str | None = None,
) -> str | None:
    if str(source or "").strip().lower() == "slack":
        return "slack"
    for raw in (body, header):
        value = str(raw or "").strip().lower()
        if value in {"cli", "ui", "slack", "unknown"}:
            return value
    return None
