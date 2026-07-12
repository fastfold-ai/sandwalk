"""Cross-platform Sandwalk auth settings (API key + enable flag + session cookies)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import string
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SESSION_COOKIE = "sandwalk_session"
SESSION_MAX_AGE = 86400  # 24h
SESSION_REMEMBER_MAX_AGE = 2592000  # 30d
AUTH_EXEMPT_PATHS = frozenset(
    {
        "/v1/health",
        "/v1/auth/status",
        "/v1/auth/login",
        "/v1/auth/logout",
    }
)


class AuthSettingsError(ValueError):
    """Invalid auth configuration."""


@dataclass
class AuthSettings:
    api_key: str = ""
    auth_enabled: bool = False
    secret_key: str = ""

    @property
    def api_key_configured(self) -> bool:
        return bool(self.api_key.strip())


def settings_dir() -> Path:
    override = (os.environ.get("SANDWALK_HOME") or "").strip()
    if override:
        return Path(override).expanduser().resolve()

    path_override = (os.environ.get("SANDWALK_SETTINGS_PATH") or "").strip()
    if path_override:
        return Path(path_override).expanduser().resolve().parent

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Sandwalk"
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(appdata) / "Sandwalk"
    xdg = (os.environ.get("XDG_CONFIG_HOME") or "").strip()
    if xdg:
        return Path(xdg).expanduser() / "sandwalk"
    return Path.home() / ".config" / "sandwalk"


def settings_path() -> Path:
    path_override = (os.environ.get("SANDWALK_SETTINGS_PATH") or "").strip()
    if path_override:
        return Path(path_override).expanduser().resolve()
    return settings_dir() / "settings.json"


def generate_api_key() -> str:
    alphabet = string.ascii_letters + string.digits
    return "sk-sandwalk-" + "".join(secrets.choice(alphabet) for _ in range(24))


def generate_secret_key() -> str:
    return secrets.token_urlsafe(32)


def validate_api_key(key: str) -> str:
    value = (key or "").strip()
    if len(value) < 4:
        raise AuthSettingsError("API key must be at least 4 characters.")
    if any(ch.isspace() for ch in value):
        raise AuthSettingsError("API key must not contain whitespace.")
    if not all(32 <= ord(ch) < 127 for ch in value):
        raise AuthSettingsError("API key must be printable ASCII.")
    return value


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


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def create_session_token(
    *,
    secret_key: str,
    remember: bool = False,
    now: float | None = None,
) -> tuple[str, int]:
    max_age = SESSION_REMEMBER_MAX_AGE if remember else SESSION_MAX_AGE
    issued = int(now if now is not None else time.time())
    payload = {
        "iat": issued,
        "exp": issued + max_age,
        "remember": bool(remember),
        "v": 1,
    }
    body = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    sig = _b64url(
        hmac.new(secret_key.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
    )
    return f"{body}.{sig}", max_age


def verify_session_token(token: str, *, secret_key: str, now: float | None = None) -> bool:
    if not token or "." not in token or not secret_key:
        return False
    body, _, sig = token.partition(".")
    if not body or not sig:
        return False
    expected = _b64url(
        hmac.new(secret_key.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
    )
    if not hmac.compare_digest(sig, expected):
        return False
    try:
        payload = json.loads(_b64url_decode(body))
    except (ValueError, json.JSONDecodeError):
        return False
    exp = payload.get("exp")
    if not isinstance(exp, int):
        return False
    return exp >= int(now if now is not None else time.time())


def extract_bearer_or_header_key(headers: Any) -> str | None:
    authorization = ""
    x_api_key = ""
    try:
        authorization = headers.get("authorization", "") or ""
        x_api_key = headers.get("x-api-key", "") or ""
    except Exception:
        return None
    if x_api_key.strip():
        return x_api_key.strip()
    scheme, _, candidate = authorization.partition(" ")
    if scheme.lower() == "bearer" and candidate.strip():
        return candidate.strip()
    return None


def key_matches(candidate: str | None, expected: str | None) -> bool:
    if not candidate or not expected:
        return False
    try:
        return secrets.compare_digest(candidate, expected)
    except (TypeError, ValueError):
        return False


def request_is_authenticated(
    *,
    headers: Any,
    cookies: Any,
    api_key: str | None,
    secret_key: str,
    query_token: str | None = None,
) -> bool:
    if not api_key:
        return True
    header_key = extract_bearer_or_header_key(headers)
    if key_matches(header_key, api_key):
        return True
    if query_token and key_matches(query_token, api_key):
        return True
    cookie_val = ""
    try:
        cookie_val = cookies.get(SESSION_COOKIE, "") or ""
    except Exception:
        cookie_val = ""
    return verify_session_token(cookie_val, secret_key=secret_key)
