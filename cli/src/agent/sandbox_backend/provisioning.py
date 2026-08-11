"""Backend selection, pip package parsing, sandbox naming, and Modal auth."""

from __future__ import annotations

import hashlib
import os
import re
import threading
from typing import Any

_SEED_LOCKS: dict[str, threading.Lock] = {}
_SEED_LOCKS_GUARD = threading.Lock()

_DEFAULT_PIP = (
    "pandas",
    "numpy",
    "matplotlib",
    "scipy",
    "pillow",
)


def _seed_lock_for(session_id: str | None) -> threading.Lock:
    key = (session_id or "default").strip() or "default"
    with _SEED_LOCKS_GUARD:
        lock = _SEED_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _SEED_LOCKS[key] = lock
        return lock


def sandbox_backend_from_config(config: Any) -> str:
    raw = str(getattr(config, "get", lambda _k, _d=None: "builtin")("sandbox.backend", "builtin") or "builtin")
    value = raw.strip().lower()
    return value if value in {"builtin", "modal"} else "builtin"


def parse_pip_packages(raw: Any) -> list[str]:
    if raw is None:
        return list(_DEFAULT_PIP)
    if isinstance(raw, (list, tuple)):
        items = [str(x).strip() for x in raw]
    else:
        text = str(raw).strip()
        if not text:
            return list(_DEFAULT_PIP)
        items = [part.strip() for part in text.replace(";", ",").split(",")]
    return [item for item in items if item]


def _safe_sandbox_name(session_id: str | None) -> str:
    base = (session_id or "default").strip() or "default"
    digest = hashlib.sha256(base.encode("utf-8")).hexdigest()[:14]
    # Modal sandbox names: alphanumeric + hyphen.
    slug = re.sub(r"[^a-zA-Z0-9-]", "-", base.lower())[:24].strip("-") or "session"
    return f"sandwalk-{slug}-{digest}"


def _ensure_modal_tokens(config: Any) -> None:
    from agent.config import sync_process_env_from_config

    sync_process_env_from_config(
        config,
        only_missing=False,
        config_keys=["compute.modal_token_id", "compute.modal_token_secret"],
    )
    token_id = (os.environ.get("MODAL_TOKEN_ID") or "").strip()
    token_secret = (os.environ.get("MODAL_TOKEN_SECRET") or "").strip()
    if not token_id or not token_secret:
        raise RuntimeError(
            "Modal sandbox requires compute.modal_token_id and "
            "compute.modal_token_secret (Integrations → Modal)."
        )
