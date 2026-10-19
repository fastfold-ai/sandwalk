"""Unit coverage for bench install jobs, integration routes, and mcp CLI status."""

from __future__ import annotations

import threading
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent.mcp_manage import status as mcp_status
from agent.mcp_manage import toggle_actions
from agent_server.bench_service import install_jobs as jobs
from agent_server.bench_service.dataset_install import BenchInstallError
from agent_server.models.bench import BenchInstallResponse
from agent_server.models.integrations import (
    IntegrationProvider,
    IntegrationSecretResponse,
    IntegrationSetupResponse,
    ValidateIntegrationResponse,
)
from agent_server.routes import integrations as integration_routes

_MISSING = object()


def _provider(key: str = "anthropic", *, configured: bool = True) -> IntegrationProvider:
    env_var = "FASTFOLD_API_KEY" if key == "fastfold-cloud" else "ANTHROPIC_API_KEY"
    return IntegrationProvider(
        key=key,
        name=key,
        category="llm",
        description="desc",
        env_var=env_var,
        configured=configured,
        source="config" if configured else "none",
    )


def _wait_job(suite_id: str, status: str) -> jobs.InstallJob:
    deadline = time.time() + 2
    job = None
    while time.time() < deadline:
        job = jobs.get_install_job(suite_id)
        if job is not None and job.status == status:
            return job
        time.sleep(0.01)
    raise AssertionError(f"{suite_id} did not reach {status}: {job}")


def test_install_job_queries_and_formatting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jobs, "_jobs", {})
    assert jobs.get_install_job("mbpp") is None
    assert jobs.is_installing("mbpp") is False
    assert jobs.install_error("mbpp") is None
    assert jobs.install_progress_text("mbpp") is None
    jobs.clear_install_job("mbpp")

    jobs._jobs["mbpp"] = jobs.InstallJob(
        suite_id="mbpp",
        status="installing",
        summary="Starting download…",
        label="Starting…",
        bytes_done=12,
        bytes_total=34,
        questions_done=1,
        questions_total=2,
        files_done=3,
        files_total=4,
        path="/cache",
        error="nope",
        needs_hf_token=True,
    )
    copied = jobs.get_install_job("mbpp")
    assert copied is not None
    copied.summary = "mutated"
    assert jobs._jobs["mbpp"].summary == "Starting download…"
    assert jobs.is_installing("mbpp") is True
    assert jobs.install_error("mbpp") is None
    assert jobs.install_progress_text("mbpp") is not None

    questions = jobs.InstallJob(
        suite_id="mmlu",
        status="installing",
        questions_done=1000,
        questions_total=4000,
    )
    assert jobs._format_progress(questions) == "1,000 / 4,000 questions · 3,000 left · 25%"
    over = jobs.InstallJob(
        suite_id="mmlu", status="installing", questions_done=10, questions_total=4
    )
    assert "0 left" in jobs._format_progress(over)
    assert "100%" in jobs._format_progress(over)
    partial = jobs.InstallJob(
        suite_id="mmlu", status="installing", questions_done=3, questions_total=0
    )
    assert jobs._format_progress(partial) == "3 questions downloaded"
    no_total = jobs.InstallJob(
        suite_id="mmlu", status="installing", questions_done=5, questions_total=None
    )
    assert jobs._format_progress(no_total) == "5 questions downloaded"

    sized = jobs.InstallJob(suite_id="mbpp", status="installing", bytes_done=512, bytes_total=1024)
    assert jobs._format_progress(sized) == "512 B / 1.0 KB · 512 B left · 50%"
    overflow = jobs.InstallJob(
        suite_id="mbpp", status="installing", bytes_done=4096, bytes_total=1024
    )
    byte_text = jobs._format_progress(overflow)
    assert "100%" in byte_text
    assert "0 B left" in byte_text
    open_ended = jobs.InstallJob(
        suite_id="mbpp", status="installing", bytes_done=1024, bytes_total=0
    )
    assert jobs._format_progress(open_ended) == "1.0 KB downloaded"

    labeled = jobs.InstallJob(
        suite_id="mbpp", status="installing", label="shard.json", summary="old"
    )
    assert jobs._format_progress(labeled) == "Downloading shard.json…"
    starting = jobs.InstallJob(
        suite_id="mbpp", status="installing", label="Starting...", summary="halfway"
    )
    assert jobs._format_progress(starting) == "halfway"
    empty = jobs.InstallJob(suite_id="mbpp", status="installing", summary="", label="Starting…")
    assert jobs._format_progress(empty) == "Downloading dataset…"

    assert jobs._format_bytes(0) == "0 B"
    assert jobs._format_bytes(1023) == "1023 B"
    assert jobs._format_bytes(1024) == "1.0 KB"
    assert jobs._format_bytes(1024 * 1024) == "1.0 MB"
    assert jobs._format_bytes(1024**3) == "1.0 GB"
    assert jobs._format_bytes(1024**4) == "1024.0 GB"
    assert jobs._format_bytes(-10) == "0 B"

    jobs._jobs["mbpp"] = jobs.InstallJob(suite_id="mbpp", status="error", summary="sum", error=None)
    assert jobs.install_error("mbpp") == "sum"
    jobs._jobs["mbpp"] = jobs.InstallJob(suite_id="mbpp", status="error", summary="", error="")
    assert jobs.install_error("mbpp") == "Install failed."
    jobs._jobs["mbpp"] = jobs.InstallJob(
        suite_id="mbpp", status="done", summary="ok", error="stale", path="/cache/mbpp"
    )
    assert jobs.install_error("mbpp") is None
    assert jobs.install_progress_text("mbpp") is None
    assert jobs.is_installing("mbpp") is False
    jobs.clear_install_job("mbpp")
    assert jobs.get_install_job("mbpp") is None
    jobs.clear_install_job("mbpp")


