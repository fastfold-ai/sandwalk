"""API key / secret key generation and validation."""

from __future__ import annotations

import secrets
import string

from agent_server.auth_settings.errors import AuthSettingsError


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
