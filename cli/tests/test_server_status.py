"""Tests for GET /v1/status and server lifecycle endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from agent_server.app import create_app


def test_server_status_report(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("FASTFOLD_SERVE_HOST", "127.0.0.1")
    monkeypatch.setenv("FASTFOLD_SERVE_PORT", "8787")
    app = create_app(store_path=tmp_path / "agent.db")

    with TestClient(app) as client:
        response = client.get("/v1/status")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "running"
        assert body["version"]
        assert body["pid"] > 0
        assert body["uptimeSeconds"] >= 0
        assert "system" in body
        assert body["system"]["label"]
        assert body["system"]["ramTotalBytes"] >= 0
        assert "cache" in body
        assert body["cache"]["path"].endswith("cache")
        assert body["host"] == "127.0.0.1"
        assert body["port"] == 8787


def test_server_stop_and_restart_dry_run(tmp_path: Path):
    app = create_app(store_path=tmp_path / "agent.db")

    with TestClient(app) as client:
        stop = client.post("/v1/server/stop")
        assert stop.status_code == 200
        assert stop.json()["ok"] is True
        assert stop.json()["action"] == "stop"

        restart = client.post("/v1/server/restart")
        assert restart.status_code == 200
        assert restart.json()["ok"] is True
        assert restart.json()["action"] == "restart"


def test_clear_runtime_cache(tmp_path: Path, monkeypatch):
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "blob.bin").write_bytes(b"hello")
    nested = cache / "nested"
    nested.mkdir()
    (nested / "x.txt").write_text("x", encoding="utf-8")

    monkeypatch.setattr("agent_server.status_service.CONFIG_DIR", tmp_path)

    app = create_app(store_path=tmp_path / "agent.db")
    with TestClient(app) as client:
        before = client.get("/v1/status").json()["cache"]
        assert before["fileCount"] >= 1
        assert before["totalBytes"] >= 1

        cleared = client.post("/v1/storage/cache/clear")
        assert cleared.status_code == 200
        body = cleared.json()
        assert body["fileCount"] == 0
        assert body["totalBytes"] == 0
        assert cache.is_dir()
        assert not any(cache.iterdir())
