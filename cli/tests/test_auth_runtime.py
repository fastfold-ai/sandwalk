"""Tests for CLI auth → running server / menubar apply helpers."""

from __future__ import annotations

from pathlib import Path

from cli.auth_runtime import (
    apply_saved_auth_to_runtime,
    try_hot_reload_auth,
    try_menubar_restart,
)


def test_hot_reload_success(monkeypatch):
    calls: list[str] = []

    def fake_http(url: str, **kwargs):
        calls.append(url)
        return 200, {"ok": True, "authEnabled": True}

    monkeypatch.setattr("cli.auth_runtime._http_json", fake_http)
    monkeypatch.setattr(
        "cli.auth_runtime._candidate_api_bases",
        lambda _control: ["http://127.0.0.1:8787"],
    )
    result = try_hot_reload_auth()
    assert result is not None
    assert result.ok
    assert result.method == "hot-reload"
    assert calls == ["http://127.0.0.1:8787/v1/auth/reload"]


def test_menubar_restart_uses_control_token(monkeypatch):
    control = {
        "host": "127.0.0.1",
        "port": 18787,
        "token": "unit-token",
        "api_base": "http://127.0.0.1:8787",
    }
    seen: dict[str, object] = {}

    def fake_http(url: str, **kwargs):
        seen["url"] = url
        seen["headers"] = kwargs.get("headers")
        return 200, {"state": "running"}

    monkeypatch.setattr("cli.auth_runtime._http_json", fake_http)
    result = try_menubar_restart(control)
    assert result is not None
    assert result.ok
    assert result.method == "menubar-restart"
    assert seen["url"] == "http://127.0.0.1:18787/v1/control/restart"
    headers = seen["headers"]
    assert isinstance(headers, dict)
    assert headers["authorization"] == "Bearer unit-token"


def test_apply_falls_back_to_menubar_when_reload_missing(monkeypatch):
    def fake_http(url: str, **kwargs):
        if url.endswith("/v1/auth/reload"):
            return 404, {"detail": "Not Found"}
        if url.endswith("/v1/control/restart"):
            return 200, {"state": "running"}
        return 0, None

    monkeypatch.setattr("cli.auth_runtime._http_json", fake_http)
    monkeypatch.setattr(
        "cli.auth_runtime.read_control_plane",
        lambda: {
            "host": "127.0.0.1",
            "port": 18787,
            "token": "tok",
            "api_base": "http://127.0.0.1:8787",
        },
    )
    result = apply_saved_auth_to_runtime()
    assert result.ok
    assert result.method == "menubar-restart"


def test_apply_reports_manual_when_nothing_running(monkeypatch):
    monkeypatch.setattr("cli.auth_runtime._http_json", lambda *a, **k: (0, None))
    monkeypatch.setattr("cli.auth_runtime.read_control_plane", lambda: None)
    result = apply_saved_auth_to_runtime()
    assert not result.ok
    assert result.method == "none"
    assert "No running Sandwalk Server" in result.message


def test_auth_reload_applies_disable_from_disk(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SANDWALK_SETTINGS_PATH", str(tmp_path / "settings.json"))
    from agent_server.app import create_app
    from agent_server.auth_settings import AuthSettings, save_settings
    from fastapi.testclient import TestClient

    save_settings(
        AuthSettings(
            api_key="sk-sandwalk-reloadtest00000000001",
            auth_enabled=True,
            secret_key="unit-secret-key",
        )
    )
    app = create_app(store_path=tmp_path / "agent.db")
    with TestClient(app) as client:
        assert client.get("/v1/sessions").status_code == 401
        save_settings(
            AuthSettings(
                api_key="sk-sandwalk-reloadtest00000000001",
                auth_enabled=False,
                secret_key="unit-secret-key",
            )
        )
        # Runtime still enforcing until reload.
        assert client.get("/v1/sessions").status_code == 401
        reloaded = client.post("/v1/auth/reload")
        assert reloaded.status_code == 200
        assert reloaded.json()["ok"] is True
        assert client.get("/v1/sessions").status_code == 200
