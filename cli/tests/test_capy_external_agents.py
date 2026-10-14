"""Capy tools that bridge to Claude Code / Codex / OpenCode / fx."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent.external_agents import claude, fx
from agent_server.capy import CAPY_TOOL_NAMES, bind_capy_deps
from agent_server.pty_manager.types import PtyInfo
from agent_server.service import AgentService
from agent_server.store import AgentStore
from tools import capy as capy_tools


class _FakePty:
    """Stands in for PtyManager: records creates, runs coroutines inline."""

    def __init__(self) -> None:
        self.created: list[dict] = []

    async def create(self, *, session_id, cwd, title=None, cols=80, rows=24, startup=None):
        self.created.append({"session_id": session_id, "cwd": cwd, "title": title, "startup": startup})
        return PtyInfo(id="pty1", session_id=session_id, title=title or "T", cwd=cwd, cols=cols, rows=rows, pid=1)

    def run_sync(self, coro, *, timeout=20.0):
        return asyncio.run(coro)


@pytest.fixture
def env(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent_server.service.CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex"))
    monkeypatch.setenv("OPENCODE_DB", str(tmp_path / "none.db"))
    monkeypatch.setattr(fx, "binary", lambda: None)
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    (tmp_path / "claude").mkdir()
    (tmp_path / "codex").mkdir()
    store = AgentStore(tmp_path / "agent.db")
    service = AgentService(store)
    pty = _FakePty()
    bind_capy_deps(SimpleNamespace(store=store, service=service, pty_manager=pty))
    published: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        "agent_server.session_event_bus.session_event_bus.publish",
        lambda typ, payload: published.append((typ, payload)),
    )
    return SimpleNamespace(store=store, service=service, pty=pty, published=published, tmp=tmp_path)


def _claude_session(root: Path, cwd: str, sid: str = "12345678-aaaa-4bbb-8ccc-ddddeeeeffff") -> None:
    folder = root / "projects" / claude.encode_cwd(cwd)
    folder.mkdir(parents=True, exist_ok=True)
    rows = [
        {"type": "user", "uuid": "u1", "sessionId": sid, "cwd": cwd, "timestamp": "2026-10-01T10:00:00Z",
         "message": {"role": "user", "content": "plot the results"}},
        {"type": "assistant", "uuid": "a1", "parentUuid": "u1", "sessionId": sid, "cwd": cwd,
         "timestamp": "2026-10-01T10:00:01Z",
         "message": {"role": "assistant", "content": [{"type": "text", "text": "Done, see plot.png."}]}},
    ]
    (folder / f"{sid}.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def test_tools_are_registered_for_capy():
    for name in (
        "capy.list_external_sessions",
        "capy.import_external_session",
        "capy.launch_external_agent",
        "capy.handoff_session",
    ):
        assert name in CAPY_TOOL_NAMES


def test_list_and_import_round_trip(env):
    work = env.tmp / "work"
    work.mkdir()
    _claude_session(env.tmp / "claude", str(work))

    listed = capy_tools.capy_list_external_sessions(workspace_path=str(work))
    assert listed["ok"] is True
    assert [s["kind"] for s in listed["sessions"]] == ["claude"]
    assert "Installed: none" in listed["summary"]

    bad = capy_tools.capy_list_external_sessions(agent="gemini")
    assert bad["ok"] is False

    sid = listed["sessions"][0]["id"]
    imported = capy_tools.capy_import_external_session(agent="claude", session_id=sid, project_id="all")
    assert imported["ok"] is True, imported
    session = env.store.get_session(imported["sessionId"])
    assert session.source == "claude"
    assert session.title == "plot the results"
    assert [m.content for m in env.store.list_messages(session.id)] == ["plot the results", "Done, see plot.png."]

    missing = capy_tools.capy_import_external_session(agent="codex", session_id="nope")
    assert missing["ok"] is False and "not found" in missing["summary"]


def test_launch_uses_project_folder_and_opens_tab(env, monkeypatch):
    folder = env.tmp / "proj"
    folder.mkdir()
    monkeypatch.setattr("agent_server.external_agents_service.external_agents.binary_for", lambda kind: f"/opt/{kind}")

    result = capy_tools.capy_launch_external_agent(agent="opencode", workspace_path=str(folder), prompt="hi", project_id="all")
    assert result["ok"] is True, result
    assert env.pty.created[0]["cwd"] == str(folder.resolve())
    assert env.pty.created[0]["startup"] == "/opt/opencode --prompt hi"
    terminal = env.store.get_terminal(result["terminalId"])
    assert terminal is not None and terminal.title == "OpenCode"
    opened = [p for t, p in env.published if t == "ui.command" and p.get("action") == "open_item"]
    assert opened and opened[0]["itemId"] == terminal.id

    not_installed = capy_tools.capy_launch_external_agent(agent="fx", workspace_path=str(folder))
    # binary_for is patched to always find one; unknown agent still fails cleanly.
    assert capy_tools.capy_launch_external_agent(agent="gemini")["ok"] is False
    assert not_installed["ok"] is True


def test_handoff_writes_file_and_launches(env, monkeypatch):
    folder = env.tmp / "proj"
    folder.mkdir()
    monkeypatch.setattr("agent_server.external_agents_service.external_agents.binary_for", lambda kind: f"/opt/{kind}")
    chat = env.service.create_session(title="Weather", workspace_path=str(folder))
    env.store.add_message(session_id=chat.id, role="user", content="check the weather")
    env.store.add_message(session_id=chat.id, role="assistant", content="Sunny.")

    result = capy_tools.capy_handoff_session(session_id=chat.id, agent="codex")
    assert result["ok"] is True, result
    path = Path(result["path"])
    assert path.is_file() and "check the weather" in path.read_text(encoding="utf-8")
    created = env.pty.created[-1]
    assert created["startup"].startswith("/opt/codex ")
    assert "handoff-" in created["startup"]
    assert env.store.get_terminal(result["terminalId"]).origin_chat_id == chat.id

    assert capy_tools.capy_handoff_session(session_id="missing", agent="codex")["ok"] is False
