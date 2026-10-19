"""Remaining run-pipeline and site-route coverage, with service, store, and HTTP faked."""

from __future__ import annotations

import asyncio
import threading
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from agent_server.models.sites import Site
from agent_server.routes import sites as site_routes
from agent_server.service import AgentService, run_pipeline
from agent_server.service.context import RunContext
from agent_server.title import TitleResult

SESSION_ID = "session-123"
RUN_ID = "run-abcdef"


class _Message:
    def __init__(self, role: str, content: str, message_id: str = "msg-1") -> None:
        self.id = message_id
        self.role = role
        self.content = content

    def model_dump(self, mode: str = "json", by_alias: bool = True) -> dict[str, str]:
        del mode, by_alias
        return {"id": self.id, "role": self.role, "content": self.content}


class _Session:
    def __init__(self, title_source: str = "auto", title: str = "Protein notes") -> None:
        self.title_source = title_source
        self.title = title

    def model_dump(self, mode: str = "json", by_alias: bool = True) -> dict[str, str]:
        del mode, by_alias
        return {"title": self.title, "titleSource": self.title_source}


class _Store:
    def __init__(self, session: _Session | None = None) -> None:
        self.session = session if session is not None else _Session()
        self.messages: list[_Message] = [_Message("user", "fold this protein", "msg-user")]
        self.events: list[dict[str, Any]] = []
        self.statuses: list[str] = []
        self.updated: dict[str, Any] | None = None
        self.update_result: _Session | None = _Session(title="Folded", title_source="auto")
        self.fail: str | None = None

    def list_messages(self, session_id: str) -> list[_Message]:
        del session_id
        if self.fail == "list":
            raise RuntimeError("list failed")
        return self.messages

    def get_session(self, session_id: str) -> _Session | None:
        del session_id
        if self.fail == "get":
            raise RuntimeError("get failed")
        return self.session

    def set_session_status(self, session_id: str, status: str) -> None:
        del session_id
        self.statuses.append(status)

    def append_event(self, **kwargs: Any) -> None:
        self.events.append(kwargs)

    def add_message(self, **kwargs: Any) -> _Message:
        return _Message(kwargs["role"], kwargs["content"], "msg-assistant")

    def update_session(self, session_id: str, **kwargs: Any) -> _Session | None:
        del session_id
        self.updated = kwargs
        if self.update_result is not None:
            self.update_result.title = kwargs["title"]
            self.update_result.title_source = kwargs["title_source"]
        return self.update_result


class _Emitter:
    def __init__(self, last_stream_at: float | None = None) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        if last_stream_at is not None:
            self.last_stream_at = last_stream_at

    def __call__(self, event: str, **payload: Any) -> None:
        self.calls.append((event, payload))


class _Admission:
    def __init__(self, error: BaseException | None = None) -> None:
        self.error = error
        self.released = 0
        self.waits: list[str] = []

    def acquire(self, on_wait: Any = None) -> None:
        if on_wait is not None:
            on_wait("parked")
            self.waits.append("parked")
        if self.error is not None:
            raise self.error

    def release(self) -> None:
        self.released += 1


class _Broker:
    def __init__(self, error: BaseException | None = None) -> None:
        self.error = error
        self.calls: list[tuple[str, str]] = []

    def cancel(self, session_id: str, reason: str = "") -> None:
        self.calls.append((session_id, reason))
        if self.error is not None:
            raise self.error


class _RecordingThread(threading.Thread):
    """Real thread for the executor; retitle threads are recorded and not started."""

    started: list[_RecordingThread] = []

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._retitle = str(kwargs.get("name", "")).startswith("retitle-")
        if self._retitle:
            super().__init__(name=kwargs.get("name"), daemon=bool(kwargs.get("daemon")))
            self.recorded_target = kwargs.get("target")
            self.recorded_args = kwargs.get("args", ())
            self.recorded_name = kwargs.get("name")
            self.recorded_daemon = kwargs.get("daemon")
            return
        super().__init__(*args, **kwargs)

    def start(self) -> None:
        if self._retitle:
            _RecordingThread.started.append(self)
            return
        super().start()


def _context() -> RunContext:
    return RunContext(
        mcp_servers=["mcp"],
        project_context="ctx",
        specialist_instructions="spec",
        allowed_skill_names=["skill"],
        allowed_tool_names=["tool"],
        sandbox_backend="builtin",
        provider="openai",
        model="gpt",
        openai_profile_id="profile",
        capy_mode=True,
    )


