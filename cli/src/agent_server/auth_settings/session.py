"""HMAC-signed session cookie tokens."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from agent_server.auth_settings.paths import SESSION_MAX_AGE, SESSION_REMEMBER_MAX_AGE


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
