"""Per-request authentication: API key header/bearer + session cookie fallback."""

from __future__ import annotations

import secrets
from typing import Any

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
