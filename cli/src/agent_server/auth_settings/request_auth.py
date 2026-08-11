"""Per-request authentication: API key header/bearer + session cookie fallback."""

from __future__ import annotations

import secrets
from typing import Any, Iterable

from agent_server.auth_settings.paths import SESSION_COOKIE
from agent_server.auth_settings.session import verify_session_token


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


def normalize_api_keys(*keys: str | None) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for key in keys:
        trimmed = (key or "").strip()
        if not trimmed or trimmed in seen:
            continue
        seen.add(trimmed)
        out.append(trimmed)
    return out


def any_key_matches(candidate: str | None, keys: Iterable[str | None]) -> bool:
    return any(key_matches(candidate, key) for key in keys)


def request_is_authenticated(
    *,
    headers: Any,
    cookies: Any,
    api_key: str | None = None,
    secret_key: str,
    query_token: str | None = None,
    api_keys: Iterable[str | None] | None = None,
) -> bool:
    """True when bearer/header/query matches any accepted key, or session cookie is valid.

    ``api_keys`` accepts both the CLI/env runtime key and the persisted settings
    key — they can diverge when ``serve`` was started with ``--api-key``.
    """
    keys = normalize_api_keys(*(api_keys or ()), api_key)
    if not keys:
        return True
    header_key = extract_bearer_or_header_key(headers)
    if any_key_matches(header_key, keys):
        return True
    if query_token and any_key_matches(query_token, keys):
        return True
    cookie_val = ""
    try:
        cookie_val = cookies.get(SESSION_COOKIE, "") or ""
    except Exception:
        cookie_val = ""
    return verify_session_token(cookie_val, secret_key=secret_key)