def _install_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    *,
    emitter: _Emitter,
    admission: _Admission,
    runner: Any,
) -> list[_RecordingThread]:
    def make_emitter(store: object, session_id: str, run_id: str) -> _Emitter:
        del store, session_id, run_id
        return emitter

    def build_context(store: object, session_id: str) -> RunContext:
        del store, session_id
        return _context()

    def admit() -> _Admission:
        return admission

    monkeypatch.setattr(run_pipeline, "make_event_emitter", make_emitter)
    monkeypatch.setattr(run_pipeline, "build_run_context", build_context)
    monkeypatch.setattr(run_pipeline, "run_existing_agent", runner)
    monkeypatch.setattr("agent_server.run_admission.run_admission", admit)
    _RecordingThread.started = []
    monkeypatch.setattr(run_pipeline.threading, "Thread", _RecordingThread)
    return _RecordingThread.started


def _execute(service: AgentService, content: str = "fold this protein") -> None:
    asyncio.run(
        service._execute_run(
            session_id=SESSION_ID,
            run_id=RUN_ID,
            content=content,
            workspace_path="/work/session",
        )
    )


def _runner_ok(service: AgentService):
    def run(*args: Any) -> str:
        ready, done = args[11], args[12]
        assert args[0] == "fold this protein"
        assert args[1] == "/work/session"
        assert args[4] == ["mcp"]
        assert args[5] == "ctx"
        assert args[8] == SESSION_ID
        assert args[13] == "openai"
        assert args[16] is True
        ready("runner")
        assert service._active_runners[SESSION_ID] == "runner"
        done()
        assert SESSION_ID not in service._active_runners
        done()
        return "assistant summary"

    return run


def _raise_cancelled(*_args: Any) -> str:
    raise asyncio.CancelledError


def _raise_interrupted(*_args: Any) -> str:
    raise InterruptedError("user stopped")


def _raise_interrupted_empty(*_args: Any) -> str:
    raise InterruptedError


def _raise_timeout(*_args: Any) -> str:
    raise TimeoutError("capacity queue")


def _raise_runtime(*_args: Any) -> str:
    raise RuntimeError("llm down")


def _event_types(store: _Store) -> list[str]:
    return [event["event_type"] for event in store.events]


def test_execute_run_completes_and_reports_stream_tail(monkeypatch: pytest.MonkeyPatch) -> None:
    store = _Store(_Session(title_source="auto", title="Protein notes"))
    service = AgentService(store)
    emitter = _Emitter(last_stream_at=12.5)
    admission = _Admission()
    started = _install_pipeline(
        monkeypatch, emitter=emitter, admission=admission, runner=_runner_ok(service)
    )

    _execute(service)

    assert admission.released == 1
    assert emitter.calls == [("activity", {"text": "parked", "kind": "capacity"})]
    assert store.statuses == ["idle"]
    assert _event_types(store) == ["assistant.message", "run.completed"]
    assert store.events[0]["payload"]["message"]["content"] == "assistant summary"
    assert store.events[1]["payload"] == {"messageId": "msg-assistant"}
    assert started == []


def test_execute_run_without_stream_timestamp_queues_retitle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _Store(_Session(title_source="pending", title="New chat"))
    service = AgentService(store)
    started = _install_pipeline(
        monkeypatch,
        emitter=_Emitter(),
        admission=_Admission(),
        runner=_runner_ok(service),
    )

    _execute(service)

    assert len(started) == 1
    thread = started[0]
    assert thread.recorded_daemon is True
    assert thread.recorded_name == f"retitle-{SESSION_ID[:8]}"
    assert thread.recorded_target == service._retitle_after_run
    assert thread.recorded_args == (SESSION_ID, RUN_ID, "fold this protein")
    assert store.statuses == ["idle"]


