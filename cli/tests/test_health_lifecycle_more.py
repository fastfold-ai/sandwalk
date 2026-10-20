"""Coverage for health routes and server stop/restart helpers."""

from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent_server.environment_service import EnvironmentError
from agent_server.models import (
    DoctorReport,
    DoctorSummary,
    EnvironmentPackageMutationResult,
    ServerCacheInfo,
    ServicesReport,
)
from agent_server.routes.health import local_user_name, register_health_routes
from agent_server.status_service import lifecycle


def test_local_user_and_health_routes(monkeypatch) -> None:
    def boom(*_args, **_kwargs):
        raise OSError("pwd")

    monkeypatch.setattr("pwd.getpwuid", boom, raising=False)
    assert local_user_name()

    deps = SimpleNamespace(
        backend_id="dev",
        service=SimpleNamespace(),
        current_api_key=lambda: "secret",
    )
    app = FastAPI()
    register_health_routes(app, deps)
    client = TestClient(app)

    assert client.get("/v1/health").status_code == 200
    debug = client.get("/v1/debug/health")
    assert debug.json()["active_runs"] == -1
    deps.service._active_runs = {"a": 1}
    assert client.get("/v1/debug/health").json()["active_runs"] == 1

    assert client.get("/v1/discover").status_code == 200
    monkeypatch.setattr(
        "agent_server.services_report.build_services_report",
        lambda version: ServicesReport(checked_at="now"),
    )
    assert client.get("/v1/services").status_code == 200
    monkeypatch.setattr(
        "agent_server.status_service.clear_cache",
        lambda: ServerCacheInfo(path="/tmp/cache"),
    )
    assert client.post("/v1/storage/cache/clear").status_code == 200
    monkeypatch.setattr(
        "agent_server.status_service.schedule_stop",
        lambda: lifecycle.schedule_stop(),
    )
    assert client.post("/v1/server/stop").status_code == 200

    assert client.get("/v1/doctor", params={"scope": "nope"}).status_code == 400
    monkeypatch.setattr(
        "agent.doctor.to_report",
        lambda scope: {
            "ok": True,
            "checked_at": "now",
            "summary": DoctorSummary().model_dump(),
            "checks": [],
        },
    )
    assert client.get("/v1/doctor").status_code == 200
    assert DoctorReport.model_validate(
        {"ok": True, "checked_at": "now", "summary": {"ok": 1, "warn": 0, "error": 0, "total": 1}}
    )

    monkeypatch.setattr(
        "agent.diagnostics.build_diagnostics_zip",
        lambda **kwargs: (b"PK", "diag.zip"),
    )
    downloaded = client.post("/v1/doctor/diagnostics", json={"ui_diagnostics": {"page": "doctor"}})
    assert downloaded.headers["content-type"] == "application/zip"

    def fail_install(self, name, allow_unlisted=False):
        raise EnvironmentError("nope")

    monkeypatch.setattr(
        "agent_server.environment_service.EnvironmentService.install",
        fail_install,
    )
    def fail_uninstall(self, name):
        raise EnvironmentError("nope")

    monkeypatch.setattr(
        "agent_server.environment_service.EnvironmentService.uninstall",
        fail_uninstall,
    )
    assert client.post("/v1/environment/packages/install", json={"name": "cowsay"}).status_code == 400
    assert client.post("/v1/environment/packages/uninstall", json={"name": "cowsay"}).status_code == 400
    monkeypatch.setattr(
        "agent_server.environment_service.EnvironmentService.install",
        lambda self, name, allow_unlisted=False: EnvironmentPackageMutationResult(
            action="install", name=name, message="ok"
        ),
    )
    assert client.post(
        "/v1/environment/packages/install",
        json={"name": "cowsay", "allow_unlisted": True},
    ).status_code == 200


def test_server_lifecycle_dry_run_and_command(monkeypatch) -> None:
    monkeypatch.setenv("FASTFOLD_DISABLE_SERVER_LIFECYCLE", "1")
    assert lifecycle._lifecycle_allowed() is False
    monkeypatch.delenv("FASTFOLD_DISABLE_SERVER_LIFECYCLE", raising=False)
    assert lifecycle._lifecycle_allowed() is False

    monkeypatch.setenv("FASTFOLD_SERVE_PUBLIC", "1")
    monkeypatch.setenv("FASTFOLD_SERVER_API_KEY", "secret")
    monkeypatch.setenv("FASTFOLD_SERVE_ORIGINS", "https://a.test, https://b.test")
    monkeypatch.setenv("FASTFOLD_SERVE_HOSTS", "a.test")
    monkeypatch.setenv("FASTFOLD_SERVE_UDS", "/tmp/sandwalk.sock")
    monkeypatch.setattr(lifecycle.shutil, "which", lambda _name: None)
    cmd = lifecycle._build_restart_command()
    assert "--uds" in cmd
    assert "--public" in cmd
    assert "--api-key" in cmd

    started: list[object] = []

    class ImmediateThread:
        def __init__(self, target, name, daemon) -> None:
            self.target = target

        def start(self) -> None:
            started.append(self.target)

    monkeypatch.setattr(lifecycle.threading, "Thread", ImmediateThread)
    monkeypatch.setattr(lifecycle.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(lifecycle.os, "kill", lambda *_args: None)
    monkeypatch.setattr(lifecycle.subprocess, "Popen", lambda *args, **kwargs: None)
    monkeypatch.setattr("agent_server.status_service._lifecycle_allowed", lambda: True)
    stopped = lifecycle.schedule_stop()
    assert stopped.action == "stop"
    started[0]()
    restarted = lifecycle.schedule_restart()
    assert restarted.action == "restart"
    started[1]()