def test_run_install_progress_success_and_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jobs, "_jobs", {})
    jobs._jobs["mbpp"] = jobs.InstallJob(
        suite_id="mbpp",
        status="installing",
        summary="Starting download…",
        label="Starting…",
    )

    def install(suite_id: str, *, force: bool = False, on_progress=None) -> BenchInstallResponse:
        assert suite_id == "mbpp"
        assert force is False
        assert on_progress is not None
        on_progress()
        on_progress(
            summary="grabbing",
            bytes_done=-8,
            bytes_total=2048,
            questions_done=-2,
            questions_total=0,
            files_done=-3,
            files_total=-1,
            label="part.bin",
        )
        snap = jobs.get_install_job(suite_id)
        assert snap is not None
        assert snap.bytes_done == 0
        assert snap.bytes_total == 2048
        assert snap.questions_done == 0
        assert snap.questions_total is None
        assert snap.files_done == 0
        assert snap.files_total == 0
        assert snap.label == "part.bin"
        on_progress(bytes_done=50, bytes_total=0, files_done=2, files_total=5)
        snap = jobs.get_install_job(suite_id)
        assert snap is not None
        assert snap.bytes_done == 50
        assert snap.bytes_total is None
        assert snap.files_done == 2
        assert snap.files_total == 5
        on_progress(questions_done=6, questions_total=9, label="rows")
        snap = jobs.get_install_job(suite_id)
        assert snap is not None
        assert snap.questions_done == 6
        assert snap.questions_total == 9
        assert snap.label == "rows"
        assert "6 / 9" in snap.summary
        with jobs._lock:
            jobs._jobs[suite_id].status = "error"
        before = jobs.get_install_job(suite_id)
        on_progress(summary="ignored", bytes_done=99)
        after = jobs.get_install_job(suite_id)
        assert before is not None and after is not None
        assert after.summary == before.summary
        assert after.bytes_done == before.bytes_done
        with jobs._lock:
            jobs._jobs.pop(suite_id, None)
        on_progress(summary="missing", bytes_done=5)
        assert jobs.get_install_job(suite_id) is None
        return BenchInstallResponse(
            ok=True, suite_id=suite_id, summary="Installed MBPP", path="/cache/mbpp"
        )

    monkeypatch.setattr(jobs, "install_suite", install)
    jobs._run_install("mbpp", False)
    done = jobs.get_install_job("mbpp")
    assert done is not None
    assert done.status == "done"
    assert done.summary == "Installed MBPP"
    assert done.path == "/cache/mbpp"
    assert jobs.install_error("mbpp") is None

    def raise_token(
        suite_id: str, *, force: bool = False, on_progress=None
    ) -> BenchInstallResponse:
        raise BenchInstallError("need token", needs_hf_token=True)

    monkeypatch.setattr(jobs, "install_suite", raise_token)
    jobs._run_install("mbpp", True)
    failed = jobs.get_install_job("mbpp")
    assert failed is not None
    assert failed.status == "error"
    assert failed.needs_hf_token is True
    assert jobs.install_error("mbpp") == "need token"

    def raise_blank(
        suite_id: str, *, force: bool = False, on_progress=None
    ) -> BenchInstallResponse:
        raise BenchInstallError("")

    monkeypatch.setattr(jobs, "install_suite", raise_blank)
    jobs._run_install("mmlu", False)
    assert jobs.install_error("mmlu") == "Install failed."

    def raise_crash(
        suite_id: str, *, force: bool = False, on_progress=None
    ) -> BenchInstallResponse:
        raise RuntimeError("disk full")

    monkeypatch.setattr(jobs, "install_suite", raise_crash)
    jobs._run_install("livecodebench", False)
    crashed = jobs.get_install_job("livecodebench")
    assert crashed is not None
    assert crashed.status == "error"
    assert crashed.needs_hf_token is False
    assert jobs.install_error("livecodebench") == "disk full"


