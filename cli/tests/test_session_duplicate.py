"""Duplicate a chat: same settings and messages, a new session and workspace."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from agent_server.app import create_app


def test_duplicate_copies_messages_and_settings(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    app = create_app(store_path=tmp_path / "agent.db", allowed_hosts=["testserver"])
    with TestClient(app) as client:
        project = client.post("/v1/projects", json={"name": "P"}).json()
        created = client.post(
            "/v1/sessions",
            json={
                "title": "Binder design",
                "projectId": project["id"],
                "provider": "openrouter",
                "model": "deepseek/deepseek-v4-flash-0731",
            },
        )
        assert created.status_code == 201
        source = created.json()
        sid = source["id"]
        # Seed a transcript directly through the store (no model call).
        store = app.state.deps.store
        store.add_message(session_id=sid, role="user", content="Design a binder for GFP")
        store.add_message(session_id=sid, role="assistant", content="Here are three candidates.")
        store.add_message(session_id=sid, role="user", content="Rank them by pLDDT")
        # Pin the source: pin state must not carry over.
        client.patch(f"/v1/sessions/{sid}", json={"organizeLabel": "pinned"})

        duplicated = client.post(f"/v1/sessions/{sid}/duplicate", headers={"X-Sandwalk-Client": "ui"})
        assert duplicated.status_code == 201, duplicated.text
        clone = duplicated.json()

        assert clone["id"] != sid
        assert clone["title"] == "Binder design (copy)"
        assert clone["projectId"] == project["id"]
        assert clone["provider"] == "openrouter"
        assert clone["model"] == "deepseek/deepseek-v4-flash-0731"
        assert clone["organizeLabel"] is None
        assert clone["status"] == "idle"
        assert clone["workspacePath"] and clone["workspacePath"] != source["workspacePath"]

        original = client.get(f"/v1/sessions/{sid}/messages").json()["data"]
        copied = client.get(f"/v1/sessions/{clone['id']}/messages").json()["data"]
        assert [(m["role"], m["content"]) for m in copied] == [
            (m["role"], m["content"]) for m in original
        ]
        assert [m["createdAt"] for m in copied] == [m["createdAt"] for m in original]
        assert all(m["sessionId"] == clone["id"] for m in copied)

        # Source untouched.
        assert len(client.get(f"/v1/sessions/{sid}/messages").json()["data"]) == 3


def test_duplicate_accepts_a_custom_title_and_404s_on_unknown(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    app = create_app(store_path=tmp_path / "agent.db", allowed_hosts=["testserver"])
    with TestClient(app) as client:
        sid = client.post("/v1/sessions", json={"title": "Chat"}).json()["id"]
        clone = client.post(f"/v1/sessions/{sid}/duplicate", json={"title": "Variant B"})
        assert clone.status_code == 201
        assert clone.json()["title"] == "Variant B"
        missing = client.post("/v1/sessions/does-not-exist/duplicate")
        assert missing.status_code == 404
