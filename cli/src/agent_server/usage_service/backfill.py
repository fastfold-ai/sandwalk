"""Best-effort backfill of usage_runs from events + CLI trajectory JSONL."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from agent_server.models.usage import UsageBackfillResponse
from agent_server.store import AgentStore
from agent_server.store.usage import normalize_surface
from agent_server.usage_service.parse import (
    canonicalize_usage_model,
    day_key_from_epoch,
    day_key_from_timestamp,
    parse_usage_tokens,
)

logger = logging.getLogger("agent_server.usage")

_BACKFILL_META_KEY = "usage_backfill_v1"
_MODEL_REPAIR_META_KEY = "usage_model_repair_v1"
_PROVIDER_REPAIR_META_KEY = "usage_provider_repair_v1"
_ALIAS_REPAIR_META_KEY = "usage_alias_repair_v1"

# Bench / chat titles often end with "· model-id".
_TITLE_MODEL_RE = re.compile(r"·\s*([^\s·][\w./:+\-]+)\s*$")


def _payload_dict(raw: object) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def _surface_from_row(row: dict[str, Any]) -> str:
    surface = normalize_surface(row.get("client_surface"))
    if surface != "unknown":
        return surface
    if str(row.get("source") or "").strip().lower() == "slack":
        return "slack"
    return "unknown"


def _model_from_usage_meta(meta: dict[str, Any]) -> str | None:
    usage = meta.get("usage_data")
    if isinstance(usage, dict):
        models = usage.get("sdk_models")
        if isinstance(models, str) and models.strip():
            return models.strip()
        if isinstance(models, (list, tuple, set)):
            cleaned = [str(m).strip() for m in models if str(m).strip()]
            if cleaned:
                return cleaned[0]
    model = str(meta.get("model") or "").strip()
    return model or None


def _model_from_title(title: object | None) -> str | None:
    match = _TITLE_MODEL_RE.search(str(title or ""))
    if not match:
        return None
    return match.group(1).strip() or None


def _trajectory_paths() -> list[Path]:
    try:
        from agent.trajectory import Trajectory

        root = Trajectory.sessions_dir()
    except Exception:
        return []
    if not root.is_dir():
        return []
    return sorted(
        path
        for path in root.glob("*.jsonl")
        if path.is_file() and not path.name.endswith(".trace.jsonl")
    )


def _trajectory_model_map() -> dict[str, str]:
    """session_id → model from CLI trajectory meta (best-effort)."""
    out: dict[str, str] = {}
    for path in _trajectory_paths():
        try:
            with path.open("r", encoding="utf-8") as handle:
                first = handle.readline()
            if not first.strip():
                continue
            meta = json.loads(first)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(meta, dict) or meta.get("type") != "meta":
            continue
        session_id = str(meta.get("session_id") or path.stem).strip()
        model_id = _model_from_usage_meta(meta)
        if session_id and model_id:
            out[session_id] = model_id
            # Prefix matches (short traj stems) — only if unique later.
            if path.stem and path.stem != session_id:
                out.setdefault(path.stem, model_id)
    return out


def _session_title_model_map(store: AgentStore) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        sessions = store.list_sessions()
    except Exception:
        return out
    for session in sessions:
        model_id = _model_from_title(getattr(session, "title", None))
        sid = str(getattr(session, "id", "") or "").strip()
        if sid and model_id:
            out[sid] = model_id
    return out


def _resolve_model(
    session_id: str,
    *,
    payload_model: str | None,
    traj_models: dict[str, str],
    title_models: dict[str, str],
) -> str | None:
    if payload_model:
        return payload_model
    if session_id in traj_models:
        return traj_models[session_id]
    if session_id in title_models:
        return title_models[session_id]
    # Short traj stems / prefixes.
    for key, model_id in traj_models.items():
        if len(key) >= 8 and (
            session_id.startswith(key) or key.startswith(session_id[:8])
        ):
            return model_id
    return None


def backfill_from_events(store: AgentStore) -> int:
    """Upsert last cumulative run.usage per run_id. Returns rows touched."""
    traj_models = _trajectory_model_map()
    title_models = _session_title_model_map(store)
    latest: dict[str, dict[str, Any]] = {}
    for row in store.list_run_usage_events():
        run_id = str(row.get("run_id") or "").strip()
        session_id = str(row.get("session_id") or "").strip()
        if not run_id or not session_id:
            continue
        payload = _payload_dict(row.get("payload"))
        tokens = parse_usage_tokens(payload)
        if (
            tokens["input_tokens"]
            + tokens["output_tokens"]
            + tokens["cache_read_tokens"]
            + tokens["cache_creation_tokens"]
            <= 0
        ):
            continue
        payload_model = (
            str(payload.get("model_id") or payload.get("modelId") or "").strip() or None
        )
        payload_provider = (
            str(payload.get("provider") or "").strip().lower() or None
        )
        model_id = _resolve_model(
            session_id,
            payload_model=payload_model,
            traj_models=traj_models,
            title_models=title_models,
        )
        if model_id:
            provider, model_id = canonicalize_usage_model(model_id, payload_provider)
        else:
            provider = payload_provider or "unknown"
        latest[run_id] = {
            "run_id": run_id,
            "session_id": session_id,
            "day": day_key_from_timestamp(row.get("timestamp")),
            "surface": _surface_from_row(row),
            "model_id": None if model_id == "unknown" else model_id,
            "provider": None if provider == "unknown" else provider,
            **tokens,
        }
    for item in latest.values():
        store.upsert_usage_run(**item)
    return len(latest)


def backfill_from_trajectories(store: AgentStore) -> int:
    """Import CLI trajectory usage_data when the session has no ledger rows yet."""
    covered = {
        str(row.get("session_id") or "").strip()
        for row in store.list_usage_runs()
        if str(row.get("session_id") or "").strip()
    }
    upserted = 0
    for path in _trajectory_paths():
        try:
            with path.open("r", encoding="utf-8") as handle:
                first = handle.readline()
            if not first.strip():
                continue
            meta = json.loads(first)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(meta, dict) or meta.get("type") != "meta":
            continue
        session_id = str(meta.get("session_id") or path.stem).strip()
        if not session_id or session_id in covered:
            continue
        usage = meta.get("usage_data")
        if not isinstance(usage, dict) or not usage:
            continue
        input_tokens = int(usage.get("sdk_input_tokens") or 0)
        output_tokens = int(usage.get("sdk_output_tokens") or 0)
        cache_read = int(usage.get("sdk_cache_read_tokens") or 0)
        cache_creation = int(usage.get("sdk_cache_creation_tokens") or 0)
        if input_tokens + output_tokens + cache_read + cache_creation <= 0:
            continue
        model_id = _model_from_usage_meta(meta)
        provider = str(meta.get("provider") or "").strip().lower() or None
        if model_id:
            provider, model_id = canonicalize_usage_model(model_id, provider)
            if model_id == "unknown":
                model_id = None
            if provider == "unknown":
                provider = None
        day = day_key_from_epoch(meta.get("updated_at") or meta.get("created_at"))
        run_id = f"traj:{session_id}"
        store.upsert_usage_run(
            run_id=run_id,
            session_id=session_id,
            day=day,
            surface="cli",
            model_id=model_id,
            provider=provider,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read,
            cache_creation_tokens=cache_creation,
        )
        covered.add(session_id)
        upserted += 1
    return upserted


def repair_missing_models(store: AgentStore) -> int:
    """Fill model_id on existing ledger rows from traj meta / session titles."""
    traj_models = _trajectory_model_map()
    title_models = _session_title_model_map(store)
    repaired = 0
    for row in store.list_usage_runs():
        current = str(row.get("model_id") or "").strip()
        if current and current != "unknown":
            continue
        session_id = str(row.get("session_id") or "").strip()
        if not session_id:
            continue
        model_id = _resolve_model(
            session_id,
            payload_model=None,
            traj_models=traj_models,
            title_models=title_models,
        )
        if not model_id:
            continue
        provider, model_id = canonicalize_usage_model(model_id, None)
        store.upsert_usage_run(
            run_id=str(row["run_id"]),
            session_id=session_id,
            day=str(row["day"]),
            surface=str(row.get("surface") or "unknown"),
            model_id=None if model_id == "unknown" else model_id,
            provider=None if provider == "unknown" else provider,
            input_tokens=int(row.get("input_tokens") or 0),
            output_tokens=int(row.get("output_tokens") or 0),
            cache_read_tokens=int(row.get("cache_read_tokens") or 0),
            cache_creation_tokens=int(row.get("cache_creation_tokens") or 0),
        )
        repaired += 1
    return repaired


def repair_missing_providers(store: AgentStore) -> int:
    """Fill provider on ledger rows from catalog/heuristic when missing."""
    repaired = 0
    for row in store.list_usage_runs():
        current = str(row.get("provider") or "").strip().lower()
        if current and current != "unknown":
            continue
        model_id = str(row.get("model_id") or "").strip()
        if not model_id or model_id == "unknown":
            continue
        provider, canon_model = canonicalize_usage_model(model_id, None)
        if provider == "unknown":
            continue
        store.upsert_usage_run(
            run_id=str(row["run_id"]),
            session_id=str(row["session_id"]),
            day=str(row["day"]),
            surface=str(row.get("surface") or "unknown"),
            model_id=canon_model,
            provider=provider,
            input_tokens=int(row.get("input_tokens") or 0),
            output_tokens=int(row.get("output_tokens") or 0),
            cache_read_tokens=int(row.get("cache_read_tokens") or 0),
            cache_creation_tokens=int(row.get("cache_creation_tokens") or 0),
        )
        repaired += 1
    return repaired


def repair_model_aliases(store: AgentStore) -> int:
    """Rewrite bench aliases / provider paths to registered model ids."""
    repaired = 0
    for row in store.list_usage_runs():
        current_model = str(row.get("model_id") or "").strip()
        if not current_model or current_model == "unknown":
            continue
        current_provider = str(row.get("provider") or "").strip().lower()
        provider, model_id = canonicalize_usage_model(
            current_model, current_provider or None
        )
        if model_id == "unknown":
            continue
        next_provider = "" if provider == "unknown" else provider
        if current_model == model_id and current_provider == next_provider:
            continue
        store.upsert_usage_run(
            run_id=str(row["run_id"]),
            session_id=str(row["session_id"]),
            day=str(row["day"]),
            surface=str(row.get("surface") or "unknown"),
            model_id=model_id,
            provider=next_provider or None,
            input_tokens=int(row.get("input_tokens") or 0),
            output_tokens=int(row.get("output_tokens") or 0),
            cache_read_tokens=int(row.get("cache_read_tokens") or 0),
            cache_creation_tokens=int(row.get("cache_creation_tokens") or 0),
        )
        repaired += 1
    return repaired


def run_backfill(store: AgentStore, *, force: bool = False) -> UsageBackfillResponse:
    if not force and store.get_usage_meta(_BACKFILL_META_KEY) == "done":
        return UsageBackfillResponse(ok=True, runs_upserted=0)
    from_events = backfill_from_events(store)
    from_traj = backfill_from_trajectories(store)
    repaired = repair_missing_models(store)
    providers = repair_missing_providers(store)
    aliases = repair_model_aliases(store)
    store.set_usage_meta(_BACKFILL_META_KEY, "done")
    store.set_usage_meta(_MODEL_REPAIR_META_KEY, "done")
    store.set_usage_meta(_PROVIDER_REPAIR_META_KEY, "done")
    store.set_usage_meta(_ALIAS_REPAIR_META_KEY, "done")
    logger.info(
        "Usage backfill: events=%s trajectories=%s models_repaired=%s "
        "providers_repaired=%s aliases_repaired=%s",
        from_events,
        from_traj,
        repaired,
        providers,
        aliases,
    )
    return UsageBackfillResponse(
        ok=True,
        runs_upserted=from_events + from_traj,
        from_events=from_events,
        from_trajectories=from_traj,
    )


def ensure_backfill(store: AgentStore) -> bool:
    """Auto-run once when ledger is empty or backfill flag missing."""
    ran = False
    if store.get_usage_meta(_BACKFILL_META_KEY) != "done":
        run_backfill(store, force=True)
        ran = True
    elif store.get_usage_meta(_MODEL_REPAIR_META_KEY) != "done":
        repaired = repair_missing_models(store)
        store.set_usage_meta(_MODEL_REPAIR_META_KEY, "done")
        logger.info("Usage model repair: rows=%s", repaired)
        ran = repaired > 0
    if store.get_usage_meta(_PROVIDER_REPAIR_META_KEY) != "done":
        providers = repair_missing_providers(store)
        store.set_usage_meta(_PROVIDER_REPAIR_META_KEY, "done")
        logger.info("Usage provider repair: rows=%s", providers)
        ran = ran or providers > 0
    if store.get_usage_meta(_ALIAS_REPAIR_META_KEY) != "done":
        aliases = repair_model_aliases(store)
        store.set_usage_meta(_ALIAS_REPAIR_META_KEY, "done")
        logger.info("Usage alias repair: rows=%s", aliases)
        ran = ran or aliases > 0
    return ran