def test_start_install_guards_and_background(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jobs, "_jobs", {})
    monkeypatch.setattr(jobs, "_lock", threading.RLock())

    def forbidden(suite_id: str, *, force: bool = False, on_progress=None) -> BenchInstallResponse:
        raise AssertionError("install_suite should not run")

    monkeypatch.setattr(jobs, "install_suite", forbidden)

    with pytest.raises(BenchInstallError) as unknown:
        jobs.start_install("  not-a-suite  ")
    assert unknown.value.status_code == 404

    def no_token() -> str:
        return ""

    monkeypatch.setattr(jobs, "resolve_hf_token", no_token)
    with pytest.raises(BenchInstallError) as missing_token:
        jobs.start_install("bixbench-verified-50")
    assert missing_token.value.needs_hf_token is True

    jobs._jobs["mbpp"] = jobs.InstallJob(
        suite_id="mbpp",
        status="installing",
        questions_done=10,
        questions_total=40,
    )
    assert jobs.is_installing("mbpp") is True
    existing = jobs.start_install("mbpp")
    assert existing.status == "installing"
    assert existing.suite_id == "mbpp"
    assert "10 / 40" in existing.summary

    def blank(_suite_id: str) -> str:
        return ""

    real_progress = jobs.install_progress_text
    monkeypatch.setattr(jobs, "install_progress_text", blank)
    again = jobs.start_install(" mbpp ")
    assert again.summary == "Install already in progress."
    assert again.ok is True
    monkeypatch.setattr(jobs, "install_progress_text", real_progress)
    jobs.clear_install_job("mbpp")

    seen: dict[str, object] = {}

    def fake_install(
        suite_id: str, *, force: bool = False, on_progress=None
    ) -> BenchInstallResponse:
        seen["suite_id"] = suite_id
        seen["force"] = force
        return BenchInstallResponse(
            ok=True, suite_id=suite_id, summary="done now", path=f"/cache/{suite_id}"
        )

    def token() -> str:
        return "hf_test"

    monkeypatch.setattr(jobs, "install_suite", fake_install)
    monkeypatch.setattr(jobs, "resolve_hf_token", token)
    started = jobs.start_install("  mbpp  ", force=True)
    assert started.status == "installing"
    assert started.summary == "Install started in the background."
    finished = _wait_job("mbpp", "done")
    assert finished.path == "/cache/mbpp"
    assert seen == {"suite_id": "mbpp", "force": True}
    assert jobs.is_installing("mbpp") is False

    seen.clear()
    bix = jobs.start_install("bixbench-verified-50", force=False)
    assert bix.status == "installing"
    bix_done = _wait_job("bixbench-verified-50", "done")
    assert bix_done.summary == "done now"
    assert seen == {"suite_id": "bixbench-verified-50", "force": False}


