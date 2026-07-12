"""Unit tests for Sandwalk auth settings helpers."""

from __future__ import annotations

from pathlib import Path

from agent_server.auth_settings import (
    AuthSettings,
    create_session_token,
    generate_api_key,
    load_settings,
    save_settings,
    validate_api_key,
    verify_session_token,
)


def test_settings_roundtrip(tmp_path: Path, monkeypatch):
    path = tmp_path / "settings.json"
    monkeypatch.setenv("SANDWALK_SETTINGS_PATH", str(path))
    settings = AuthSettings(
        api_key="sk-sandwalk-testkey123456789012",
        auth_enabled=True,
        secret_key="secret",
    )
    save_settings(settings)
    loaded = load_settings()
    assert loaded.api_key == settings.api_key
    assert loaded.auth_enabled is True
    assert loaded.secret_key == "secret"


def test_validate_and_generate_key():
    key = generate_api_key()
    assert key.startswith("sk-sandwalk-")
    assert validate_api_key(key) == key


def test_session_token_roundtrip():
    token, max_age = create_session_token(secret_key="abc", remember=True)
    assert max_age == 2592000
    assert verify_session_token(token, secret_key="abc")
    assert not verify_session_token(token, secret_key="other")
    assert not verify_session_token("bad", secret_key="abc")
