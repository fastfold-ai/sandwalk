"""HTTP surface for Claude Code / Codex / OpenCode / fx interop."""

from __future__ import annotations

import json
import os
import stat
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent.external_agents import claude, fx
from agent_server import external_agents_service as svc

SYSTEM_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"


def _with_fake_bin(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PATH", f"{tmp_path / 'bin'}{os.pathsep}{SYSTEM_PATH}")


@pytest.fixture
def api(tmp_path: Path, monkeypatch):
    from agent_server.app import create_app

    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex"))
    monkeypatch.setenv("OPENCODE_DB", str(tmp_path / "none.db"))
    monkeypatch.setenv("HERMES_STATE_DB", str(tmp_path / "hermes-none.db"))
    monkeypatch.setattr(fx, "binary", lambda: None)
    # System dirs only: the developer's real claude/codex/fx must not leak in.
    # Tests that need an "agent" prepend a fake one.
    monkeypatch.setenv("PATH", SYSTEM_PATH)
    (tmp_path / "claude").mkdir()
    (tmp_path / "codex").mkdir()
    app = create_app(store_path=tmp_path / "agent.db", allowed_hosts=["testserver"])
    with TestClient(app) as client:
        yield client


def _claude_session(root: Path, cwd: str, sid: str = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee") -> None:
    folder = root / "projects" / claude.encode_cwd(cwd)
    folder.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "type": "user",
            "uuid": "u1",
            "sessionId": sid,
            "cwd": cwd,
            "timestamp": "2026-10-01T10:00:00.000Z",
            "message": {"role": "user", "content": "summarize the repo"},
        },
        {
            "type": "assistant",
            "uuid": "a1",
            "parentUuid": "u1",
            "sessionId": sid,
            "cwd": cwd,
            "timestamp": "2026-10-01T10:00:01.000Z",
            "message": {
                "role": "assistant",
                "model": "claude-opus-5-5",
                "content": [
                    {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "ls"}},
                    {"type": "tool_use", "id": "t2", "name": "Read", "input": {"file_path": "README.md"}},
                ],
            },
        },
        {
            "type": "assistant",
            "uuid": "a2",
            "parentUuid": "a1",
            "sessionId": sid,
            "cwd": cwd,
            "timestamp": "2026-10-01T10:00:03.000Z",
            "message": {"role": "assistant", "content": [{"type": "text", "text": "It is a CLI."}]},
        },
    ]
    (folder / f"{sid}.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def test_list_reports_installed_agents_and_sessions_for_cwd(api, tmp_path: Path):
    cwd = tmp_path / "work"
    cwd.mkdir()
    _claude_session(tmp_path / "claude", str(cwd))

    body = api.get("/v1/external-agents", params={"cwd": str(cwd)}).json()
    kinds = {a["kind"]: a for a in body["agents"]}
    assert set(kinds) == {"claude", "codex", "opencode", "fx", "hermes"}
    assert kinds["fx"]["installed"] is False
    assert [s["kind"] for s in body["sessions"]] == ["claude"]
    assert body["sessions"][0]["title"] == "summarize the repo"
    assert body["sessions"][0]["label"] == "Claude Code"

    # Unknown kind is a 400, not a crash.
    assert api.get("/v1/external-agents", params={"kind": "gemini"}).status_code == 400
    # Agents only, no session scan.
    quick = api.get("/v1/external-agents", params={"sessions": "false"}).json()
    assert quick["sessions"] == []


def test_import_creates_seeded_session_in_same_folder(api, tmp_path: Path):
    cwd = tmp_path / "work"
    cwd.mkdir()
    _claude_session(tmp_path / "claude", str(cwd))
    sid = api.get("/v1/external-agents", params={"cwd": str(cwd)}).json()["sessions"][0]["id"]

    resp = api.post("/v1/external-agents/import", json={"kind": "claude", "sessionId": sid})
    assert resp.status_code == 201, resp.text
    session = resp.json()
    assert session["source"] == "claude"
    assert session["sourceLabel"].startswith("Claude Code · ")
    assert session["title"] == "Claude Code · summarize the repo"
    assert session["titleSource"] == "user"
    assert Path(session["workspacePath"]).resolve() == cwd.resolve()

    messages = api.get(f"/v1/sessions/{session['id']}/messages").json()["data"]
    assert [m["role"] for m in messages] == ["user", "assistant", "assistant"]
    assert messages[0]["content"] == "summarize the repo"
    assert "- Bash ls" in messages[1]["content"] and "- Read README.md" in messages[1]["content"]
    assert messages[2]["content"] == "It is a CLI."
    # Order is preserved by created_at even when source timestamps collide.
    stamps = [m["createdAt"] for m in messages]
    assert stamps == sorted(stamps)


def test_import_from_home_directory_gets_a_private_workspace(api, tmp_path: Path, monkeypatch):
    """A CLI session run from ``~`` must not make ~ the chat's workspace.

    The Files panel lists the workspace recursively; on a home directory that
    walk starved the whole server. Fall back to Sandwalk's own per-session
    folder instead.
    """
    home = tmp_path / "home"
    home.mkdir()
    # Patch the service's own seam, not `Path.home`: a global patch leaks into
    # `agent.config.CONFIG_DIR` when that module first imports on this worker.
    monkeypatch.setattr(svc, "_home_dir", lambda: home.resolve())
    _claude_session(tmp_path / "claude", str(home), sid="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
    sid = api.get("/v1/external-agents", params={"cwd": str(home)}).json()["sessions"][0]["id"]

    session = api.post("/v1/external-agents/import", json={"kind": "claude", "sessionId": sid}).json()
    ws = Path(session["workspacePath"]).resolve()
    assert ws != home.resolve()
    assert session["id"] in str(ws)  # Sandwalk's default per-session workspace

    # The imported chat shows up in the normal session list.
    listed = api.get("/v1/sessions").json()["data"]
    assert any(item["id"] == session["id"] for item in listed)


def test_import_unknown_session_is_400(api):
    resp = api.post("/v1/external-agents/import", json={"kind": "codex", "sessionId": "nope"})
    assert resp.status_code == 400
    assert "not found" in resp.json()["detail"]


def test_import_falls_back_to_default_workspace_when_cwd_is_gone(api, tmp_path: Path):
    gone = str(tmp_path / "deleted-folder")
    _claude_session(tmp_path / "claude", gone)
    sid = api.get("/v1/external-agents", params={"kind": "claude"}).json()["sessions"][0]["id"]
    session = api.post("/v1/external-agents/import", json={"kind": "claude", "sessionId": sid}).json()
    assert session["workspacePath"]
    assert session["workspacePath"] != gone


def _fake_binary(tmp_path: Path, name: str) -> Path:
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    script = bindir / name
    # Stay in the foreground longer than the probe interval. A 2s sleep
    # exits before the next allowed probe on a slow CI shell startup.
    script.write_text("#!/bin/sh\necho FAKE-$0 \"$@\"\nsleep 30\n", encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script


def test_launch_opens_terminal_with_startup_command(api, tmp_path: Path, monkeypatch):
    fake = _fake_binary(tmp_path, "codex")
    _with_fake_bin(monkeypatch, tmp_path)
    work = tmp_path / "proj"
    work.mkdir()

    resp = api.post(
        "/v1/external-agents/launch",
        json={"kind": "codex", "workspacePath": str(work), "prompt": "hello there"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["kind"] == "codex"
    assert body["command"].startswith(str(fake))
    assert "'hello there'" in body["command"]
    assert body["terminal"]["title"] == "Codex"
    assert Path(body["terminal"]["workspacePath"]).resolve() == work.resolve()
    assert body["pty"]["sessionId"] == body["terminal"]["id"]
    assert body["pty"]["status"] == "running"

    # The row exists like any other terminal and the PTY is attached to it.
    terminals = api.get("/v1/terminals").json()["data"]
    assert any(t["id"] == body["terminal"]["id"] for t in terminals)
    ptys = api.get(f"/v1/sessions/{body['terminal']['id']}/pty").json()["data"]
    assert [p["id"] for p in ptys] == [body["pty"]["id"]]
    api.delete(f"/v1/sessions/{body['terminal']['id']}/pty/{body['pty']['id']}")


def test_launch_without_binary_is_400(api, tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PATH", SYSTEM_PATH)
    resp = api.post("/v1/external-agents/launch", json={"kind": "fx", "workspacePath": str(tmp_path)})
    assert resp.status_code == 400
    assert "not installed" in resp.json()["detail"]


def test_handoff_writes_markdown_and_launches(api, tmp_path: Path, monkeypatch):
    _fake_binary(tmp_path, "claude")
    _with_fake_bin(monkeypatch, tmp_path)
    work = tmp_path / "proj"
    work.mkdir()
    created = api.post("/v1/sessions", json={"title": "Weather plan", "workspacePath": str(work)}).json()
    sid = created["id"]
    # Seed two turns directly in the store (no model run).
    store = api.app.state.deps.store
    store.add_message(session_id=sid, role="user", content="check the weather")
    store.add_message(session_id=sid, role="assistant", content="Sunny all week.")

    resp = api.post(f"/v1/sessions/{sid}/handoff", json={"kind": "claude", "launch": True})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    path = Path(body["path"])
    assert path.is_file() and path.parent == work / ".sandwalk"
    text = path.read_text(encoding="utf-8")
    assert "# Weather plan" in text and "check the weather" in text and "Sunny all week." in text
    assert body["messages"] == 2
    assert ".sandwalk/handoff-" in body["prompt"]
    assert body["terminal"]["originChatId"] == sid
    assert body["command"].endswith("'") and "Sandwalk transcript" in body["command"]
    api.delete(f"/v1/sessions/{body['terminal']['id']}/pty/{body['pty']['id']}")


def test_handoff_without_launch_only_writes_file(api, tmp_path: Path):
    work = tmp_path / "proj"
    work.mkdir()
    sid = api.post("/v1/sessions", json={"title": "T", "workspacePath": str(work)}).json()["id"]
    body = api.post(f"/v1/sessions/{sid}/handoff", json={"kind": "opencode", "launch": False}).json()
    assert Path(body["path"]).is_file()
    assert "terminal" not in body
    assert api.post("/v1/sessions/missing/handoff", json={"kind": "fx"}).status_code == 404


def test_startup_command_resume_variants(monkeypatch):
    monkeypatch.setattr(svc.external_agents, "binary_for", lambda kind: f"/bin/{kind}")
    assert svc.startup_command("claude", resume_id="abc") == "/bin/claude --resume abc"
    assert svc.startup_command("codex", resume_id="abc") == "/bin/codex resume abc"
    assert svc.startup_command("opencode", resume_id="abc") == "/bin/opencode -s abc"
    assert svc.startup_command("fx", resume_id="abc") == "/bin/fx resume abc"
    assert svc.startup_command("fx", prompt="hi there") == "/bin/fx 'hi there'"
    assert svc.startup_command("hermes", resume_id="abc") == "/bin/hermes --resume abc"
    assert svc.startup_command("hermes", prompt="hi there") == "/bin/hermes chat -q 'hi there'"


def test_pty_agent_detection_sees_foreground_process(api, tmp_path: Path, monkeypatch):
    """A PTY whose foreground process is named ``claude`` reports agent=claude."""
    _fake_binary(tmp_path, "claude")
    _with_fake_bin(monkeypatch, tmp_path)
    work = tmp_path / "proj"
    work.mkdir()
    body = api.post("/v1/external-agents/launch", json={"kind": "claude", "workspacePath": str(work)}).json()
    tid, pid = body["terminal"]["id"], body["pty"]["id"]
    seen = None
    deadline = time.time() + 6
    while time.time() < deadline:
        rows = api.get(f"/v1/sessions/{tid}/pty").json()["data"]
        if rows and rows[0].get("agent") == "claude":
            seen = rows[0]
            break
        time.sleep(0.25)
    api.delete(f"/v1/sessions/{tid}/pty/{pid}")
    assert seen is not None, "agent was never detected in the foreground"
    assert seen["agentCwd"] is None or Path(seen["agentCwd"]).name == "proj"


def test_handoff_native_writes_codex_rollout_and_resumes(api, tmp_path: Path, monkeypatch):
    _fake_binary(tmp_path, "codex")
    _with_fake_bin(monkeypatch, tmp_path)
    work = tmp_path / "proj"
    work.mkdir()
    sid = api.post("/v1/sessions", json={"title": "Native", "workspacePath": str(work)}).json()["id"]
    store = api.app.state.deps.store
    store.add_message(session_id=sid, role="user", content="hello")
    store.add_message(session_id=sid, role="assistant", content="hi")

    body = api.post(f"/v1/sessions/{sid}/handoff", json={"kind": "codex", "native": True, "launch": True}).json()
    assert body["native"] is True
    assert Path(body["nativePath"]).is_file()
    assert Path(body["nativePath"]).name.endswith(f"-{body['resumeId']}.jsonl")
    assert body["command"].endswith(f"resume {body['resumeId']}")
    # Markdown fallback is still there.
    assert Path(body["path"]).is_file()
    api.delete(f"/v1/sessions/{body['terminal']['id']}/pty/{body['pty']['id']}")

    # Native is Claude/Codex only.
    resp = api.post(f"/v1/sessions/{sid}/handoff", json={"kind": "opencode", "native": True, "launch": False})
    assert resp.status_code == 400 and "no native session import" in resp.json()["detail"]