class _Integrations:
    def __init__(self) -> None:
        self.updates: list[tuple[str, dict[str, str]]] = []
        self.setups: list[tuple[str, str | None]] = []

    def list(self) -> list[IntegrationProvider]:
        return [_provider()]

    def get(self, key: str) -> IntegrationProvider | None:
        if key in {"missing", "ghost"}:
            return None
        return _provider(key)

    def reveal_secret(self, key: str) -> IntegrationSecretResponse:
        if key == "missing":
            raise KeyError(key)
        return IntegrationSecretResponse(
            configured=True, env_var="ANTHROPIC_API_KEY", value="secret"
        )

    def update(self, key: str, values: dict[str, str]) -> IntegrationProvider:
        self.updates.append((key, dict(values)))
        if key == "missing":
            raise KeyError(key)
        if key == "bad":
            raise ValueError("bad value")
        return _provider(key)

    def remove(self, key: str) -> IntegrationProvider:
        if key == "missing":
            raise KeyError(key)
        return _provider(key, configured=False)

    def validate(self, key: str) -> ValidateIntegrationResponse:
        if key == "missing":
            raise KeyError(key)
        return ValidateIntegrationResponse(ok=True, configured=True, source="config", message="ok")

    def install_capability(self, key: str, capability_id: str) -> IntegrationProvider:
        if key == "missing":
            raise KeyError(key)
        if capability_id == "bad":
            raise ValueError("cannot install")
        return _provider(key)

    def autofill(self, key: str) -> IntegrationProvider:
        if key == "missing":
            raise KeyError(key)
        if key == "bad":
            raise ValueError("no autofill")
        return _provider(key)

    def setup(self, key: str, working_directory: str | None) -> IntegrationSetupResponse:
        self.setups.append((key, working_directory))
        if key == "missing":
            raise KeyError(key)
        if key == "bad":
            raise ValueError("no setup")
        return IntegrationSetupResponse(ok=True, integration_key=key, summary="ready")


class _Connector:
    def __init__(self) -> None:
        self.calls = 0
        self.fail = False

    async def reconcile_fastfold_auth(self) -> None:
        self.calls += 1
        if self.fail:
            raise RuntimeError("relay down")


