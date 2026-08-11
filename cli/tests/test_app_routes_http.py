"""HTTP route coverage for doctor, storage, projects, and MCP catalog."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from agent.config import Config
from agent_server.app import create_app
from agent_server.models import (
    DoctorReport,
    DoctorSummary,
    EnvironmentReport,
    StorageLocation,
    StorageReport,
)


def test_storage_and_doctor_routes(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent.config.CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr("agent.config.CONFIG_FILE", tmp_path / "cfg" / "config.json")
    (tmp_path / "cfg").mkdir(parents=True, exist_ok=True)
    Config({}).save()

    fake_report = {
        "ok": True,
        "checkedAt": "2026-01-01T00:00:00+00:00",
        "summary": {"ok": 1, "warn": 0, "error": 0, "total": 1},
        "checks": [],
    }
    fake_storage = StorageReport(
        location=StorageLocation(path=str(tmp_path), label="default location", bytes=0),
        categories=[],
        total_bytes=0,
        available_bytes=0,
        checked_at="2026-01-01T00:00:00+00:00",
    )

    with (
        patch("agent.doctor.to_report", return_value=fake_report),
        patch(
            "agent_server.storage_service.StorageService.get_report",
            return_value=fake_storage,
        ),
    ):
        app = create_app(store_path=tmp_path / "agent.db", allowed_hosts=["testserver"])
        with TestClient(app) as client:
            doctor = client.get("/v1/doctor")
            assert doctor.status_code == 200

            storage = client.get("/v1/storage")
            assert storage.status_code == 200

            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as zf:
                zf.writestr("diag.txt", "ok")
            with patch(
                "agent.diagnostics.build_diagnostics_zip",
                return_value=(buf.getvalue(), "diag.zip"),
            ):
                diag = client.get("/v1/doctor/diagnostics")
                assert diag.status_code == 200
                assert diag.headers["content-type"] == "application/zip"


def test_projects_http_crud(tmp_path: Path):
    app = create_app(store_path=tmp_path / "agent.db", allowed_hosts=["testserver"])
    folder = tmp_path / "project-data"
    folder.mkdir()
    with TestClient(app) as client:
        created = client.post(
            "/v1/projects",
            json={
                "name": "Parkinsons",
                "description": "Target discovery",
                "agentContext": "Focus on LRRK2",
                "folderPath": str(folder),
                "icon": "flask",
                "color": "green",
                "pinned": True,
            },
        )
        assert created.status_code == 201
        body = created.json()
        project_id = body["id"]
        assert body["folderPath"] == str(folder.resolve())
        assert body["icon"] == "flask"
        assert body["color"] == "green"

        listed = client.get("/v1/projects")
        assert listed.status_code == 200
        assert any(item["id"] == project_id for item in listed.json()["data"])

        fetched = client.get(f"/v1/projects/{project_id}")
        assert fetched.status_code == 200
        assert fetched.json()["icon"] == "flask"

        patched = client.patch(
            f"/v1/projects/{project_id}",
            json={
                "name": "Parkinsons v2",
                "pinned": False,
                "icon": "brain",
                "color": "purple",
                "clearFolderPath": True,
            },
        )
        assert patched.status_code == 200
        assert patched.json()["name"] == "Parkinsons v2"
        assert patched.json()["icon"] == "brain"
        assert patched.json()["color"] == "purple"
        assert patched.json()["folderPath"] is None

        deleted = client.delete(f"/v1/projects/{project_id}")
        assert deleted.status_code == 200
        assert deleted.json()["deleted"] is True


def test_mcp_catalog_connect_and_disconnect(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent.config.CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr("agent.config.CONFIG_FILE", tmp_path / "cfg" / "config.json")
    (tmp_path / "cfg").mkdir(parents=True, exist_ok=True)
    Config({}).save()

    app = create_app(store_path=tmp_path / "agent.db", allowed_hosts=["testserver"])
    with (
        TestClient(app) as client,
        patch(
            "agent_server.mcp_service.probe_mcp_server",
            return_value={"ok": True, "toolCount": 2, "message": "ok", "tools": ["a"]},
        ),
    ):
        connected = client.post(
            "/v1/mcp-servers/catalog/tamarind/connect",
            json={"method": "api_key", "apiKey": "tam-secret"},
        )
        assert connected.status_code == 200
        body = connected.json()
        assert body["ok"] is True
        assert body["toolCount"] == 2

        disconnected = client.delete("/v1/mcp-servers/catalog/tamarind/connect")
        assert disconnected.status_code == 200
        assert disconnected.json()["enabled"] is False

        missing = client.post(
            "/v1/mcp-servers/catalog/unknown/connect",
            json={"method": "api_key", "apiKey": "x"},
        )
        assert missing.status_code == 404


def test_mcp_catalog_enable_requires_credentials(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent.config.CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr("agent.config.CONFIG_FILE", tmp_path / "cfg" / "config.json")
    (tmp_path / "cfg").mkdir(parents=True, exist_ok=True)
    Config({}).save()

    app = create_app(store_path=tmp_path / "agent.db", allowed_hosts=["testserver"])
    with TestClient(app) as client:
        resp = client.patch(
            "/v1/mcp-servers/catalog/tamarind",
            json={"enabled": True},
        )
        assert resp.status_code == 400


def test_environment_route(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent.config.CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr("agent.config.CONFIG_FILE", tmp_path / "cfg" / "config.json")
    (tmp_path / "cfg").mkdir(parents=True, exist_ok=True)
    Config({}).save()

    with patch(
        "agent_server.environment_service.EnvironmentService.get_report",
        return_value=EnvironmentReport(
            python_path="/usr/bin/python3",
            env_path=None,
            env_bytes=0,
            groups=[],
            core=[],
            checked_at="2026-01-01T00:00:00+00:00",
        ),
    ):
        app = create_app(store_path=tmp_path / "agent.db", allowed_hosts=["testserver"])
        with TestClient(app) as client:
            env = client.get("/v1/environment")
            assert env.status_code == 200
