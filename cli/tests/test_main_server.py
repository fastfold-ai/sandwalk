"""Tests for agent_server.main run_server launcher."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent_server.main import run_server


def test_run_server_loopback_starts_uvicorn(tmp_path: Path, monkeypatch):
    captured: dict = {}

    def fake_run(app, **kwargs):
        captured["app"] = app
        captured["kwargs"] = kwargs

    monkeypatch.setattr("uvicorn.run", fake_run)
    monkeypatch.setenv("SANDWALK_SETTINGS_PATH", str(tmp_path / "settings.json"))

    run_server(host="127.0.0.1", port=9999, api_key="local-secret")

    assert captured["kwargs"]["host"] == "127.0.0.1"
    assert captured["kwargs"]["port"] == 9999
    assert captured["app"] is not None


def test_run_server_uds_mode(tmp_path: Path, monkeypatch):
    socket_path = tmp_path / "agent.sock"
    captured: dict = {}

    def fake_run(app, **kwargs):
        captured.update(kwargs)

    monkeypatch.setattr("uvicorn.run", fake_run)
    monkeypatch.setenv("SANDWALK_SETTINGS_PATH", str(tmp_path / "settings.json"))

    run_server(host="127.0.0.1", uds=socket_path)

    assert captured.get("uds") == str(socket_path.resolve())
    assert not socket_path.exists()


def test_run_server_rejects_public_without_key(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("uvicorn.run", lambda *args, **kwargs: None)
    monkeypatch.setenv("SANDWALK_SETTINGS_PATH", str(tmp_path / "settings.json"))

    with pytest.raises(ValueError, match="api-key"):
        run_server(host="0.0.0.0", public=True)


def test_run_server_rejects_uds_with_public(tmp_path: Path):
    with pytest.raises(ValueError, match="Unix-socket"):
        run_server(host="127.0.0.1", public=True, api_key="k", uds=Path("/tmp/x.sock"))


def test_run_server_rejects_non_loopback_without_public():
    with pytest.raises(ValueError, match="Non-loopback"):
        run_server(host="0.0.0.0")
