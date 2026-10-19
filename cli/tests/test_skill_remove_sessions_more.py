"""Coverage for skill uninstall and session route errors."""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent.skills import remove as skill_remove
from agent_server.models import AgentSession, CompactSessionResponse
from agent_server.routes.sessions import register_session_routes
from agent_server.service import SessionBusyError


def _session() -> AgentSession:
    now = datetime.now(UTC)
    return AgentSession(id="s1", title="Chat", created_at=now, updated_at=now)


def test_skill_state_and_removal(tmp_path, monkeypatch) -> None:
    config = tmp_path / "config"
    global_dir = tmp_path / "skills"
    npx_dir = tmp_path / "npx-skills"
    npx_root = tmp_path / "npx-root"
    for path in (config, global_dir, npx_dir, npx_root):
        path.mkdir()
    monkeypatch.setattr(skill_remove._skills, "CONFIG_DIR", config)
    monkeypatch.setattr(skill_remove._skills, "GLOBAL_SKILLS_DIR", global_dir)
    monkeypatch.setattr(skill_remove._skills, "NPX_SKILLS_DIR", npx_dir)
    monkeypatch.setattr(skill_remove._skills, "NPX_INSTALL_ROOT", npx_root)
    monkeypatch.setattr(
        "agent.deepagents_runtime.skills_sources.invalidate_skill_sources_cache",
        lambda: None,
    )

    assert skill_remove._read_skill_state() == {"version": 1, "disabled": []}
    state_path = skill_remove._skill_state_path()
    state_path.write_text("{", encoding="utf-8")
    assert skill_remove._read_skill_state()["disabled"] == []
    state_path.write_text("[]", encoding="utf-8")
    assert skill_remove._read_skill_state()["disabled"] == []
    state_path.write_text('{"version": 2, "disabled": [" ok ", ""]}', encoding="utf-8")
    assert skill_remove._read_skill_state()["disabled"] == [" ok "]

    info = SimpleNamespace(name="Firecrawl")
    monkeypatch.setattr(skill_remove._skills, "iter_skills", lambda _root: {"firecrawl-cli": info})
    monkeypatch.setattr(
        skill_remove._skills,
        "_resolve_skill_key",
        lambda name, _skills: "firecrawl-cli" if name == "firecrawl" else None,
    )
    monkeypatch.setattr(
        skill_remove._skills,
        "_normalize_skill_lookup",
        lambda value: str(value or "").strip().lower(),
    )
    missing = skill_remove.set_skill_enabled("nope", True)
    assert missing["ok"] is False
    enabled = skill_remove.set_skill_enabled("firecrawl", False)
    assert enabled["ok"] is True
    assert "firecrawl-cli" in skill_remove._read_skill_state()["disabled"]
    skill_remove._clear_skill_enabled_state(set())
    skill_remove._clear_skill_enabled_state({"other"})
    skill_remove._clear_skill_enabled_state({"firecrawl-cli", "Firecrawl", " ok "})
    assert skill_remove._read_skill_state()["disabled"] == []

    bundled = global_dir / "bundled"
    bundled.mkdir()
    (bundled / "SKILL.md").write_text("---\n", encoding="utf-8")
    npx_skill = npx_dir / "npx-one"
    npx_skill.mkdir()
    (npx_skill / "SKILL.md").write_text("---\n", encoding="utf-8")
    (npx_root / "skills-lock.json").write_text("{}", encoding="utf-8")
    project = tmp_path / "proj"
    claude = project / ".claude" / "skills" / "local"
    claude.mkdir(parents=True)
    (claude / "SKILL.md").write_text("---\n", encoding="utf-8")
    (project / "skills-lock.json").write_text('{"skills": {"local": {}}}', encoding="utf-8")

    original_rmtree = shutil.rmtree

    def fail_once(path):
        if path.name == "bundled":
            raise OSError("busy")
        original_rmtree(path)

    monkeypatch.setattr(skill_remove.shutil, "rmtree", fail_once)
    removed = skill_remove.remove_all_skills(project_root=project)
    assert "npx-one" in removed["removed"]
    assert "local" in removed["removed"]

    target = global_dir / "gone"
    target.mkdir()
    monkeypatch.setattr(skill_remove._skills, "_scan_dir", lambda _dest, _kind: {})
    monkeypatch.setattr(skill_remove._skills, "_resolve_skill_key", lambda _name, _installed: None)
    def refuse(_path):
        raise OSError("no")

    monkeypatch.setattr(skill_remove.shutil, "rmtree", refuse)
    failed = skill_remove.remove_skill("gone", dest=global_dir)
    assert failed["ok"] is False
    monkeypatch.setattr(skill_remove.shutil, "rmtree", original_rmtree)
    (target / "SKILL.md").write_text("---\n", encoding="utf-8")
    monkeypatch.setattr(
        skill_remove._skills,
        "_read_manifest",
        lambda _dest: {"skills": {"gone": {}}},
    )
    monkeypatch.setattr(skill_remove._skills, "_write_manifest", lambda _dest, _manifest: None)
    removed_one = skill_remove.remove_skill("gone", dest=global_dir)
    assert removed_one["ok"] is True, removed_one
    assert skill_remove.remove_skill("missing", dest=global_dir)["ok"] is False


