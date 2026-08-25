"""Unit tests for optional production UI mounting."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from agent_server.app import create_app
from agent_server.static_ui import resolve_ui_dist


def _write_fake_dist(root: Path) -> Path:
    dist = root / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text(
        "<!doctype html><html><body>Sandwalk UI</body></html>",
        encoding="utf-8",
    )
    (assets / "app.js").write_text("console.log('ok')", encoding="utf-8")
    (dist / "favicon.ico").write_text("ico", encoding="utf-8")
    return dist


def test_resolve_ui_dist_none_when_unset(monkeypatch):
    monkeypatch.delenv("SANDWALK_UI_DIST", raising=False)
    monkeypatch.delenv("FASTFOLD_UI_DIST", raising=False)
    assert resolve_ui_dist() is None


def test_resolve_ui_dist_requires_index(tmp_path: Path, monkeypatch):
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("SANDWALK_UI_DIST", str(empty))
    assert resolve_ui_dist() is None


def test_static_ui_serves_spa_and_keeps_api(tmp_path: Path, monkeypatch):
    dist = _write_fake_dist(tmp_path)
    monkeypatch.setenv("SANDWALK_UI_DIST", str(dist))

    app = create_app(store_path=tmp_path / "agent.db", allowed_hosts=["testserver"])
    with TestClient(app) as client:
        health = client.get("/v1/health")
        assert health.status_code == 200

        index = client.get("/")
        assert index.status_code == 200
        assert "Sandwalk UI" in index.text

        asset = client.get("/assets/app.js")
        assert asset.status_code == 200
        assert "console.log" in asset.text

        favicon = client.get("/favicon.ico")
        assert favicon.status_code == 200

        spa = client.get("/dashboard/skills")
        assert spa.status_code == 200
        assert "Sandwalk UI" in spa.text

        missing_api = client.get("/v1/this-route-is-not-registered")
        assert missing_api.status_code == 404
        assert missing_api.headers["content-type"].startswith("application/json")
        assert "Not Found" in missing_api.json()["detail"]