def test_integration_routes_with_fake_service(monkeypatch: pytest.MonkeyPatch) -> None:
    svc = _Integrations()
    connector = _Connector()
    app = FastAPI()
    integration_routes.register_integration_routes(
        app,
        SimpleNamespace(integrations_service=svc, connector_service=connector),
    )
    client = TestClient(app)

    listing = client.get("/v1/integrations")
    assert listing.status_code == 200
    assert listing.json()["data"][0]["key"] == "anthropic"
    assert client.get("/v1/integrations/anthropic").status_code == 200
    missing = client.get("/v1/integrations/missing")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Integration not found."

    revealed = client.get("/v1/integrations/anthropic/secret")
    assert revealed.status_code == 200
    assert revealed.json()["value"] == "secret"
    assert client.get("/v1/integrations/missing/secret").status_code == 404

    updated = client.put(
        "/v1/integrations/anthropic",
        json={"value": "sk-test", "values": {"EXTRA": "1"}},
    )
    assert updated.status_code == 200
    assert svc.updates[-1] == ("anthropic", {"EXTRA": "1", "ANTHROPIC_API_KEY": "sk-test"})
    assert connector.calls == 0

    fastfold = client.put(
        "/v1/integrations/fastfold-cloud",
        json={"values": {"FASTFOLD_API_KEY": "ff"}},
    )
    assert fastfold.status_code == 200
    assert connector.calls == 1
    assert svc.updates[-1] == ("fastfold-cloud", {"FASTFOLD_API_KEY": "ff"})

    ghost = client.put("/v1/integrations/ghost", json={"value": "abc"})
    assert ghost.status_code == 404
    assert all(key != "ghost" for key, _values in svc.updates)
    bad = client.put("/v1/integrations/bad", json={"values": {"X": "y"}})
    assert bad.status_code == 400
    assert bad.json()["detail"] == "bad value"
    assert client.put("/v1/integrations/missing", json={"values": {"X": "y"}}).status_code == 404

    connector.fail = True
    removed = client.delete("/v1/integrations/fastfold-cloud")
    assert removed.status_code == 200
    assert removed.json()["configured"] is False
    assert connector.calls == 2
    assert client.delete("/v1/integrations/missing").status_code == 404
    connector.fail = False

    validated = client.post("/v1/integrations/anthropic/validate")
    assert validated.status_code == 200
    assert validated.json()["ok"] is True
    assert client.post("/v1/integrations/missing/validate").status_code == 404

    installed = client.post("/v1/integrations/boltz/capabilities/boltz-api-cli/install")
    assert installed.status_code == 200
    assert client.post("/v1/integrations/missing/capabilities/x/install").status_code == 404
    rejected = client.post("/v1/integrations/boltz/capabilities/bad/install")
    assert rejected.status_code == 400
    assert rejected.json()["detail"] == "cannot install"

    assert client.post("/v1/integrations/skills-sh/autofill").status_code == 200
    assert client.post("/v1/integrations/missing/autofill").status_code == 404
    autofill_bad = client.post("/v1/integrations/bad/autofill")
    assert autofill_bad.status_code == 400
    assert autofill_bad.json()["detail"] == "no autofill"

    setup = client.post(
        "/v1/integrations/skills-sh/setup",
        json={"workingDirectory": "/work"},
    )
    assert setup.status_code == 200
    assert setup.json()["summary"] == "ready"
    assert svc.setups[-1] == ("skills-sh", "/work")
    default_setup = client.post("/v1/integrations/skills-sh/setup")
    assert default_setup.status_code == 200
    assert svc.setups[-1] == ("skills-sh", None)
    assert client.post("/v1/integrations/missing/setup", json={}).status_code == 404
    setup_bad = client.post("/v1/integrations/bad/setup", json={})
    assert setup_bad.status_code == 400
    assert setup_bad.json()["detail"] == "no setup"

    seen_returns: list[str] = []
    reject_start = {"on": False}
    import_queue: list[object] = [
        {
            "ready": True,
            "provider": _provider("fastfold-cloud"),
            "team_id": 12,
        },
        {"ready": False},
        {"ready": True, "provider": _provider("fastfold-cloud"), "team_id": None},
        "bad",
    ]

    def fake_start(*, return_to: str) -> str:
        seen_returns.append(return_to)
        if reject_start["on"]:
            raise ValueError("origin rejected")
        return "https://example.test/allow"

    def fake_import(service: _Integrations) -> dict:
        assert service is svc
        item = import_queue.pop(0)
        if item == "bad":
            raise ValueError("grant missing")
        assert isinstance(item, dict)
        return item

    monkeypatch.setattr(
        "agent_server.integrations_service.fastfold_one_click.start_fastfold_one_click",
        fake_start,
    )
    monkeypatch.setattr(
        "agent_server.integrations_service.fastfold_one_click.import_fastfold_one_click",
        fake_import,
    )

    started = client.post(
        "/v1/integrations/fastfold-cloud/one-click",
        headers={"origin": "http://localhost:1420"},
    )
    assert started.status_code == 200
    assert started.json()["authUrl"] == "https://example.test/allow"
    assert seen_returns and "localhost:1420" in seen_returns[-1]
    reject_start["on"] = True
    rejected_start = client.post("/v1/integrations/fastfold-cloud/one-click")
    assert rejected_start.status_code == 400
    assert rejected_start.json()["detail"] == "origin rejected"

    connector.fail = True
    calls_before = connector.calls
    imported = client.post("/v1/integrations/fastfold-cloud/one-click/import")
    assert imported.status_code == 200
    body = imported.json()
    assert body["ready"] is True
    assert body["teamId"] == "12"
    assert body["provider"]["key"] == "fastfold-cloud"
    assert connector.calls == calls_before + 1

    waiting = client.post("/v1/integrations/fastfold-cloud/one-click/import")
    assert waiting.status_code == 200
    assert waiting.json()["ready"] is False
    assert waiting.json()["provider"] is None
    assert waiting.json()["teamId"] is None
    assert connector.calls == calls_before + 1

    connector.fail = False
    noteam = client.post("/v1/integrations/fastfold-cloud/one-click/import")
    assert noteam.status_code == 200
    assert noteam.json()["ready"] is True
    assert noteam.json()["teamId"] is None
    assert connector.calls == calls_before + 2

    grant = client.post("/v1/integrations/fastfold-cloud/one-click/import")
    assert grant.status_code == 400
    assert grant.json()["detail"] == "grant missing"
    assert connector.calls == calls_before + 2