def test_session_routes_cover_list_and_errors() -> None:
    session = _session()
    calls: list[str] = []

    class Service:
        def create_session(self, **kwargs):
            calls.append("create")
            if kwargs.get("title") == "bad":
                raise ValueError("bad title")
            return session

        def duplicate_session(self, session_id, **kwargs):
            if session_id == "missing":
                raise KeyError(session_id)
            if session_id == "bad":
                raise ValueError("bad")
            return session

        def update_session(self, **kwargs):
            if kwargs["session_id"] == "missing":
                raise KeyError("missing")
            if kwargs["session_id"] == "bad":
                raise ValueError("bad")
            return session

        def auto_title_session(self, session_id, **kwargs):
            if session_id == "missing":
                raise KeyError(session_id)
            return session

        async def delete_session(self, session_id):
            return session_id != "missing"

        def interrupt(self, _session_id):
            return True

        def compact_session(self, session_id, **kwargs):
            if session_id == "missing":
                raise KeyError(session_id)
            if session_id == "busy":
                raise SessionBusyError("busy")
            if session_id == "bad":
                raise ValueError("bad")
            return CompactSessionResponse(turns_before=4, turns_after=2, summary="ok")

        def submit_approvals(self, session_id, **kwargs):
            if session_id == "lookup":
                raise LookupError("stale")
            if session_id == "bad":
                raise ValueError("bad")
            if session_id == "missing":
                raise KeyError(session_id)
            return {"accepted": True, "interrupt_id": "i1"}

    store = SimpleNamespace(
        list_sessions_by_ids=lambda ids: [session] if ids else [],
        get_session_by_source=lambda source: session if source == "capy" else None,
        sessions_revision=lambda: "1:0:0",
        search_sessions=lambda query, limit=50: [session],
        get_session=lambda session_id: None if session_id == "missing" else session,
    )
    deps = SimpleNamespace(
        store=store,
        service=Service(),
        list_visible_sessions=lambda project_id: [session],
        store_for_session=lambda session_id: store,
    )
    app = FastAPI()
    register_session_routes(app, deps)
    client = TestClient(app)

    assert client.get("/v1/sessions", params={"ids": "s1, ,s2"}).status_code == 200
    assert client.get("/v1/sessions", params={"source": "capy"}).json()["data"][0]["id"] == "s1"
    assert client.get("/v1/sessions", params={"projectId": "p"}).status_code == 200
    assert client.get("/v1/sessions/revision").json()["revision"] == "1:0:0"
    assert client.get("/v1/sessions/search", params={"q": "chat"}).status_code == 200
    assert client.post("/v1/sessions", json={"title": "Hi"}).status_code == 201
    assert client.post("/v1/sessions", json={"title": "bad"}).status_code == 400
    assert client.post("/v1/sessions/s1/duplicate", json={}).status_code == 201
    assert client.post("/v1/sessions/missing/duplicate", json={"title": "Copy"}).status_code == 404
    assert client.post("/v1/sessions/bad/duplicate").status_code == 400
    assert client.get("/v1/sessions/s1").status_code == 200
    assert client.get("/v1/sessions/missing").status_code == 404
    assert client.patch("/v1/sessions/s1", json={"clearLlm": True, "clearProjectId": True}).status_code == 200
    assert client.patch("/v1/sessions/missing", json={"title": "x"}).status_code == 404
    assert client.patch("/v1/sessions/bad", json={"title": "x"}).status_code == 400
    assert client.post("/v1/sessions/s1/title/auto", json={}).status_code == 200
    assert client.post("/v1/sessions/missing/title/auto").status_code == 404
    assert client.delete("/v1/sessions/s1").status_code == 200
    assert client.delete("/v1/sessions/missing").status_code == 404
    assert client.post("/v1/sessions/s1/interrupt").json()["interrupted"] is True
    assert client.post("/v1/sessions/missing/interrupt").status_code == 404
    assert client.post("/v1/sessions/s1/compact", json={"instructions": "shorter"}).status_code == 200
    assert client.post("/v1/sessions/missing/compact").status_code == 404
    assert client.post("/v1/sessions/busy/compact").status_code == 409
    assert client.post("/v1/sessions/bad/compact").status_code == 400
    approvals = {"decisions": [{"type": "approve"}]}
    assert client.post("/v1/sessions/s1/approvals", json=approvals).status_code == 200
    assert client.post("/v1/sessions/missing/approvals", json=approvals).status_code == 404
    assert client.post("/v1/sessions/lookup/approvals", json=approvals).status_code == 409
    assert client.post("/v1/sessions/bad/approvals", json=approvals).status_code == 400
    assert "create" in calls
