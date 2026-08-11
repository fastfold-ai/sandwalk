from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent_server.app import create_app
from agent_server.main import run_server
from agent_server.store import AgentStore
from agent_server.workspace import WorkspaceConflictError, WorkspacePathError, WorkspaceService


def test_store_persists_sessions_messages_and_events(tmp_path: Path):
    path = tmp_path / "agent.db"
    store = AgentStore(path)
    session = store.create_session(title="Protein research", workspace_path=None)
    message = store.add_message(
        session_id=session.id,
        role="user",
        content="Fold this sequence",
    )
    event = store.append_event(
        session_id=session.id,
        run_id="run-1",
        event_type="run.started",
        payload={"messageId": message.id},
    )
    assert store.set_message_feedback(message.id, "up") is True
    assert store.get_session_feedback(session.id) == {message.id: "up"}

    reopened = AgentStore(path)
    persisted_session = reopened.get_session(session.id)
    assert persisted_session is not None
    assert persisted_session.id == session.id
    assert persisted_session.title == session.title
    assert reopened.list_messages(session.id) == [message]
    assert reopened.list_events(session.id, after_sequence=0) == [event]
    assert reopened.list_events(session.id, after_sequence=event.sequence) == []


def test_agent_server_health_and_session_contract(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SANDWALK_SETTINGS_PATH", str(tmp_path / "settings.json"))
    app = create_app(store_path=tmp_path / "agent.db")

    with TestClient(app) as client:
        health = client.get("/v1/health")
        assert health.status_code == 200
        assert health.json()["capabilities"]["apiVersion"] == "v1"
        assert health.json()["capabilities"]["localFilesystem"] is True
        assert health.json()["capabilities"]["skills"] is True
        assert health.json()["capabilities"]["integrations"] is True

        integrations = client.get("/v1/integrations")
        assert integrations.status_code == 200
        integration_keys = {item["key"] for item in integrations.json()["data"]}
        assert {
            "anthropic",
            "openai",
            "fastfold-cloud",
            "boltz",
            "modal",
            "langsmith",
            "nvidia",
            "opencode",
            "deepseek",
            "minimax",
            "mistral",
            "qwen",
            "together",
            "openrouter",
            "tavily",
        }.issubset(
            integration_keys
        )

        runtime_settings = client.get("/v1/settings/runtime")
        assert runtime_settings.status_code == 200
        assert runtime_settings.json()["provider"] in {"anthropic", "openai"}

        created_mcp = client.post(
            "/v1/mcp-servers",
            json={
                "name": "filesystem",
                "transport": "stdio",
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", str(tmp_path)],
            },
        )
        assert created_mcp.status_code == 201
        mcp_id = created_mcp.json()["id"]
        # Seeded catalog rows share the list, so match by id instead of position.
        listed = client.get("/v1/mcp-servers").json()["data"]
        assert mcp_id in {row["id"] for row in listed}
        assert client.delete(f"/v1/mcp-servers/{mcp_id}").status_code == 200
        remaining = client.get("/v1/mcp-servers").json()["data"]
        assert mcp_id not in {row["id"] for row in remaining}

        created = client.post(
            "/v1/sessions",
            json={"title": "Local session", "workspacePath": str(tmp_path)},
        )
        assert created.status_code == 201
        session = created.json()
        assert session["title"] == "Local session"
        assert session["workspacePath"] == str(tmp_path)

        sessions = client.get("/v1/sessions")
        assert sessions.status_code == 200
        assert sessions.json()["data"][0]["id"] == session["id"]

        renamed = client.patch(
            f"/v1/sessions/{session['id']}",
            json={"title": "Renamed session", "organizeLabel": "pinned"},
        )
        assert renamed.status_code == 200
        assert renamed.json()["title"] == "Renamed session"
        assert renamed.json()["organizeLabel"] == "pinned"

        search = client.get("/v1/sessions/search", params={"q": "Renamed"})
        assert search.status_code == 200
        assert [item["id"] for item in search.json()["data"]] == [session["id"]]

        messages = client.get(f"/v1/sessions/{session['id']}/messages")
        assert messages.status_code == 200
        assert messages.json() == {"data": [], "feedback": {}}

        # Persist a tool event and export via one-shot history endpoint.
        from agent_server.store import AgentStore

        store = AgentStore(tmp_path / "agent.db")
        store.append_event(
            session_id=session["id"],
            run_id="run-1",
            event_type="tool.started",
            payload={
                "name": "shell.run",
                "arguments": {"command": "echo hi"},
                "toolCallId": "tool-1",
            },
        )
        history = client.get(f"/v1/sessions/{session['id']}/events/history")
        assert history.status_code == 200
        body = history.json()
        tool_events = [item for item in body["data"] if item["type"] == "tool.started"]
        assert len(tool_events) == 1
        assert tool_events[0]["payload"]["name"] == "shell.run"
        assert tool_events[0]["payload"]["arguments"] == {"command": "echo hi"}

        deleted = client.delete(f"/v1/sessions/{session['id']}")
        assert deleted.status_code == 200
        assert deleted.json() == {"deleted": True}
        assert client.get(f"/v1/sessions/{session['id']}").status_code == 404


def test_agent_server_api_key_protects_v1_routes(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SANDWALK_SETTINGS_PATH", str(tmp_path / "settings.json"))
    app = create_app(store_path=tmp_path / "agent.db", api_key="test-secret")

    with TestClient(app) as client:
        # Health / discover stay public for connect + LAN probes.
        assert client.get("/v1/health").status_code == 200
        discover = client.get("/v1/discover")
        assert discover.status_code == 200
        body = discover.json()
        assert body["service"] == "sandwalk"
        assert body["authRequired"] is True
        assert body.get("deviceLabel")
        assert client.get("/v1/sessions").status_code == 401
        response = client.get(
            "/v1/sessions",
            headers={"authorization": "Bearer test-secret"},
        )
        assert response.status_code == 200


def test_auth_login_cookie_grants_access(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SANDWALK_SETTINGS_PATH", str(tmp_path / "settings.json"))
    from agent_server.auth_settings import AuthSettings, save_settings

    save_settings(
        AuthSettings(api_key="cookie-secret", auth_enabled=True, secret_key="unit-secret-key")
    )
    app = create_app(store_path=tmp_path / "agent.db")

    with TestClient(app) as client:
        assert client.get("/v1/sessions").status_code == 401
        login = client.post(
            "/v1/auth/login",
            json={"apiKey": "cookie-secret", "remember": True},
        )
        assert login.status_code == 200
        assert client.get("/v1/sessions").status_code == 200
        status = client.get("/v1/auth/status").json()
        assert status["authEnabled"] is True
        assert status["apiKeyConfigured"] is True
        assert status["authenticated"] is True

        client.post("/v1/auth/logout")
        status = client.get("/v1/auth/status").json()
        assert status["authEnabled"] is True
        assert status["authenticated"] is False


def test_workspace_service_confines_paths_and_detects_conflicts(tmp_path: Path):
    workspace = WorkspaceService(tmp_path)
    first = workspace.write("results/report.md", content="# Result")
    assert first.content == "# Result"
    assert {"results", "results/report.md"}.issubset(
        {item.path for item in workspace.list()}
    )

    updated = workspace.write(
        "results/report.md",
        content="# Updated",
        base_version=first.version,
    )
    assert updated.content == "# Updated"

    with pytest.raises(WorkspaceConflictError):
        workspace.write(
            "results/report.md",
            content="# Stale",
            base_version=first.version,
        )

    with pytest.raises(WorkspacePathError):
        workspace.read("../outside.txt")


def test_agent_server_workspace_file_contract(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SANDWALK_SETTINGS_PATH", str(tmp_path / "settings.json"))
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    app = create_app(store_path=tmp_path / "agent.db")

    with TestClient(app) as client:
        session = client.post(
            "/v1/sessions",
            json={"title": "Files", "workspacePath": str(workspace)},
        ).json()
        session_id = session["id"]

        written = client.put(
            f"/v1/sessions/{session_id}/files/content",
            json={"path": "notes/result.md", "content": "hello"},
        )
        assert written.status_code == 200
        assert written.json()["content"] == "hello"

        files = client.get(f"/v1/sessions/{session_id}/files")
        assert files.status_code == 200
        paths = {item["path"] for item in files.json()["data"]}
        assert {"notes", "notes/result.md"}.issubset(paths)

        uploaded = client.post(
            f"/v1/sessions/{session_id}/files/upload",
            files={"file": ("data.csv", b"a,b\n1,2\n", "text/csv")},
        )
        assert uploaded.status_code == 200
        assert uploaded.json()["path"] in {"data.csv", "uploads/data.csv"}

        deleted = client.delete(
            f"/v1/sessions/{session_id}/files",
            params={"path": "notes", "recursive": "true"},
        )
        assert deleted.status_code == 200
        assert not (workspace / "notes").exists()


def test_public_server_requires_api_key(monkeypatch, tmp_path):
    monkeypatch.setenv("SANDWALK_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("SANDWALK_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setattr("agent_server.main._serve", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "agent_server.app.create_app",
        lambda **kwargs: type(
            "App",
            (),
            {
                "state": type(
                    "State",
                    (),
                    {
                        "runtime_api_key": kwargs.get("api_key"),
                        "ui_dist": None,
                    },
                )()
            },
        )(),
    )

    with pytest.raises(ValueError, match="api-key"):
        run_server(host="0.0.0.0", public=True)

    # LAN defaults: --host 0.0.0.0 implies public; origins/hosts get safe defaults.
    run_server(host="0.0.0.0", api_key="secret")
    run_server(
        host="0.0.0.0",
        public=True,
        api_key="secret",
        allowed_origins=["https://agent.example.com"],
        allowed_hosts=["agent.example.com"],
    )