def _prints(console: MagicMock) -> str:
    return " ".join(str(call.args[0]) for call in console.print.call_args_list if call.args)


def test_enable_disable_usage_and_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    entry_stdio = SimpleNamespace(id="pymol", name="PyMOL", transport="stdio", auth_mode="none")
    entry_http = SimpleNamespace(
        id="exa", name="Exa", transport="streamable_http", auth_mode="api_key"
    )
    entry_ok = SimpleNamespace(
        id="ok-server", name="Ready", transport="streamable_http", auth_mode="api_key"
    )
    plans = [
        (None, None),
        (entry_stdio, None),
        (entry_stdio, None),
        (entry_http, None),
        (entry_ok, SimpleNamespace(id="id-ready", name="Ready")),
        (None, SimpleNamespace(id="id-custom", name="Mine")),
        (entry_stdio, SimpleNamespace(id="id-off", name="PyMOL")),
    ]
    ensured = [
        None,
        SimpleNamespace(id="id-stdio", name="PyMOL"),
        SimpleNamespace(id="id-http", name="Exa"),
    ]
    store = MagicMock()
    service = MagicMock()

    def resolve(ref: str, store_arg: object) -> tuple:
        assert store_arg is store
        assert ref
        return plans.pop(0)

    def ensure(catalog_id: str, *, enabled: bool):
        assert enabled is False
        assert catalog_id
        return ensured.pop(0)

    def credentials_configured(entry, config=None) -> bool:
        return entry.id == "ok-server"

    monkeypatch.setattr(toggle_actions, "resolve_server_ref", resolve)
    monkeypatch.setattr(
        "agent_server.mcp_service.credentials_configured",
        credentials_configured,
    )
    service.ensure_catalog_server.side_effect = ensure

    console = MagicMock()
    assert (
        toggle_actions.handle_enable_disable(
            "enable", ["enable"], console, store=store, service=service
        )
        == 2
    )
    assert "Usage:" in _prints(console)

    console = MagicMock()
    assert (
        toggle_actions.handle_enable_disable(
            "enable", ["enable", "missing"], console, store=store, service=service
        )
        == 1
    )
    assert "Not found" in _prints(console)

    console = MagicMock()
    assert (
        toggle_actions.handle_enable_disable(
            "enable", ["enable", "pymol"], console, store=store, service=service
        )
        == 1
    )
    assert "Not found" in _prints(console)

    console = MagicMock()
    assert (
        toggle_actions.handle_enable_disable(
            "enable", ["enable", "pymol"], console, store=store, service=service
        )
        == 1
    )
    assert "launcher is not installed" in _prints(console)

    console = MagicMock()
    assert (
        toggle_actions.handle_enable_disable(
            "enable", ["enable", "exa"], console, store=store, service=service
        )
        == 1
    )
    assert "is not connected" in _prints(console)
    assert "mcp connect exa" in _prints(console)

    console = MagicMock()
    assert (
        toggle_actions.handle_enable_disable(
            "enable", ["enable", "ok-server"], console, store=store, service=service
        )
        == 0
    )
    assert "Enabled" in _prints(console)

    console = MagicMock()
    assert (
        toggle_actions.handle_enable_disable(
            "enable", ["enable", "mine"], console, store=store, service=service
        )
        == 0
    )
    assert "Enabled" in _prints(console)
    assert "Mine" in _prints(console)

    console = MagicMock()
    assert (
        toggle_actions.handle_enable_disable(
            "disable", ["disable", "pymol"], console, store=store, service=service
        )
        == 0
    )
    assert "Disabled" in _prints(console)
    assert plans == []
    assert ensured == []
    assert store.update_mcp_server.call_args_list == [
        (("id-ready",), {"enabled": True}),
        (("id-custom",), {"enabled": True}),
        (("id-off",), {"enabled": False}),
    ]


