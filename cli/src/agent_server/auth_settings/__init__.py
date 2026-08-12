"""Cross-platform Sandwalk auth settings (API key + enable flag + session cookies).

Split package — re-exports the public surface previously defined in
``agent_server/auth_settings.py`` so existing imports keep working.
"""

from __future__ import annotations

from agent_server.auth_settings.errors import AuthSettingsError
from agent_server.auth_settings.keys import generate_api_key, generate_secret_key, validate_api_key
from agent_server.auth_settings.paths import (
    AUTH_EXEMPT_PATHS,
    SESSION_COOKIE,
    SESSION_MAX_AGE,
    SESSION_REMEMBER_MAX_AGE,
    settings_dir,
    settings_path,
)
from agent_server.auth_settings.persistence import (
    AuthSettings,
    ensure_api_key,
    load_settings,
    resolve_effective_api_key,
    save_settings,
)
from agent_server.auth_settings.request_auth import (
    any_key_matches,
    extract_bearer_or_header_key,
    key_matches,
    normalize_api_keys,
    request_is_authenticated,
)
from agent_server.auth_settings.session import create_session_token, verify_session_token

__all__ = [
    "SESSION_COOKIE",
    "SESSION_MAX_AGE",
    "SESSION_REMEMBER_MAX_AGE",
    "AUTH_EXEMPT_PATHS",
    "AuthSettingsError",
    "AuthSettings",
    "settings_dir",
    "settings_path",
    "generate_api_key",
    "generate_secret_key",
    "validate_api_key",
    "load_settings",
    "save_settings",
    "ensure_api_key",
    "resolve_effective_api_key",
    "create_session_token",
    "verify_session_token",
    "extract_bearer_or_header_key",
    "key_matches",
    "normalize_api_keys",
    "any_key_matches",
    "request_is_authenticated",
]
