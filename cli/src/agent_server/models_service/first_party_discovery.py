"""Live model lists from OpenAI and Anthropic, so new families show up on release day.

The curated catalog in ``agent.model_catalog.data`` gives the well-known rows
good labels and descriptions. This module asks each provider's ``/v1/models``
for everything else and appends what the catalog does not already carry:

- OpenAI ``GET /v1/models`` returns ids only (plus ``created`` / ``owned_by``).
  We keep the chat-capable GPT families and drop dated snapshots, audio,
  realtime, image, transcription, search and embedding ids.
- Anthropic ``GET /v1/models`` returns ``display_name``, ``line``,
  ``max_input_tokens`` and a ``deprecated_at`` lifecycle, which we use for the
  label, grouping, context window and the default toggle.

Newer than the newest curated family (GPT-6+, or any current Claude line) is
enabled by default; older or deprecated ids are listed but start hidden, the
same opt-in pattern OpenRouter and Bedrock discovery use. Responses are cached
in-process for 15 minutes; a failed fetch is cached for one minute so a
provider outage cannot make the Models page slow.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from agent.config import Config
from agent.model_catalog import context_window_for_model, format_discovered_model_label
from agent_server.models import AgentModel
from agent_server.models_service.helpers import _reasoning_fields

logger = logging.getLogger("models_service")

_TTL_OK_S = 15 * 60
_TTL_ERR_S = 60
_TIMEOUT_S = 8.0

_OPENAI_URL = "https://api.openai.com/v1/models"
_ANTHROPIC_URL = "https://api.anthropic.com/v1/models"
_ANTHROPIC_VERSION = "2023-06-01"

# OpenAI chat families we surface; everything else on /v1/models is a
# specialised endpoint (audio, images, embeddings, moderation, ...).
_OPENAI_CHAT_PREFIXES = ("gpt-5", "gpt-6", "gpt-7", "o3", "o4")
_OPENAI_EXCLUDE = re.compile(
    r"(-\d{4}-\d{2}-\d{2}$)"            # dated snapshots
    r"|(-chat-latest$)"                 # chat.com alias of the same model
    r"|(realtime|audio|transcribe|tts|image|search-api|embedding|moderation|cyber|rosalind)"
)
# Discovered OpenAI ids at or above this family start enabled; older start hidden.
_OPENAI_ENABLED_PREFIXES = ("gpt-6", "gpt-7")


@dataclass
class DiscoveredModel:
    id: str
    label: str
    description: str
    context_window: int | None = None
    deprecated: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class _CacheEntry:
    at: float
    models: list[DiscoveredModel]
    error: str | None


_cache: dict[str, _CacheEntry] = {}
_cache_lock = threading.Lock()


def _cached(provider: str) -> _CacheEntry | None:
    with _cache_lock:
        entry = _cache.get(provider)
    if entry is None:
        return None
    ttl = _TTL_ERR_S if entry.error else _TTL_OK_S
    if time.monotonic() - entry.at > ttl:
        return None
    return entry


def _store(provider: str, models: list[DiscoveredModel], error: str | None) -> _CacheEntry:
    entry = _CacheEntry(at=time.monotonic(), models=models, error=error)
    with _cache_lock:
        _cache[provider] = entry
    return entry


def _reset_cache_for_tests() -> None:
    with _cache_lock:
        _cache.clear()


def _get_json(url: str, headers: dict[str, str], params: dict[str, Any] | None = None) -> Any:
    import httpx

    response = httpx.get(url, headers=headers, params=params, timeout=_TIMEOUT_S)
    response.raise_for_status()
    return response.json()


# -- OpenAI -----------------------------------------------------------------


def _openai_family_rank(model_id: str) -> tuple[float, str]:
    """Sort key: newest family first (gpt-6.1 > gpt-6 > gpt-5.6 ...)."""
    match = re.match(r"^(?:gpt-|o)(\d+(?:\.\d+)?)", model_id)
    version = float(match.group(1)) if match else 0.0
    return (-version, model_id)


def fetch_openai_models(api_key: str) -> list[DiscoveredModel]:
    payload = _get_json(_OPENAI_URL, {"Authorization": f"Bearer {api_key}"})
    rows = payload.get("data") if isinstance(payload, dict) else None
    ids: list[str] = []
    for row in rows or []:
        model_id = str((row or {}).get("id") or "").strip()
        if not model_id or not model_id.startswith(_OPENAI_CHAT_PREFIXES):
            continue
        if _OPENAI_EXCLUDE.search(model_id):
            continue
        ids.append(model_id)
    ids.sort(key=_openai_family_rank)
    return [
        DiscoveredModel(
            id=model_id,
            label=_openai_label(model_id),
            description="OpenAI (discovered)",
            context_window=context_window_for_model(model_id),
        )
        for model_id in ids
    ]


def _openai_default_enabled(model_id: str) -> bool:
    return model_id.startswith(_OPENAI_ENABLED_PREFIXES)


def _openai_label(model_id: str) -> str:
    """``gpt-6.1-sol`` → ``GPT-6.1 Sol``; ``o3-mini`` stays ``o3-mini``."""
    match = re.match(r"^gpt-(\d+(?:\.\d+)?)(?:-(.+))?$", model_id)
    if not match:
        return model_id
    version, rest = match.group(1), match.group(2) or ""
    suffix = " ".join(part.capitalize() for part in rest.split("-") if part)
    return f"GPT-{version}{(' ' + suffix) if suffix else ''}"


_CLAUDE_ID = re.compile(r"^claude-([a-z]+)-(\d+)(?:-(\d+))?")


def _claude_version(model_id: str) -> tuple[str, float] | None:
    match = _CLAUDE_ID.match(model_id)
    if not match:
        return None
    line, major, minor = match.group(1), match.group(2), match.group(3) or "0"
    return line, float(f"{major}.{minor}")


def _anthropic_default_enabled(model: DiscoveredModel, curated_ids: set[str]) -> bool:
    """On by default unless deprecated or older than the curated newest in its line."""
    if model.deprecated:
        return False
    parsed = _claude_version(model.id)
    if parsed is None:
        return True
    line, version = parsed
    newest = 0.0
    for known in curated_ids:
        other = _claude_version(known)
        if other and other[0] == line:
            newest = max(newest, other[1])
    return version >= newest


# -- Anthropic ----------------------------------------------------------------


def fetch_anthropic_models(api_key: str) -> list[DiscoveredModel]:
    headers = {"x-api-key": api_key, "anthropic-version": _ANTHROPIC_VERSION}
    out: list[DiscoveredModel] = []
    after: str | None = None
    for _ in range(5):  # pagination guard
        params: dict[str, Any] = {"limit": 100}
        if after:
            params["after_id"] = after
        payload = _get_json(_ANTHROPIC_URL, headers, params)
        rows = payload.get("data") if isinstance(payload, dict) else None
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            model_id = str(row.get("id") or "").strip()
            if not model_id:
                continue
            line = str(row.get("line") or "").strip()
            deprecated = bool(row.get("deprecated_at"))
            max_in = row.get("max_input_tokens")
            description = "Anthropic (discovered)"
            if line:
                description = f"Anthropic {line.capitalize()} line (discovered)"
            if deprecated:
                description += " · deprecated"
            out.append(
                DiscoveredModel(
                    id=model_id,
                    label=str(row.get("display_name") or "").strip()
                    or format_discovered_model_label(model_id),
                    description=description,
                    context_window=int(max_in) if isinstance(max_in, int) else None,
                    deprecated=deprecated,
                    extra={"line": line or None},
                )
            )
        if not (isinstance(payload, dict) and payload.get("has_more")):
            break
        after = str(payload.get("last_id") or "") or None
        if not after:
            break
    return out


# -- shared ---------------------------------------------------------------------


def _models_for(provider: str, api_key: str) -> _CacheEntry:
    cached = _cached(provider)
    if cached is not None:
        return cached
    try:
        if provider == "openai":
            models = fetch_openai_models(api_key)
        elif provider == "anthropic":
            models = fetch_anthropic_models(api_key)
        else:
            models = []
        return _store(provider, models, None)
    except Exception as exc:  # noqa: BLE001 — the static catalog still lists
        logger.info("Model discovery for %s failed: %s", provider, exc.__class__.__name__)
        return _store(provider, [], f"{exc.__class__.__name__}")


def _seed_hidden(cfg: Config, provider: str, fresh_hidden: list[str], fresh_seen: list[str]) -> None:
    """Hide ids on first sight (opt-in). A later user enable sticks."""
    key = f"llm.{provider}_seen_models"
    raw = cfg.get(key, [])
    seen = {str(v).strip() for v in raw} if isinstance(raw, list) else set()
    new_seen = [m for m in fresh_seen if m not in seen]
    if not new_seen:
        return
    hidden = set(cfg.hidden_models())
    hidden.update(m for m in fresh_hidden if m not in seen)
    seen.update(new_seen)
    cfg.set("llm.hidden_models", sorted(hidden))
    cfg.set(key, sorted(seen))
    try:
        cfg.save()
    except Exception:  # noqa: BLE001 — listing must still return models
        pass


def _cloud_key(cfg: Config, provider: str) -> str | None:
    """The cloud API key for the provider, regardless of the active profile.

    ``cfg.llm_api_key("openai")`` follows the active OpenAI profile, which is a
    local server (Llama, Ollama) for many users; discovery wants the real
    OpenAI key the Models page stores, same as the Connected badge does.
    """
    import os

    if provider == "openai":
        return cfg._normalized_secret(cfg.get("llm.openai_api_key")) or cfg._normalized_secret(
            os.environ.get("OPENAI_API_KEY")
        )
    if provider == "anthropic":
        return (
            cfg._normalized_secret(cfg.get("llm.anthropic_api_key"))
            or cfg._normalized_secret(cfg.get("llm.api_key"))
            or cfg._normalized_secret(os.environ.get("ANTHROPIC_API_KEY"))
        )
    return cfg.llm_api_key(provider)


def first_party_discovered_items(
    cfg: Config, hidden: set[str], known_ids: set[str], *, enabled_only: bool
) -> list[AgentModel]:
    """OpenAI + Anthropic models not already in the curated catalog."""
    items: list[AgentModel] = []
    for provider in ("openai", "anthropic"):
        api_key = _cloud_key(cfg, provider)
        if not api_key:
            continue
        entry = _models_for(provider, api_key)
        curated = set(known_ids)
        fresh = [m for m in entry.models if m.id not in known_ids]
        if not fresh:
            continue
        if provider == "openai":
            start_hidden = [m.id for m in fresh if not _openai_default_enabled(m.id)]
        else:
            start_hidden = [m.id for m in fresh if not _anthropic_default_enabled(m, curated)]
        _seed_hidden(cfg, provider, start_hidden, [m.id for m in fresh])
        hidden.clear()
        hidden.update(cfg.hidden_models())
        health = f"discovery failed ({entry.error})" if entry.error else None
        for model in fresh:
            known_ids.add(model.id)
            enabled = not cfg.is_model_hidden(model.id, provider)
            if enabled_only and not enabled:
                continue
            items.append(
                AgentModel(
                    id=model.id,
                    label=model.label,
                    description=model.description,
                    provider=provider,
                    source="cloud",
                    profile_id=None,
                    backend=None,
                    enabled=enabled,
                    health=health,
                    context_window=model.context_window or context_window_for_model(model.id),
                    **_reasoning_fields(cfg, provider, model.id),
                )
            )
    return items


__all__ = [
    "DiscoveredModel",
    "fetch_anthropic_models",
    "fetch_openai_models",
    "first_party_discovered_items",
]