def test_validate_reports_tools_and_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    entry_many = SimpleNamespace(id="many")
    entry_one = SimpleNamespace(id="one")
    entry_boom = SimpleNamespace(id="boom")
    server_bare = SimpleNamespace(id="bare")
    server_empty = SimpleNamespace(id="empty")
    plans = [
        (None, None),
        (entry_many, SimpleNamespace(id="ignored")),
        (entry_one, None),
        (None, server_bare),
        (entry_boom, server_bare),
        (None, server_empty),
    ]

    def resolve(ref: str, store_arg: object) -> tuple:
        assert ref
        return plans.pop(0)

    def validate(*, catalog_id: str | None = None, server_id: str | None = None) -> dict:
        if catalog_id == "boom":
            raise RuntimeError("probe down")
        if catalog_id == "many":
            return {
                "ok": True,
                "message": "up",
                "toolCount": 41,
                "tools": [f"tool-{index}" for index in range(41)],
            }
        if catalog_id == "one":
            return {"ok": False, "message": "down", "tools": ["only"]}
        if server_id == "bare":
            return {"ok": True, "tools": ["alpha"]}
        if server_id == "empty":
            return {"ok": False, "message": "none"}
        raise AssertionError((catalog_id, server_id))

    monkeypatch.setattr(toggle_actions, "resolve_server_ref", resolve)
    service = MagicMock()
    service.validate.side_effect = validate
    store = MagicMock()

    console = MagicMock()
    assert (
        toggle_actions.handle_validate("probe", ["probe"], console, store=store, service=service)
        == 2
    )
    assert "mcp probe" in _prints(console)

    console = MagicMock()
    assert (
        toggle_actions.handle_validate(
            "validate", ["validate", "missing"], console, store=store, service=service
        )
        == 1
    )
    assert "Not found" in _prints(console)

    console = MagicMock()
    assert (
        toggle_actions.handle_validate(
            "tools", ["tools", "many"], console, store=store, service=service
        )
        == 0
    )
    printed = _prints(console)
    assert "up" in printed
    assert "Tools (41)" in printed
    assert "tool-0" in printed
    assert "tool-39" in printed
    assert "+1 more" in printed
    assert "tool-40" not in printed

    console = MagicMock()
    assert (
        toggle_actions.handle_validate(
            "validate", ["validate", "one"], console, store=store, service=service
        )
        == 1
    )
    printed = _prints(console)
    assert "down" in printed
    assert "only" in printed
    assert "more" not in printed

    console = MagicMock()
    assert (
        toggle_actions.handle_validate(
            "validate", ["validate", "bare"], console, store=store, service=service
        )
        == 0
    )
    printed = _prints(console)
    assert "Tools (1)" in printed
    assert "alpha" in printed

    console = MagicMock()
    assert (
        toggle_actions.handle_validate(
            "validate", ["validate", "boom"], console, store=store, service=service
        )
        == 1
    )
    assert "Validate failed" in _prints(console)
    assert "probe down" in _prints(console)

    console = MagicMock()
    assert (
        toggle_actions.handle_validate(
            "validate", ["validate", "empty"], console, store=store, service=service
        )
        == 1
    )
    printed = _prints(console)
    assert "none" in printed
    assert "Tools" not in printed
    assert plans == []