def test_execute_run_cancelled_clears_approvals(monkeypatch: pytest.MonkeyPatch) -> None:
    store = _Store()
    service = AgentService(store)
    broker = _Broker()
    admission = _Admission()
    _install_pipeline(
        monkeypatch, emitter=_Emitter(), admission=admission, runner=_raise_cancelled
    )

    def broker_factory() -> _Broker:
        return broker

    monkeypatch.setattr("agent.hitl.get_approval_broker", broker_factory)

    with pytest.raises(asyncio.CancelledError):
        _execute(service)

    assert broker.calls == [(SESSION_ID, "Run cancelled")]
    assert store.statuses == ["interrupted"]
    assert store.events[-1]["event_type"] == "run.interrupted"
    assert store.events[-1]["payload"] == {"reason": "Run cancelled"}
    assert admission.released == 1


def test_execute_run_cancelled_when_broker_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    store = _Store()
    service = AgentService(store)
    broker = _Broker(error=RuntimeError("broker down"))
    _install_pipeline(
        monkeypatch, emitter=_Emitter(), admission=_Admission(), runner=_raise_cancelled
    )

    def broker_factory() -> _Broker:
        return broker

    monkeypatch.setattr("agent.hitl.get_approval_broker", broker_factory)

    with pytest.raises(asyncio.CancelledError):
        _execute(service)

    assert store.statuses == ["interrupted"]
    assert store.events[-1]["payload"]["reason"] == "Run cancelled"


def test_execute_run_interrupted(monkeypatch: pytest.MonkeyPatch) -> None:
    store = _Store()
    service = AgentService(store)
    _install_pipeline(
        monkeypatch, emitter=_Emitter(), admission=_Admission(), runner=_raise_interrupted
    )

    _execute(service)

    assert store.statuses == ["interrupted"]
    assert store.events[-1]["payload"] == {"reason": "user stopped"}


def test_execute_run_interrupted_without_message(monkeypatch: pytest.MonkeyPatch) -> None:
    store = _Store()
    service = AgentService(store)
    _install_pipeline(
        monkeypatch,
        emitter=_Emitter(),
        admission=_Admission(),
        runner=_raise_interrupted_empty,
    )

    _execute(service)

    assert store.events[-1]["payload"] == {"reason": "Run interrupted"}


def test_execute_run_capacity_timeout_from_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    store = _Store()
    service = AgentService(store)
    admission = _Admission()
    _install_pipeline(
        monkeypatch, emitter=_Emitter(), admission=admission, runner=_raise_timeout
    )

    _execute(service)

    assert admission.released == 1
    assert store.statuses == ["error"]
    assert store.events[-1]["event_type"] == "run.failed"
    assert store.events[-1]["payload"] == {"error": "capacity queue"}


def test_execute_run_capacity_timeout_while_waiting(monkeypatch: pytest.MonkeyPatch) -> None:
    store = _Store()
    service = AgentService(store)

    def runner(*_args: Any) -> str:
        raise AssertionError("runner should stay parked")

    admission = _Admission(error=TimeoutError())
    _install_pipeline(monkeypatch, emitter=_Emitter(), admission=admission, runner=runner)

    _execute(service)

    assert admission.released == 0
    assert store.statuses == ["error"]
    assert store.events[-1]["payload"] == {
        "error": "This run waited too long for capacity."
    }


def test_execute_run_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    store = _Store()
    service = AgentService(store)
    _install_pipeline(
        monkeypatch, emitter=_Emitter(), admission=_Admission(), runner=_raise_runtime
    )

    _execute(service)

    assert store.statuses == ["error"]
    assert store.events[-1]["event_type"] == "run.failed"
    assert store.events[-1]["payload"]["error"] == (
        "Agent run failed. Check the server logs for details."
    )


def _history(*pairs: tuple[str, str]) -> list[_Message]:
    return [_Message(role, content, f"m{index}") for index, (role, content) in enumerate(pairs)]


def test_retitle_skips_settled_session() -> None:
    store = _Store(_Session(title_source="auto", title="Protein notes"))
    service = AgentService(store)

    service._retitle_after_run(SESSION_ID, RUN_ID, "fold this protein")

    assert store.updated is None
    assert store.events == []


