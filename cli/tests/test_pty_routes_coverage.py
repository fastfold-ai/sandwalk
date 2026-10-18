"""Session PTY HTTP routes with an in-memory terminal manager."""

from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from agent_server.routes import sessions_pty as pty_routes


class _Info:
    def __init__(self, pty_id="p1", session_id="host"):
        self.id = pty_id
        self.session_id = session_id

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "title": "shell",
            "cwd": "/tmp",
            "cols": 80,
            "rows": 24,
            "pid": 7,
            "status": "running",
        }


class _Live:
    output_log = b"ready\n"


class _Manager:
    def __init__(self):
        self.resize_result = _Info()
        self.remove_ok = True

    def list(self, session_id):
        return [_Info(session_id=session_id)]

    def get(self, session_id, pty_id):
        if pty_id == "missing":
            return None
        return _Info(pty_id, session_id)

    def get_session(self, session_id, pty_id):
        return _Live()

    async def create(self, **kwargs):
        return _Info(session_id=kwargs["session_id"])

    async def update_title(self, session_id, pty_id, title):
        if title == "gone":
            return None
        return _Info(pty_id, session_id)

    async def resize(self, session_id, pty_id, cols, rows):
        return self.resize_result

    async def remove(self, session_id, pty_id):
        if pty_id == "missing":
            return False
        return self.remove_ok

    async def attach(self, session_id, pty_id, websocket):
        return None


def _app(manager, store, service, api_key=""):
    app = FastAPI()
    deps = SimpleNamespace(
        store=store,
        service=service,
        pty_manager=manager,
        current_api_key=lambda: api_key,
        current_secret=lambda: "secret",
    )
    pty_routes.register_pty_routes(app, deps)
    return TestClient(app)


def test_pty_http_routes(monkeypatch):
    monkeypatch.setattr(pty_routes, "delete_snapshot", lambda session_id: None)
    monkeypatch.setattr(pty_routes, "read_snapshot", lambda session_id: b"disk")
    monkeypatch.setattr(pty_routes, "write_snapshot", lambda session_id, data: None)
    manager = _Manager()
    store = SimpleNamespace(
        get_session=lambda session_id: object() if session_id in {"chat-1", "chat-empty"} else None,
        get_terminal=lambda session_id: SimpleNamespace(workspace_path="/work")
        if session_id == "term_1"
        else None,
    )
    service = SimpleNamespace(
        ensure_workspace=lambda session_id: SimpleNamespace(
            workspace_path="/repo" if session_id == "chat-1" else None
        )
    )
    client = _app(manager, store, service)

    listed = client.get("/v1/sessions/host/pty")
    assert listed.status_code == 200
    assert listed.json()["data"][0]["id"] == "p1"
    assert client.get("/v1/sessions/missing/pty").status_code == 404
    assert client.get("/v1/sessions/term_missing/pty").status_code == 404
    assert client.get("/v1/sessions/term_1/pty").status_code == 200
    assert client.get("/v1/sessions/chat-1/pty").status_code == 200

    created = client.post("/v1/sessions/host/pty", json={"title": "lab", "startup": "pwd"})
    assert created.status_code == 201
    created_term = client.post("/v1/sessions/term_1/pty", json={})
    assert created_term.status_code == 201
    assert client.post("/v1/sessions/chat-1/pty", json={}).status_code == 201
    assert client.post("/v1/sessions/chat-empty/pty", json={}).status_code == 409

    updated = client.put(
        "/v1/sessions/host/pty/p1",
        json={"title": "renamed", "cols": 100, "rows": 40},
    )
    assert updated.status_code == 200
    assert client.put("/v1/sessions/host/pty/missing", json={"title": "x"}).status_code == 404
    assert client.put("/v1/sessions/host/pty/p1", json={"title": "gone"}).status_code == 404
    manager.resize_result = None
    assert client.put(
        "/v1/sessions/host/pty/p1",
        json={"cols": 90, "rows": 30},
    ).status_code == 404
    manager.resize_result = _Info()

    assert client.delete("/v1/sessions/host/pty/missing").status_code == 404
    manager.remove_ok = True
    assert client.delete("/v1/sessions/host/pty/p1").status_code == 204

    snap = client.get("/v1/sessions/host/snapshot")
    assert snap.status_code == 200
    assert snap.json()["data"]
    flushed = client.post("/v1/sessions/host/snapshot/flush")
    assert flushed.status_code == 204

    class _Quiet:
        output_log = b""

    manager.get_session = lambda session_id, pty_id: _Quiet()
    disk = client.get("/v1/sessions/chat-1/snapshot")
    assert disk.json()["data"]
    monkeypatch.setattr(pty_routes, "read_snapshot", lambda session_id: None)
    empty = client.get("/v1/sessions/chat-1/snapshot")
    assert empty.json()["data"] is None
    assert client.post("/v1/sessions/chat-1/snapshot/flush").status_code == 204


def test_pty_websocket_auth_and_missing(monkeypatch):
    manager = _Manager()
    store = SimpleNamespace(
        get_session=lambda session_id: None,
        get_terminal=lambda session_id: None,
    )
    service = SimpleNamespace(ensure_workspace=lambda session_id: SimpleNamespace(workspace_path=None))
    import pytest

    client = _app(manager, store, service, api_key="secret")
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/v1/sessions/host/pty/p1/connect"):
            pass

    open_client = _app(manager, store, service, api_key="")
    for path in (
        "/v1/sessions/missing/pty/p1/connect",
        "/v1/sessions/term_missing/pty/p1/connect",
        "/v1/sessions/host/pty/missing/connect",
    ):
        with pytest.raises(WebSocketDisconnect):
            with open_client.websocket_connect(path):
                pass
    with open_client.websocket_connect("/v1/sessions/host/pty/p1/connect"):
        pass