def test_print_mcp_status_catalog_and_servers(monkeypatch: pytest.MonkeyPatch) -> None:
    from rich.table import Table

    class _Server:
        def __init__(
            self,
            id: str,
            name: str,
            enabled: bool,
            transport: str,
            url: str | None = None,
            command: str | None = None,
            args: list[str] | None = None,
            catalog_id: object = _MISSING,
        ) -> None:
            self.id = id
            self.name = name
            self.enabled = enabled
            self.transport = transport
            self.url = url
            self.command = command
            self.args = [] if args is None else args
            if catalog_id is not _MISSING:
                self.catalog_id = catalog_id

    catalog = [
        {
            "id": "pymol",
            "name": "PyMOL",
            "connected": True,
            "auth_method": "oauth",
            "transport": "stdio",
        },
        {
            "id": "exa",
            "name": "Exa",
            "enabled": True,
            "preferred_auth": "api_key",
            "transport": "streamable_http",
        },
        {
            "id": "linear",
            "name": "Linear",
            "configured": True,
            "auth_mode": "api_key",
            "transport": "sse",
        },
        {"id": "off", "name": "Off", "transport": "http"},
    ]
    servers = [
        _Server(
            "abcdef123456",
            "PyMOL",
            True,
            "stdio",
            command="python",
            args=["-m", "pymol"],
            catalog_id="pymol",
        ),
        _Server(
            "1234567890ab",
            "Exa",
            False,
            "streamable_http",
            url="https://exa.example/mcp",
            catalog_id="exa",
        ),
        _Server(
            "custom1234", "Mine", True, "sse", url="", command="tool", args=[], catalog_id=None
        ),
        _Server("zzzzzzzzzz", "Bare", False, "stdio", catalog_id=""),
    ]

    def service() -> SimpleNamespace:
        return SimpleNamespace(
            catalog_statuses=lambda: catalog,
            store=SimpleNamespace(list_mcp_servers=lambda: servers),
        )

    monkeypatch.setattr(mcp_status, "_service", service)
    console = MagicMock()
    mcp_status.print_mcp_status(console)
    printed = _prints(console)
    assert "Suggested MCP servers" in printed
    assert "Registered servers" in printed
    assert "2 custom server(s); 2 from catalog" in printed
    assert "enable/disable" in printed
    assert "No MCP servers" not in printed
    tables = [
        item
        for item in (call.args[0] for call in console.print.call_args_list)
        if isinstance(item, Table)
    ]
    assert len(tables) == 2
    assert len(tables[0].rows) == 4
    assert len(tables[1].rows) == 4

    def empty_service() -> SimpleNamespace:
        return SimpleNamespace(
            catalog_statuses=lambda: [],
            store=SimpleNamespace(list_mcp_servers=lambda: []),
        )

    monkeypatch.setattr(mcp_status, "_service", empty_service)
    console = MagicMock()
    mcp_status.print_mcp_status(console)
    printed = _prints(console)
    assert "No MCP servers registered yet." in printed
    tables = [
        item
        for item in (call.args[0] for call in console.print.call_args_list)
        if isinstance(item, Table)
    ]
    assert len(tables) == 1
    assert len(tables[0].rows) == 0

    catalog_only = [
        _Server(
            "catalog99",
            "Catalog",
            True,
            "stdio",
            command="bin",
            args=["--flag"],
            catalog_id="pymol",
        )
    ]

    def catalog_service() -> SimpleNamespace:
        return SimpleNamespace(
            catalog_statuses=lambda: [
                {"id": "pymol", "name": "PyMOL", "connected": False, "transport": "stdio"}
            ],
            store=SimpleNamespace(list_mcp_servers=lambda: catalog_only),
        )

    monkeypatch.setattr(mcp_status, "_service", catalog_service)
    console = MagicMock()
    mcp_status.print_mcp_status(console)
    printed = _prints(console)
    assert "custom server" not in printed
    assert "Registered servers" in printed
    tables = [
        item
        for item in (call.args[0] for call in console.print.call_args_list)
        if isinstance(item, Table)
    ]
    assert len(tables) == 2
    assert len(tables[1].rows) == 1