def test_retitle_llm_title_persists(monkeypatch: pytest.MonkeyPatch) -> None:
    store = _Store(_Session(title_source="pending", title="New chat"))
    store.messages = _history(
        ("user", "fold this protein"),
        ("assistant", "starting"),
        ("user", "use the alphafold skill"),
        ("assistant", "folded"),
    )
    service = AgentService(store)
    seen: dict[str, Any] = {}

    def generate(history: list[dict[str, str]], fallback_query: str | None = None) -> TitleResult:
        seen["history"] = history
        seen["fallback"] = fallback_query
        return TitleResult(title="Fold proteins", final=True)

    monkeypatch.setattr("agent_server.title.generate_session_title", generate)

    service._retitle_after_run(SESSION_ID, RUN_ID, "fold this protein")

    assert seen["fallback"] == "fold this protein"
    assert seen["history"][0] == {"role": "user", "content": "fold this protein"}
    assert store.updated == {"title": "Fold proteins", "title_source": "auto"}
    assert store.events[-1]["event_type"] == "session.updated"
    assert store.events[-1]["payload"]["session"]["title"] == "Fold proteins"


def test_retitle_skips_empty_llm_title(monkeypatch: pytest.MonkeyPatch) -> None:
    store = _Store(_Session(title_source="pending", title="New chat"))
    store.messages = _history(
        ("user", "fold this protein"),
        ("assistant", "starting"),
        ("user", "again"),
        ("assistant", "done"),
    )
    service = AgentService(store)

    def generate(history: list[dict[str, str]], fallback_query: str | None = None) -> TitleResult:
        del history, fallback_query
        return TitleResult(title="", final=True)

    monkeypatch.setattr("agent_server.title.generate_session_title", generate)

    service._retitle_after_run(SESSION_ID, RUN_ID, "fold this protein")

    assert store.updated is None
    assert store.events == []


def test_retitle_fallback_when_update_is_missing() -> None:
    store = _Store(_Session(title_source="pending", title="New chat"))
    store.messages = _history(("user", "fold this protein"))
    store.update_result = None
    service = AgentService(store)

    service._retitle_after_run(SESSION_ID, RUN_ID, "fold this protein")

    assert store.updated == {"title": "fold this protein", "title_source": "pending"}
    assert store.events == []


def test_retitle_swallows_title_errors() -> None:
    store = _Store(_Session(title_source="pending", title="New chat"))
    store.fail = "list"
    service = AgentService(store)

    service._retitle_after_run(SESSION_ID, RUN_ID, "fold this protein")

    assert store.events == []


def test_retitle_swallows_lookup_errors() -> None:
    store = _Store(_Session(title_source="pending", title="New chat"))
    store.fail = "get"
    service = AgentService(store)

    service._retitle_after_run(SESSION_ID, RUN_ID, "fold this protein")

    assert store.updated is None


def test_site_error_maps_status() -> None:
    missing = site_routes._site_error(KeyError("missing site"))
    invalid = site_routes._site_error(ValueError("bad name"))
    failed = site_routes._site_error(RuntimeError("backend down"))

    assert missing.status_code == 404
    assert missing.detail == "missing site"
    assert invalid.status_code == 400
    assert invalid.detail == "bad name"
    assert failed.status_code == 500
    assert failed.detail == "Site operation failed."


def _sample_site(storage: Path, **updates: Any) -> Site:
    now = datetime(2026, 10, 18, tzinfo=UTC)
    payload: dict[str, Any] = {
        "id": "site-1",
        "name": "Demo",
        "slug": "demo",
        "status": "ready",
        "source_path": "/work/demo",
        "storage_path": str(storage),
        "content_sha256": "abc",
        "file_count": 2,
        "bytes": 12,
        "size_bytes": 12,
        "created_at": now,
        "updated_at": now,
    }
    payload.update(updates)
    return Site(**payload)


class _SiteStore:
    def __init__(self, site: Site) -> None:
        self.site = site
        self.visible = True

    def list_sites(self) -> list[Site]:
        if not self.visible:
            return []
        return [self.site]

    def get_site(self, site_id: str) -> Site | None:
        if not self.visible or site_id != self.site.id:
            return None
        return self.site


