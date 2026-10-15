"""Hermes Agent sessions: SQLite at ``$HERMES_HOME/state.db`` (default ``~/.hermes``).

Only local surfaces are listed (``cli``, ``oneshot``, ``local``). Gateway
sessions (Telegram, Discord, Slack, …) stay out of the picker. The database
may be open in the TUI, so every read is read-only and closed immediately.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent.external_agents.types import (
    ExternalSession,
    ExternalSessionSummary,
    ExternalTurn,
    clip,
    same_dir,
    title_from_turns,
)

_LOCAL_SOURCES = ("cli", "oneshot", "local")


def db_path() -> Path:
    override = os.environ.get("HERMES_STATE_DB", "").strip()
    if override:
        return Path(override).expanduser()
    home = os.environ.get("HERMES_HOME", "").strip()
    base = Path(home).expanduser() if home else Path.home() / ".hermes"
    return base / "state.db"


def _connect() -> sqlite3.Connection | None:
    path = db_path()
    if not path.is_file():
        return None
    try:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=1.0)
    except sqlite3.Error:
        return None
    connection.row_factory = sqlite3.Row
    return connection


def _ts(value: Any) -> datetime | None:
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return None
    if seconds <= 0:
        return None
    # Hermes stores unix seconds; tolerate a millisecond stamp if one shows up.
    if seconds > 1e12:
        seconds /= 1000.0
    return datetime.fromtimestamp(seconds, tz=UTC)


def _tool_summaries(raw: str | None) -> list[str]:
    if not raw or not str(raw).strip():
        return []
    try:
        calls = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(calls, list):
        return []
    lines: list[str] = []
    for call in calls:
        if not isinstance(call, dict):
            continue
        function = call.get("function") if isinstance(call.get("function"), dict) else call
        name = str(function.get("name") or "tool")
        arguments = function.get("arguments")
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                arguments = {}
        detail = ""
        if isinstance(arguments, dict):
            for key in ("command", "cmd", "path", "file_path", "filePath", "pattern", "query"):
                value = arguments.get(key)
                if isinstance(value, str) and value.strip():
                    detail = " " + clip(value, 100)
                    break
        lines.append(f"{name}{detail}")
    return lines


def _turns_for(connection: sqlite3.Connection, session_id: str) -> tuple[list[ExternalTurn], str | None]:
    turns: list[ExternalTurn] = []
    rows = connection.execute(
        "SELECT role, content, tool_calls, tool_name, timestamp FROM messages "
        "WHERE session_id = ? AND active = 1 AND compacted = 0 "
        "ORDER BY timestamp ASC, id ASC",
        (session_id,),
    ).fetchall()
    for row in rows:
        role = str(row["role"] or "")
        at = _ts(row["timestamp"])
        text = str(row["content"] or "").strip()
        if role == "user" and text:
            turns.append(ExternalTurn(role="user", text=text, at=at))
        elif role == "assistant":
            if text:
                turns.append(ExternalTurn(role="assistant", text=text, at=at))
            for line in _tool_summaries(row["tool_calls"]):
                turns.append(ExternalTurn(role="tool", text=line, at=at))
        elif role == "tool":
            name = str(row["tool_name"] or "tool")
            detail = f" {clip(text, 100)}" if text else ""
            turns.append(ExternalTurn(role="tool", text=f"{name}{detail}", at=at))
    return turns, None


def _summary(row: sqlite3.Row, turns: int, fallback: str) -> ExternalSessionSummary:
    title = str(row["title"] or "").strip() or fallback
    return ExternalSessionSummary(
        kind="hermes",
        id=str(row["id"]),
        title=clip(title, 72),
        cwd=str(row["cwd"]) if row["cwd"] else None,
        updated_at=_ts(row["last_activity_at"]) or _ts(row["started_at"]),
        turns=turns,
    )


def list_sessions(cwd: str | None = None, *, limit: int = 50) -> list[ExternalSessionSummary]:
    connection = _connect()
    if connection is None:
        return []
    placeholders = ",".join("?" for _ in _LOCAL_SOURCES)
    rows: list[ExternalSessionSummary] = []
    try:
        sessions = connection.execute(
            f"SELECT id, title, cwd, model, started_at, last_activity_at, message_count FROM sessions "
            f"WHERE source IN ({placeholders}) AND archived = 0 AND hidden = 0 AND message_count > 0 "
            f"ORDER BY COALESCE(last_activity_at, started_at) DESC LIMIT ?",
            (*_LOCAL_SOURCES, max(limit * 4, limit)),
        ).fetchall()
        for row in sessions:
            if cwd and not same_dir(str(row["cwd"] or ""), cwd):
                continue
            rows.append(_summary(row, int(row["message_count"] or 0), "Hermes session"))
            if len(rows) >= limit:
                break
    except sqlite3.Error:
        return rows
    finally:
        connection.close()
    return rows


def read_session(session_id: str) -> ExternalSession | None:
    sid = str(session_id or "").strip()
    if not sid:
        return None
    connection = _connect()
    if connection is None:
        return None
    try:
        row = connection.execute(
            "SELECT id, title, cwd, model, started_at, last_activity_at, message_count, source "
            "FROM sessions WHERE id = ?",
            (sid,),
        ).fetchone()
        if row is None or str(row["source"] or "") not in _LOCAL_SOURCES:
            return None
        turns, _model = _turns_for(connection, sid)
    except sqlite3.Error:
        return None
    finally:
        connection.close()
    if not turns:
        return None
    summary = _summary(row, len(turns), title_from_turns(turns, "Hermes session"))
    model = str(row["model"] or "").strip() or None
    return ExternalSession(summary=summary, turns=turns, model=model)
