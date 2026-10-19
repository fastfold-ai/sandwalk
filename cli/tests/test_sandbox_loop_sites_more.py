"""Extra coverage for sandbox routes, LoopRunMixin.run, and sites.manage."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException

from agent.loop.clarification import ClarificationNeeded
from agent.loop.run import LoopRunMixin
from agent_server.models import SessionSandboxStatus
from agent_server.routes import sessions_sandbox as sandbox_routes
from tools import sites as sites_tool

_CONTEXT = {"workspace_path": "/tmp/sandwalk-coverage-ws"}


async def _inline_to_thread(func, /, *args, **kwargs):
    return func(*args, **kwargs)


def _sandbox_status(session_id: str, status: str = "ready") -> SessionSandboxStatus:
    return SessionSandboxStatus(session_id=session_id, backend="builtin", status=status)


class _FakeSandboxService:
    def __init__(self, store):
        self.store = store

    def status(self, session_id: str) -> SessionSandboxStatus:
        if session_id == "missing":
            raise KeyError(session_id)
        return _sandbox_status(session_id)

    def start(self, session_id: str) -> SessionSandboxStatus:
        if session_id == "missing":
            raise KeyError(session_id)
        if session_id == "bad-value":
            raise ValueError("sandbox value")
        if session_id == "bad-runtime":
            raise RuntimeError("sandbox runtime")
        return _sandbox_status(session_id, "running")

    def stop(self, session_id: str) -> SessionSandboxStatus:
        if session_id == "missing":
            raise KeyError(session_id)
        return _sandbox_status(session_id, "stopped")

    def restart(self, session_id: str) -> SessionSandboxStatus:
        if session_id == "missing":
            raise KeyError(session_id)
        if session_id == "bad-value":
            raise ValueError("restart value")
        if session_id == "bad-runtime":
            raise RuntimeError("restart runtime")
        return _sandbox_status(session_id, "running")


def _sandbox_endpoint(monkeypatch, path: str, method: str):
    monkeypatch.setattr(sandbox_routes.asyncio, "to_thread", _inline_to_thread)
    monkeypatch.setattr(
        "agent_server.session_sandbox_service.SessionSandboxService",
        _FakeSandboxService,
    )
    app = FastAPI()
    sandbox_routes.register_session_sandbox_routes(app, SimpleNamespace(store=object()))
    for route in app.routes:
        methods = getattr(route, "methods", None) or set()
        if getattr(route, "path", None) == path and method in methods:
            return route.endpoint
    raise AssertionError(f"missing route {method} {path}")


def _invoke(endpoint, session_id: str):
    return asyncio.run(endpoint(session_id))


def _expect_http(endpoint, session_id: str, status_code: int, detail: str) -> None:
    with pytest.raises(HTTPException) as raised:
        _invoke(endpoint, session_id)
    assert raised.value.status_code == status_code
    assert raised.value.detail == detail


def test_get_and_stop_session_sandbox(monkeypatch) -> None:
    get_sandbox = _sandbox_endpoint(
        monkeypatch, "/v1/sessions/{session_id}/sandbox", "GET"
    )
    stop_sandbox = _sandbox_endpoint(
        monkeypatch, "/v1/sessions/{session_id}/sandbox/stop", "POST"
    )

    found = _invoke(get_sandbox, "sess-1")
    assert found.session_id == "sess-1"
    assert found.status == "ready"
    _expect_http(get_sandbox, "missing", 404, "Session not found.")

    stopped = _invoke(stop_sandbox, "sess-1")
    assert stopped.status == "stopped"
    _expect_http(stop_sandbox, "missing", 404, "Session not found.")


def test_start_and_restart_session_sandbox(monkeypatch) -> None:
    start_sandbox = _sandbox_endpoint(
        monkeypatch, "/v1/sessions/{session_id}/sandbox/start", "POST"
    )
    restart_sandbox = _sandbox_endpoint(
        monkeypatch, "/v1/sessions/{session_id}/sandbox/restart", "POST"
    )

    started = _invoke(start_sandbox, "sess-1")
    assert started.status == "running"
    _expect_http(start_sandbox, "missing", 404, "Session not found.")
    _expect_http(start_sandbox, "bad-value", 400, "sandbox value")
    _expect_http(start_sandbox, "bad-runtime", 400, "sandbox runtime")

    restarted = _invoke(restart_sandbox, "sess-1")
    assert restarted.status == "running"
    _expect_http(restart_sandbox, "missing", 404, "Session not found.")
    _expect_http(restart_sandbox, "bad-value", 400, "restart value")
    _expect_http(restart_sandbox, "bad-runtime", 400, "restart runtime")


class _Trajectory:
    def __init__(self, session_id: str = "sess-1", title: str = "Kinase screen"):
        self.session_id = session_id
        self.title = title
        self.model = None
        self.saved = False
        self.turns: list[tuple] = []

    def add_turn(self, query: str, answer: str, plan) -> None:
        self.turns.append((query, answer, plan))

    def save(self) -> None:
        self.saved = True


class _RunStore:
    def __init__(
        self,
        *,
        fail_ensure: bool = False,
        fail_failed_event: bool = False,
        fail_idle: bool = False,
    ):
        self.fail_ensure = fail_ensure
        self.fail_failed_event = fail_failed_event
        self.fail_idle = fail_idle
        self.statuses: list[str] = []
        self.events: list[str] = []

    def ensure_session(self, session_id: str, title: str, client_surface: str) -> None:
        if self.fail_ensure:
            raise RuntimeError("ensure failed")

    def add_message(self, session_id: str, role: str, content: str):
        return SimpleNamespace(id="msg-1")

    def set_session_status(self, session_id: str, status: str) -> None:
        if status == "idle" and self.fail_idle:
            raise RuntimeError("idle failed")
        self.statuses.append(status)

    def append_event(self, session_id: str, run_id: str, event_type: str, payload: dict) -> None:
        if event_type == "run.failed" and self.fail_failed_event:
            raise RuntimeError("event failed")
        self.events.append(event_type)


class _Runner:
    def __init__(self, result=None, error: Exception | None = None, poke: str = "no"):
        self._result = result
        self._error = error
        self._poke = poke

    def run(self, query, context, progress_callback=None):
        if progress_callback is not None and self._poke == "ok":
            progress_callback("activity", detail="working")
        if progress_callback is not None and self._poke == "boom":
            progress_callback("activity", detail="working")
            progress_callback("boom", detail="nope")
        if self._error is not None:
            raise self._error
        return self._result


def _result(summary: str = "answer", raw=None):
    return SimpleNamespace(summary=summary, plan=None, raw_results=raw)


class _Loop(LoopRunMixin):
    def __init__(self, store, trajectory, runner, *, emit_error=False, persist_error=False):
        self.store = store
        self.trajectory = trajectory
        self._runner = runner
        self.headless = True
        self.session = SimpleNamespace(current_model="stub-model")
        self.emit_error = emit_error
        self.persist_error = persist_error
        self.emitted: list[str] = []

    def ensure_workspace_path(self) -> str:
        return ""

    def _emit_store_progress(self, **kwargs) -> None:
        if self.emit_error:
            raise RuntimeError("emit failed")
        event = kwargs.get("event")
        if isinstance(event, str):
            self.emitted.append(event)

    def _persist_turn_to_store(self, query, answer, run_id=None, user_message_id=None) -> None:
        if self.persist_error:
            raise RuntimeError("persist failed")


def test_run_logs_store_startup_failure() -> None:
    loop = _Loop(
        _RunStore(fail_ensure=True),
        _Trajectory(),
        _Runner(result=_result()),
    )
    result = loop.run("query text", _CONTEXT)
    assert result.summary == "answer"
    assert loop.store.statuses == []
    assert loop.trajectory.saved is True


def test_run_progress_without_session_swallows_callback_errors() -> None:
    calls: list[str] = []

    def callback(event: str = "activity", **payload) -> None:
        calls.append(event)
        if event == "boom":
            raise RuntimeError("callback failed")

    silent = _Loop(
        _RunStore(),
        _Trajectory(session_id=""),
        _Runner(result=_result(), poke="ok"),
    )
    assert silent.run("query text", _CONTEXT, progress_callback=None).summary == "answer"

    noisy = _Loop(
        _RunStore(),
        _Trajectory(session_id=""),
        _Runner(result=_result(), poke="boom"),
    )
    assert noisy.run("query text", _CONTEXT, progress_callback=callback).summary == "answer"
    assert calls == ["activity", "boom", "turn_complete"]


def test_run_failure_swallows_status_and_progress_errors() -> None:
    loop = _Loop(
        _RunStore(fail_failed_event=True),
        _Trajectory(),
        _Runner(error=RuntimeError("run failed")),
        emit_error=True,
    )
    with pytest.raises(RuntimeError, match="run failed"):
        loop.run("query text", _CONTEXT)
    assert loop.store.statuses == ["running", "failed"]
    assert loop.store.events == ["run.started"]


def test_run_swallows_turn_complete_and_persist_errors() -> None:
    loop = _Loop(
        _RunStore(),
        _Trajectory(),
        _Runner(result=_result("done")),
        emit_error=True,
        persist_error=True,
    )
    result = loop.run("query text", _CONTEXT)
    assert result.summary == "done"
    assert loop.trajectory.saved is True
    assert loop.trajectory.model == "stub-model"
    assert loop.trajectory.turns == [("query text", "done", None)]


def test_run_swallows_clarification_store_errors() -> None:
    raw = {
        "clarification": {
            "clarification_needed": True,
            "question": "Which genome?",
            "missing": ["organism"],
            "suggestions": ["human"],
        }
    }
    loop = _Loop(
        _RunStore(fail_idle=True),
        _Trajectory(),
        _Runner(result=_result(raw=raw)),
    )
    with pytest.raises(ClarificationNeeded) as raised:
        loop.run("query text", _CONTEXT)
    assert raised.value.clarification.question == "Which genome?"
    assert loop.store.statuses == ["running"]


def test_is_placeholder_title_delegates() -> None:
    assert LoopRunMixin._is_placeholder_title("new chat") is True
    assert LoopRunMixin._is_placeholder_title("Kinase screen") is False
    assert LoopRunMixin._is_placeholder_title(None) is True


class _Site:
    def __init__(self, **fields):
        self.id = fields["id"]
        self.name = fields["name"]
        self.status = fields["status"]
        self.cloud_url = fields.get("cloud_url")
        self.origin_session_id = fields.get("origin_session_id")
        self.origin_project_id = fields.get("origin_project_id")

    def model_dump(self, mode: str = "json", by_alias: bool = True) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "cloudUrl": self.cloud_url,
        }


def _site(**overrides) -> _Site:
    fields = {
        "id": "site-1",
        "name": "Demo",
        "status": "draft",
        "cloud_url": None,
        "origin_session_id": "sess-origin",
        "origin_project_id": "proj-origin",
    }
    fields.update(overrides)
    return _Site(**fields)


class _SitesStore:
    def __init__(self, *, sites=None, site=None, error: Exception | None = None):
        self.sites = list(sites or [])
        self.site = site
        self.error = error
        self.closed = False

    def list_sites(self):
        if self.error is not None:
            raise self.error
        return self.sites

    def get_site(self, site_id: str):
        return self.site

    def close(self) -> None:
        self.closed = True


class _SitesService:
    def __init__(self, store):
        self.store = store
        self.registered = None
        self.published_slug = None
        self.deleted: list[str] = []

    def register(self, **kwargs):
        self.registered = kwargs
        return _site(name=kwargs.get("name") or "Created", id=kwargs.get("site_id") or "site-1")

    def rename(self, site_id: str, name: str):
        if name == "boom":
            raise ValueError("bad name")
        return _site(name=name, id=site_id)

    def create_preview(self, site_id: str):
        return (
            f"http://preview.local/{site_id}",
            datetime(2026, 10, 19, 12, 0, tzinfo=UTC),
        )

    def publish(self, site_id: str, slug: str | None = None):
        self.published_slug = slug
        if site_id == "missing":
            raise KeyError(site_id)
        return _site(
            name="Pub",
            id=site_id,
            status="published",
            cloud_url="https://pub.sandwalk.site",
        )

    def delete(self, site_id: str) -> None:
        if site_id == "slow":
            raise TimeoutError("timed out")
        if site_id == "down":
            raise RuntimeError("delete failed")
        self.deleted.append(site_id)


def _install_sites(monkeypatch, store: _SitesStore, service: _SitesService) -> None:
    def store_factory():
        return store

    def service_factory(bound_store):
        assert bound_store is store
        return service

    monkeypatch.setattr(sites_tool, "AgentStore", store_factory)
    monkeypatch.setattr(sites_tool, "SitesService", service_factory)


def test_sites_list_status_and_unknown(monkeypatch) -> None:
    listed = _site(id="site-a", name="Alpha")
    store = _SitesStore(sites=[listed])
    _install_sites(monkeypatch, store, _SitesService(store))

    listed_result = sites_tool.manage(action="list")
    assert listed_result["ok"] is True
    assert listed_result["summary"] == "1 site(s)."
    assert listed_result["sites"] == [
        {"id": "site-a", "name": "Alpha", "status": "draft", "cloudUrl": None}
    ]
    assert store.closed is True

    missing = _SitesStore(site=None)
    _install_sites(monkeypatch, missing, _SitesService(missing))
    missing_result = sites_tool.manage(action="status", site_id="nope")
    assert missing_result == {"ok": False, "summary": "Site not found."}
    assert missing.closed is True

    found_store = _SitesStore(site=_site(name="Beta", status="published"))
    _install_sites(monkeypatch, found_store, _SitesService(found_store))
    found = sites_tool.manage(action="info", site_id="site-1")
    assert found["ok"] is True
    assert found["summary"] == "Site 'Beta' is published."
    assert found["site"]["name"] == "Beta"

    unknown_store = _SitesStore()
    _install_sites(monkeypatch, unknown_store, _SitesService(unknown_store))
    unknown = sites_tool.manage(action="frobnicate")
    assert unknown == {"ok": False, "summary": "Unknown Sites action: frobnicate"}
    assert unknown_store.closed is True


def test_sites_update_rename_preview_publish_delete(monkeypatch) -> None:
    missing = _SitesStore(site=None)
    _install_sites(monkeypatch, missing, _SitesService(missing))
    assert sites_tool.manage(action="update", site_id="gone") == {
        "ok": False,
        "summary": "Site not found.",
    }

    existing = _site(name="Demo")
    store = _SitesStore(site=existing)
    service = _SitesService(store)
    _install_sites(monkeypatch, store, service)
    updated = sites_tool.manage(
        action="update",
        site_id="site-1",
        name="",
        path="dist",
        session_id="",
        project_id="",
    )
    assert updated["ok"] is True
    assert updated["summary"] == "Updated local site 'Demo'."
    assert service.registered is not None
    assert service.registered["name"] == "Demo"
    assert service.registered["session_id"] == "sess-origin"
    assert service.registered["project_id"] == "proj-origin"
    assert service.registered["source"] == "dist"
    assert service.registered["workspace_root"] == Path.cwd()
    assert store.closed is True

    rename_store = _SitesStore()
    _install_sites(monkeypatch, rename_store, _SitesService(rename_store))
    renamed = sites_tool.manage(action="rename", site_id="site-1", name="Renamed")
    assert renamed["ok"] is True
    assert renamed["summary"] == "Renamed site to 'Renamed'."
    assert renamed["site"]["name"] == "Renamed"

    preview_store = _SitesStore()
    _install_sites(monkeypatch, preview_store, _SitesService(preview_store))
    preview = sites_tool.manage(action="preview", site_id="site-1")
    assert preview["ok"] is True
    assert preview["url"] == "http://preview.local/site-1"
    assert preview["expires_at"] == "2026-10-19T12:00:00+00:00"
    assert "Preview ready until" in preview["summary"]

    publish_store = _SitesStore()
    publish_service = _SitesService(publish_store)
    _install_sites(monkeypatch, publish_store, publish_service)
    published = sites_tool.manage(action="publish", site_id="site-1", slug="  ")
    assert publish_service.published_slug is None
    assert published["ok"] is True
    assert published["url"] == "https://pub.sandwalk.site"
    assert published["summary"] == "Published 'Pub' at https://pub.sandwalk.site."

    named_store = _SitesStore()
    named_service = _SitesService(named_store)
    _install_sites(monkeypatch, named_store, named_service)
    sites_tool.manage(action="publish", site_id="site-1", slug=" demo ")
    assert named_service.published_slug == "demo"

    delete_store = _SitesStore()
    delete_service = _SitesService(delete_store)
    _install_sites(monkeypatch, delete_store, delete_service)
    deleted = sites_tool.manage(action="delete", site_id="site-1")
    assert deleted == {
        "ok": True,
        "summary": "Deleted local site site-1.",
        "deleted": True,
    }
    assert delete_service.deleted == ["site-1"]


def test_sites_manage_returns_tool_errors(monkeypatch) -> None:
    slow = _SitesStore()
    _install_sites(monkeypatch, slow, _SitesService(slow))
    timed_out = sites_tool.manage(action="delete", site_id="slow")
    assert timed_out == {"ok": False, "summary": "timed out"}
    assert slow.closed is True

    broken = _SitesStore()
    _install_sites(monkeypatch, broken, _SitesService(broken))
    renamed = sites_tool.manage(action="rename", site_id="site-1", name="boom")
    assert renamed == {"ok": False, "summary": "bad name"}

    missing = _SitesStore()
    _install_sites(monkeypatch, missing, _SitesService(missing))
    unpublished = sites_tool.manage(action="publish", site_id="missing", slug="demo")
    assert unpublished == {"ok": False, "summary": "'missing'"}

    down = _SitesStore(error=RuntimeError("list failed"))
    _install_sites(monkeypatch, down, _SitesService(down))
    listed = sites_tool.manage(action="list")
    assert listed == {"ok": False, "summary": "list failed"}
    assert down.closed is True