class _SitesService:
    def __init__(self, site: Site) -> None:
        self.site = site
        self.mode = "ok"
        self.calls: list[tuple[Any, ...]] = []
        self.publish_url: str | None = "https://sites.example/demo"

    def _raise(self) -> None:
        mode = self.mode
        self.mode = "ok"
        if mode == "missing":
            raise KeyError("missing site")
        if mode == "invalid":
            raise ValueError("bad name")
        if mode == "down":
            raise RuntimeError("backend down")

    def register(self, **kwargs: Any) -> Site:
        self.calls.append(("register", kwargs))
        self._raise()
        return self.site.model_copy(update={"name": kwargs["name"]})

    def rename(self, site_id: str, name: str) -> Site:
        self.calls.append(("rename", site_id, name))
        self._raise()
        return self.site.model_copy(update={"name": name})

    def delete(self, site_id: str) -> None:
        self.calls.append(("delete", site_id))
        self._raise()

    def create_preview(self, site_id: str) -> tuple[str, datetime]:
        self.calls.append(("preview", site_id))
        self._raise()
        return "/v1/sites/site-1/preview/ticket/", datetime(2026, 10, 18, tzinfo=UTC)

    def publish(self, site_id: str, slug: str | None = None) -> Site:
        self.calls.append(("publish", site_id, slug))
        self._raise()
        return self.site.model_copy(
            update={
                "slug": slug,
                "status": "published",
                "cloud_url": self.publish_url,
                "cloud_site_id": "cloud-1" if self.publish_url else None,
            }
        )

    def preview_site(self, site_id: str, token: str) -> Site | None:
        self.calls.append(("preview_site", site_id, token))
        if token != "ticket":
            return None
        return self.site


