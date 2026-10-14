"""Readers for Claude Code, Codex, OpenCode, and fx sessions.

Fixtures are short synthetic copies of each tool's real shape. Nothing here
reads the developer's own ``~/.claude`` / ``~/.codex`` / OpenCode database.
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import pytest

from agent import external_agents as ea
from agent.external_agents import claude, codex, fx, opencode
from agent.external_agents.handoff import handoff_markdown, launch_argv, write_handoff

# --- Claude Code ------------------------------------------------------------


def _claude_fixture(root: Path, cwd: str, session_id: str = "11111111-2222-4333-8444-555555555555") -> Path:
    folder = root / "projects" / claude.encode_cwd(cwd)
    folder.mkdir(parents=True)
    path = folder / f"{session_id}.jsonl"
    rows = [
        {"type": "mode", "mode": "normal", "sessionId": session_id},
        {
            "type": "user",
            "uuid": "u1",
            "parentUuid": None,
            "sessionId": session_id,
            "cwd": cwd,
            "timestamp": "2026-10-01T10:00:00.000Z",
            "message": {"role": "user", "content": "fix the failing test"},
        },
        {
            "type": "assistant",
            "uuid": "a1",
            "parentUuid": "u1",
            "sessionId": session_id,
            "cwd": cwd,
            "timestamp": "2026-10-01T10:00:02.000Z",
            "message": {
                "role": "assistant",
                "model": "claude-opus-5-5",
                "content": [
                    {"type": "text", "text": "Reading the test first."},
                    {"type": "tool_use", "id": "toolu_1", "name": "Read", "input": {"file_path": "tests/test_x.py"}},
                ],
            },
        },
        {
            "type": "user",
            "uuid": "u2",
            "parentUuid": "a1",
            "sessionId": session_id,
            "cwd": cwd,
            "timestamp": "2026-10-01T10:00:03.000Z",
            "message": {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": "toolu_1", "content": "def test_x(): ..."}],
            },
        },
        {
            "type": "assistant",
            "uuid": "a2",
            "parentUuid": "u2",
            "sessionId": session_id,
            "cwd": cwd,
            "timestamp": "2026-10-01T10:00:05.000Z",
            "message": {"role": "assistant", "model": "claude-opus-5-5", "content": [{"type": "text", "text": "Fixed."}]},
        },
        {"type": "last-prompt", "lastPrompt": "fix the failing test", "sessionId": session_id},
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return path


def test_claude_encode_cwd_matches_documented_scheme():
    assert claude.encode_cwd("/Users/me/Repository/app") == "-Users-me-Repository-app"


def test_claude_reader_lists_and_reads(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    cwd = str(tmp_path / "work")
    _claude_fixture(tmp_path, cwd)

    rows = claude.list_sessions(cwd)
    assert len(rows) == 1
    assert rows[0].title == "fix the failing test"
    assert rows[0].cwd == cwd
    assert rows[0].kind == "claude"

    # Other folders are excluded when a cwd is given.
    assert claude.list_sessions(str(tmp_path / "elsewhere")) == []

    session = claude.read_session(rows[0].id)
    assert session is not None
    assert session.model == "claude-opus-5-5"
    roles = [(t.role, t.text) for t in session.turns]
    assert roles == [
        ("user", "fix the failing test"),
        ("assistant", "Reading the test first."),
        ("tool", "Read tests/test_x.py"),
        ("assistant", "Fixed."),
    ]


def test_claude_read_rejects_path_traversal(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    assert claude.read_session("../etc/passwd") is None
    assert claude.read_session("") is None


# --- Codex ------------------------------------------------------------------


def _codex_fixture(root: Path, cwd: str, session_id: str = "01a107ef-98ea-7070-9d11-56075b77b6e7") -> Path:
    folder = root / "sessions" / "2026" / "10" / "04"
    folder.mkdir(parents=True)
    path = folder / f"rollout-2026-10-04T13-21-45-{session_id}.jsonl"

    def env(ordinal: int, kind: str, payload: dict) -> dict:
        return {"timestamp": "2026-10-04T17:23:22.908Z", "ordinal": ordinal, "type": kind, "payload": payload}

    rows = [
        env(0, "session_meta", {"id": session_id, "cwd": cwd, "timestamp": "2026-10-04T17:21:45.195Z"}),
        env(1, "turn_context", {"turn_id": "t1", "cwd": cwd, "model": "gpt-6-astra"}),
        env(
            2,
            "response_item",
            {"type": "message", "role": "developer", "content": [{"type": "input_text", "text": "<app-context>x</app-context>"}]},
        ),
        env(
            3,
            "response_item",
            {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "<environment_context>cwd</environment_context>"}]},
        ),
        env(4, "response_item", {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "check the weather"}]}),
        env(5, "response_item", {"type": "reasoning", "summary": [], "encrypted_content": "gAAAA"}),
        env(
            6,
            "response_item",
            {"type": "function_call", "name": "shell", "call_id": "c1", "arguments": json.dumps({"command": ["curl", "wttr.in"]})},
        ),
        env(7, "response_item", {"type": "function_call_output", "call_id": "c1", "output": "Sunny"}),
        env(8, "response_item", {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "It is sunny."}]}),
        env(9, "event_msg", {"type": "task_complete"}),
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return path


def test_codex_reader_lists_and_reads(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    cwd = str(tmp_path / "proj")
    _codex_fixture(tmp_path, cwd)

    rows = codex.list_sessions(cwd)
    assert len(rows) == 1
    assert rows[0].id == "01a107ef-98ea-7070-9d11-56075b77b6e7"
    assert rows[0].title == "check the weather"
    assert rows[0].cwd == cwd
    assert codex.list_sessions("/nowhere") == []

    session = codex.read_session(rows[0].id)
    assert session is not None
    assert session.model == "gpt-6-astra"
    assert [(t.role, t.text) for t in session.turns] == [
        ("user", "check the weather"),
        ("tool", "shell curl wttr.in"),
        ("assistant", "It is sunny."),
    ]


def test_codex_list_without_cwd_returns_everything(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    _codex_fixture(tmp_path, "/a")
    assert len(codex.list_sessions(None)) == 1


# --- OpenCode ---------------------------------------------------------------


def _opencode_fixture(db: Path, cwd: str) -> str:
    connection = sqlite3.connect(db)
    connection.executescript(
        """
        CREATE TABLE session (
            id TEXT PRIMARY KEY, project_id TEXT, parent_id TEXT, directory TEXT, title TEXT,
            time_created INTEGER, time_updated INTEGER, time_archived INTEGER
        );
        CREATE TABLE message (id TEXT PRIMARY KEY, session_id TEXT, time_created INTEGER, time_updated INTEGER, data TEXT);
        CREATE TABLE part (id TEXT PRIMARY KEY, message_id TEXT, session_id TEXT, time_created INTEGER, time_updated INTEGER, data TEXT);
        """
    )
    sid = "ses_fixture1"
    connection.execute(
        "INSERT INTO session VALUES (?, 'prj', NULL, ?, 'Fix the build', 1787258215986, 1787258342608, NULL)",
        (sid, cwd),
    )
    connection.execute(
        "INSERT INTO message VALUES ('m1', ?, 1787258216056, 1787258216056, ?)",
        (sid, json.dumps({"role": "user", "model": {"providerID": "opencode", "modelID": "kimi-k3"}})),
    )
    connection.execute(
        "INSERT INTO part VALUES ('p1', 'm1', ?, 1787258216060, 1787258216060, ?)",
        (sid, json.dumps({"type": "text", "text": "help me fix this build"})),
    )
    connection.execute(
        "INSERT INTO message VALUES ('m2', ?, 1787258217000, 1787258217000, ?)",
        (sid, json.dumps({"role": "assistant", "parentID": "m1"})),
    )
    for i, part in enumerate(
        [
            {"type": "step-start"},
            {"type": "reasoning", "text": "look at the script"},
            {"type": "tool", "tool": "read", "callID": "r0", "state": {"status": "completed", "input": {"filePath": "scripts/build.ts"}}},
            {"type": "text", "text": "The import path is wrong; patching it."},
            {"type": "step-finish", "reason": "stop"},
        ]
    ):
        connection.execute(
            "INSERT INTO part VALUES (?, 'm2', ?, ?, ?, ?)",
            (f"q{i}", sid, 1787258217100 + i, 1787258217100 + i, json.dumps(part)),
        )
    # An archived session and a child session must not show up.
    connection.execute(
        "INSERT INTO session VALUES ('ses_old', 'prj', NULL, ?, 'Old', 1, 2, 3)", (cwd,)
    )
    connection.execute(
        "INSERT INTO session VALUES ('ses_child', 'prj', ?, ?, 'Child', 1, 2, NULL)", (sid, cwd)
    )
    connection.commit()
    connection.close()
    return sid


def test_opencode_reader_lists_and_reads(tmp_path: Path, monkeypatch):
    db = tmp_path / "opencode.db"
    monkeypatch.setenv("OPENCODE_DB", str(db))
    cwd = "/Users/me/Projects/harness"
    sid = _opencode_fixture(db, cwd)

    rows = opencode.list_sessions(cwd)
    assert [r.id for r in rows] == [sid]
    assert rows[0].title == "Fix the build"
    assert opencode.list_sessions("/other") == []

    session = opencode.read_session(sid)
    assert session is not None
    assert session.model == "kimi-k3"
    assert [(t.role, t.text) for t in session.turns] == [
        ("user", "help me fix this build"),
        ("tool", "read scripts/build.ts"),
        ("assistant", "The import path is wrong; patching it."),
    ]


def test_opencode_missing_db_is_empty(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("OPENCODE_DB", str(tmp_path / "missing.db"))
    assert opencode.list_sessions(None) == []
    assert opencode.read_session("x") is None


# --- fx ---------------------------------------------------------------------


def test_fx_reader_uses_cli_json(monkeypatch):
    listing = {
        "kind": "sessions",
        "sessions": [
            {
                "id": "VNLmbhf7-Suo",
                "title": "Exact Reply Request",
                "workspace_root": "/private/tmp/fx-probe",
                "updated_at_ms": 1792007603923,
                "history_len": 1,
            },
            {"id": "empty", "title": None, "workspace_root": "/x", "updated_at_ms": 1, "history_len": 0},
        ],
    }
    detail = {
        "kind": "session_detail",
        "id": "VNLmbhf7-Suo",
        "updated_at_ms": 1792007603923,
        "history": [
            {
                "kind": "assistant",
                "user": {"text": "Reply with exactly: hi", "images": []},
                "assistant": "hi",
                "execution": {"tool_steps": [{"tool": "shell", "input": {"command": "ls"}}]},
            }
        ],
    }

    def fake_run(args):
        if args[0] == "sessions":
            return listing
        if args[0] == "session":
            return detail if args[1] == "VNLmbhf7-Suo" else None
        return None

    monkeypatch.setattr(fx, "_run_json", fake_run)
    monkeypatch.setattr(fx, "binary", lambda: "/usr/local/bin/fx")

    rows = fx.list_sessions("/tmp/fx-probe")  # /private prefix is tolerated
    assert [r.id for r in rows] == ["VNLmbhf7-Suo"]
    assert rows[0].turns == 1

    session = fx.read_session("VNLmbhf7-Suo")
    assert session is not None
    assert [(t.role, t.text) for t in session.turns] == [
        ("user", "Reply with exactly: hi"),
        ("tool", "shell ls"),
        ("assistant", "hi"),
    ]
    assert session.summary.cwd == "/private/tmp/fx-probe"


def test_fx_without_binary_is_empty(monkeypatch):
    monkeypatch.setattr(fx, "binary", lambda: None)
    assert fx.list_sessions(None) == []
    assert fx.read_session("abc") is None
    assert fx.read_session("--help") is None


# --- facade -----------------------------------------------------------------


def test_facade_normalizes_kinds_and_merges(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "c"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "x"))
    monkeypatch.setenv("OPENCODE_DB", str(tmp_path / "none.db"))
    monkeypatch.setattr(fx, "binary", lambda: None)
    cwd = str(tmp_path / "proj")
    (tmp_path / "c").mkdir()
    (tmp_path / "x").mkdir()
    _claude_fixture(tmp_path / "c", cwd)
    _codex_fixture(tmp_path / "x", cwd)

    assert ea.normalize_kind("Claude-Code") == "claude"
    assert ea.normalize_kind("fx.sh") == "fx"
    assert ea.normalize_kind("gemini") is None

    rows = ea.list_sessions(cwd=cwd)
    assert {r.kind for r in rows} == {"claude", "codex"}
    assert ea.read_session("nope", "id") is None
    assert ea.read_session("codex", rows[[r.kind for r in rows].index("codex")].id) is not None


# --- handoff ----------------------------------------------------------------


class _Msg:
    def __init__(self, role: str, content: str) -> None:
        self.role = role
        self.content = content


def test_handoff_markdown_and_launch_argv(tmp_path: Path):
    md = handoff_markdown(
        title="Weather plan",
        messages=[_Msg("user", "check the weather"), _Msg("system", "hidden"), _Msg("assistant", "Sunny.")],
    )
    assert md.startswith("# Weather plan")
    assert "## User\n\ncheck the weather" in md
    assert "## Assistant\n\nSunny." in md
    assert "hidden" not in md

    path = write_handoff(str(tmp_path), "abcdef123456", md)
    assert path == tmp_path / ".sandwalk" / "handoff-abcdef12.md"
    assert path.read_text(encoding="utf-8") == md

    assert launch_argv("claude", "/bin/claude", prompt="go") == ["/bin/claude", "go"]
    assert launch_argv("opencode", "/bin/opencode", prompt="go") == ["/bin/opencode", "--prompt", "go"]
    assert launch_argv("fx", "/bin/fx") == ["/bin/fx"]


@pytest.mark.parametrize("kind", ["claude", "codex", "opencode", "fx"])
def test_installed_agents_reports_every_kind(kind):
    kinds = [row["kind"] for row in ea.installed_agents()]
    assert kind in kinds


# --- native writers (Claude / Codex) ----------------------------------------


def test_claude_writer_round_trips_through_reader(tmp_path: Path, monkeypatch):
    from agent.external_agents.writers import write_claude_session

    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude"))
    cwd = str(tmp_path / "proj")
    Path(cwd).mkdir()
    messages = [_Msg("user", "check the weather"), _Msg("system", "nope"), _Msg("assistant", "Sunny.")]
    sid, path = write_claude_session(cwd=cwd, title="Weather", messages=messages)
    assert path == tmp_path / "claude" / "projects" / claude.encode_cwd(cwd) / f"{sid}.jsonl"
    assert oct(path.stat().st_mode)[-3:] == "600"

    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert records[0]["type"] == "mode" and records[-1]["type"] == "last-prompt"
    assert records[-1]["lastPrompt"] == "check the weather"
    turns = [r for r in records if r["type"] in ("user", "assistant")]
    assert turns[0]["parentUuid"] is None
    assert turns[1]["parentUuid"] == turns[0]["uuid"]
    assert all(r["sessionId"] == sid and r["cwd"] == cwd for r in turns)

    # Our own reader sees exactly what we wrote.
    back = claude.read_session(sid)
    assert back is not None
    assert [(t.role, t.text) for t in back.turns] == [("user", "check the weather"), ("assistant", "Sunny.")]
    assert claude.list_sessions(cwd)[0].id == sid


def test_codex_writer_round_trips_through_reader(tmp_path: Path, monkeypatch):
    from agent.external_agents.writers import write_codex_session

    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex"))
    cwd = str(tmp_path / "proj")
    messages = [_Msg("user", "plot it"), _Msg("assistant", "Done."), _Msg("user", "thanks")]
    sid, path = write_codex_session(cwd=cwd, title="Plotting", messages=messages)
    assert path.name.startswith("rollout-") and path.name.endswith(f"-{sid}.jsonl")
    assert uuid_version(sid) == 7

    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert records[0]["type"] == "session_meta"
    assert records[0]["payload"]["cwd"] == cwd and records[0]["payload"]["id"] == sid
    assert [r["ordinal"] for r in records] == list(range(len(records)))
    kinds = [(r["type"], r["payload"].get("role")) for r in records[1:]]
    assert kinds == [
        ("turn_context", None),
        ("response_item", "user"),
        ("response_item", "assistant"),
        ("turn_context", None),
        ("response_item", "user"),
    ]
    index = (tmp_path / "codex" / "session_index.jsonl").read_text(encoding="utf-8")
    assert sid in index and "Plotting" in index

    back = codex.read_session(sid)
    assert back is not None
    assert [(t.role, t.text) for t in back.turns] == [("user", "plot it"), ("assistant", "Done."), ("user", "thanks")]


def test_native_writer_rejects_unsupported_and_empty(tmp_path: Path, monkeypatch):
    from agent.external_agents.writers import write_native_session

    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    with pytest.raises(ValueError, match="handoff"):
        write_native_session("opencode", cwd=str(tmp_path), title="x", messages=[_Msg("user", "hi")])
    with pytest.raises(ValueError, match="Nothing to export"):
        write_native_session("claude", cwd=str(tmp_path), title="x", messages=[_Msg("system", "hi")])


def test_ps_in_group_lists_the_current_process() -> None:
    from agent.external_agents.detect import _ps_in_group

    out = _ps_in_group(os.getpgrp())
    assert out is not None
    pids = [line.split()[0] for line in out.splitlines() if line.split()]
    assert str(os.getpid()) in pids


def uuid_version(value: str) -> int:
    import uuid as _uuid

    return _uuid.UUID(value).version
