"""Load/save the persisted ``AuthSettings`` (API key + enable flag + secret key)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_server.auth_settings.keys import generate_api_key, generate_secret_key
from agent_server.auth_settings.paths import settings_path


@dataclass
class AuthSettings:
    api_key: str = ""
    auth_enabled: bool = False
    secret_key: str = ""

    @property
    def api_key_configured(self) -> bool:
        return bool(self.api_key.strip())


def _default_settings() -> AuthSettings:
    return AuthSettings(
        api_key="",
        auth_enabled=False,
        secret_key=generate_secret_key(),
    )


def load_settings(path: Path | None = None, *, create_if_missing: bool = True) -> AuthSettings:
    file_path = path or settings_path()
    if not file_path.is_file():
        settings = _default_settings()
        if create_if_missing:
            save_settings(settings, path=file_path)
        return settings
    try:
        raw = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        settings = _default_settings()
        if create_if_missing:
            save_settings(settings, path=file_path)
        return settings
    auth = raw.get("auth") if isinstance(raw, dict) else {}
    if not isinstance(auth, dict):
        auth = {}
    secret = str(auth.get("secret_key") or "").strip() or generate_secret_key()
    return AuthSettings(
        api_key=str(auth.get("api_key") or "").strip(),
        auth_enabled=bool(auth.get("auth_enabled", False)),
        secret_key=secret,
    )


def save_settings(settings: AuthSettings, path: Path | None = None) -> Path:
    file_path = path or settings_path()
    file_path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, Any] = {}
    if file_path.is_file():
        try:
            existing = json.loads(file_path.read_text(encoding="utf-8"))
            if not isinstance(existing, dict):
                existing = {}
        except (OSError, json.JSONDecodeError):
            existing = {}
    existing["auth"] = {
        "api_key": settings.api_key,
        "auth_enabled": settings.auth_enabled,
        "secret_key": settings.secret_key or generate_secret_key(),
    }
    tmp = file_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    tmp.replace(file_path)
    return file_path


def ensure_api_key(settings: AuthSettings | None = None) -> AuthSettings:
    current = settings or load_settings()
    changed = False
    if not current.secret_key:
        current.secret_key = generate_secret_key()
        changed = True
    if not current.api_key:
        current.api_key = generate_api_key()
        changed = True
    if changed:
        save_settings(current)
    return current


def resolve_effective_api_key(
    *,
    cli_api_key: str | None = None,
    settings: AuthSettings | None = None,
) -> str | None:
    """CLI/env override wins; otherwise use persisted key when auth_enabled."""
    override = (cli_api_key or "").strip() or None
    if override:
        return override
    current = settings or load_settings()
    if current.auth_enabled and current.api_key:
        return current.api_key
    return None