@pytest.fixture()
def sites_http(tmp_path: Path):
    (tmp_path / "index.html").write_text("<html>ok</html>", encoding="utf-8")
    (tmp_path / "app.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "blob.zzzx").write_text("xyz", encoding="utf-8")
    site = _sample_site(tmp_path)
    service = _SitesService(site)
    store = _SiteStore(site)
    app = FastAPI()
    site_routes.register_site_routes(app, SimpleNamespace(store=store, sites_service=service))
    with TestClient(app) as client:
        yield service, store, client


def _route(app: FastAPI, name: str):
    for route in app.routes:
        if getattr(route, "name", None) == name:
            return route.endpoint
    raise AssertionError(name)


def test_list_and_get_sites(sites_http) -> None:
    _service, store, client = sites_http

    listed = client.get("/v1/sites")
    assert listed.status_code == 200
    assert listed.json()["data"][0]["id"] == "site-1"

    found = client.get("/v1/sites/site-1")
    assert found.status_code == 200
    assert found.json()["name"] == "Demo"

    missing = client.get("/v1/sites/other")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Site not found."

    store.visible = False
    empty = client.get("/v1/sites")
    assert empty.status_code == 200
    assert empty.json()["data"] == []


def test_create_update_rename_and_delete_sites(sites_http) -> None:
    service, _store, client = sites_http
    created = client.post(
        "/v1/sites",
        json={"name": "Demo", "path": "/work/demo", "sessionId": "sess", "projectId": "proj"},
    )
    assert created.status_code == 201
    assert created.json()["name"] == "Demo"
    assert service.calls[-1][1]["source"] == "/work/demo"
    assert service.calls[-1][1]["session_id"] == "sess"
    assert service.calls[-1][1]["project_id"] == "proj"

    updated = client.put(
        "/v1/sites/site-1/content",
        json={"name": "Demo 2", "path": "/work/demo2"},
    )
    assert updated.status_code == 200
    assert service.calls[-1][1]["site_id"] == "site-1"

    renamed = client.patch("/v1/sites/site-1", json={"name": "Renamed"})
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Renamed"

    deleted = client.delete("/v1/sites/site-1")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True


@pytest.mark.parametrize(
    ("method", "path", "body", "mode", "status", "detail"),
    [
        ("post", "/v1/sites", {"name": "Demo", "path": "/work"}, "missing", 404, "missing site"),
        ("post", "/v1/sites", {"name": "Demo", "path": "/work"}, "invalid", 400, "bad name"),
        ("post", "/v1/sites", {"name": "Demo", "path": "/work"}, "down", 500, "Site operation failed."),
        ("put", "/v1/sites/site-1/content", {"name": "Demo", "path": "/work"}, "missing", 404, "missing site"),
        ("put", "/v1/sites/site-1/content", {"name": "Demo", "path": "/work"}, "invalid", 400, "bad name"),
        ("put", "/v1/sites/site-1/content", {"name": "Demo", "path": "/work"}, "down", 500, "Site operation failed."),
        ("patch", "/v1/sites/site-1", {"name": "Demo"}, "missing", 404, "missing site"),
        ("patch", "/v1/sites/site-1", {"name": "Demo"}, "invalid", 400, "bad name"),
        ("patch", "/v1/sites/site-1", {"name": "Demo"}, "down", 500, "Site operation failed."),
        ("delete", "/v1/sites/site-1", None, "missing", 404, "missing site"),
        ("delete", "/v1/sites/site-1", None, "invalid", 400, "bad name"),
        ("delete", "/v1/sites/site-1", None, "down", 500, "Site operation failed."),
        ("post", "/v1/sites/site-1/preview-ticket", None, "missing", 404, "missing site"),
        ("post", "/v1/sites/site-1/preview-ticket", None, "invalid", 400, "bad name"),
        ("post", "/v1/sites/site-1/preview-ticket", None, "down", 500, "Site operation failed."),
    ],
)
def test_site_mutations_map_errors(sites_http, method, path, body, mode, status, detail) -> None:
    service, _store, client = sites_http
    service.mode = mode
    response = client.request(method, path, json=body)
    assert response.status_code == status
    assert response.json()["detail"] == detail


def test_preview_ticket_and_publish(sites_http) -> None:
    service, _store, client = sites_http

    ticket = client.post("/v1/sites/site-1/preview-ticket")
    assert ticket.status_code == 200
    assert ticket.json()["url"] == "/v1/sites/site-1/preview/ticket/"
    assert ticket.json()["expiresAt"]

    published = client.post("/v1/sites/site-1/publish", json={"slug": "demo"})
    assert published.status_code == 200
    body = published.json()
    assert body["url"] == "https://sites.example/demo"
    assert body["cloudSiteId"] == "cloud-1"
    assert body["site"]["status"] == "published"

    service.publish_url = None
    untitled = client.post("/v1/sites/site-1/publish", json={})
    assert untitled.status_code == 200
    assert untitled.json()["url"] == ""
    assert untitled.json()["cloudSiteId"] is None


@pytest.mark.parametrize(
    ("mode", "status", "detail"),
    [
        ("missing", 404, "missing site"),
        ("invalid", 400, "bad name"),
        ("down", 502, "backend down"),
    ],
)
def test_publish_errors(sites_http, mode, status, detail) -> None:
    service, _store, client = sites_http
    service.mode = mode
    response = client.post("/v1/sites/site-1/publish", json={"slug": "demo"})
    assert response.status_code == status
    assert response.json()["detail"] == detail


def test_serve_preview_files(sites_http) -> None:
    _service, _store, client = sites_http
    base = "/v1/sites/site-1/preview/ticket"

    expired = client.get(f"{base.replace('ticket', 'nope')}/index.html")
    assert expired.status_code == 404
    assert expired.json()["detail"] == "Preview not found or expired."

    page = client.get(f"{base}/index.html")
    assert page.status_code == 200
    assert page.text == "<html>ok</html>"
    assert page.headers["x-content-type-options"] == "nosniff"
    assert page.headers["cache-control"] == "no-store"
    assert page.headers["content-type"].startswith("text/html")

    script = client.get(f"{base}/app.js")
    assert script.status_code == 200
    assert script.text == "console.log(1)"
    assert script.headers["cache-control"] == "public, max-age=3600"
    assert "javascript" in script.headers["content-type"]

    blob = client.get(f"{base}/blob.zzzx")
    assert blob.status_code == 200
    assert blob.headers["content-type"].startswith("application/octet-stream")

    missing_script = client.get(f"{base}/missing.js")
    assert missing_script.status_code == 404
    assert missing_script.json()["detail"] == "Preview asset not found."

    fallback = client.get(f"{base}/missing.js", headers={"accept": "text/html"})
    assert fallback.status_code == 200
    assert fallback.text == "<html>ok</html>"

    extensionless = client.get(f"{base}/about")
    assert extensionless.status_code == 200
    assert extensionless.text == "<html>ok</html>"


def test_serve_preview_empty_and_escaped_paths(sites_http) -> None:
    _service, _store, client = sites_http
    endpoint = _route(client.app, "serve_preview")
    request = SimpleNamespace(headers={"accept": ""})

    page = asyncio.run(endpoint("site-1", "ticket", "", request))
    assert Path(page.path).name == "index.html"
    assert page.headers["cache-control"] == "no-store"

    with pytest.raises(HTTPException) as caught:
        asyncio.run(endpoint("site-1", "ticket", "../secret.txt", request))
    assert caught.value.status_code == 404
    assert caught.value.detail == "Preview asset not found."
