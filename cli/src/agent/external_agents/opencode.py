"""OpenCode sessions: one SQLite database with ``session``, ``message``, ``part``.

Default path is ``~/.local/share/opencode/opencode.db`` (``OPENCODE_DB``
overrides). The database is WAL-mode and may be open in the TUI, so every
read opens read-only and closes immediately.
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from agent.external_agents.types import (
    ExternalSession,
    ExternalSessionSummary,
    ExternalTurn,
    clip,
    same_dir,
    title_from_turns,
    ts_from_ms,
)


def db_path() -> Path:
    override = os.environ.get("OPENCODE_DB", "").strip()
    if override:
        return Path(override).expanduser()
    xdg = os.environ.get("XDG_DATA_HOME", "").strip()
    base = Path(xdg).expanduser() if xdg else Path.home() / ".local" / "share"
    return base / "opencode" / "opencode.db"


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


def _tool_summary(part: dict[str, Any]) -> str:
    name = str(part.get("tool") or "tool")
    state = part.get("state") if isinstance(part.get("state"), dict) else {}
    inputs = state.get("input") if isinstance(state.get("input"), dict) else {}
    for key in ("filePath", "path", "command", "pattern", "query", "url"):
        value = inputs.get(key)
        if isinstance(value, str) and value.strip():
            return f"{name} {clip(value, 100)}"
    return name


def _turns_for(connection: sqlite3.Connection, session_id: str) -> tuple[list[ExternalTurn], str | None]:
    turns: list[ExternalTurn] = []
    model: str | None = None
    messages = connection.execute(
        "SELECT id, data, time_created FROM message WHERE session_id = ? ORDER BY time_created ASC",
        (session_id,),
    ).fetchall()
    for message in messages:
        try:
            data = json.loads(message["data"] or "{}")
        except json.JSONDecodeError:
            continue
        role = data.get("role")
        if role not in ("user", "assistant"):
            continue
        if model is None and isinstance(data.get("model"), dict):
            mid = data["model"].get("modelID")
            if isinstance(mid, str):
                model = mid
        at = ts_from_ms(message["time_created"])
        parts = connection.execute(
            "SELECT data FROM part WHERE message_id = ? ORDER BY time_created ASC",
            (message["id"],),
        ).fetchall()
        texts: list[str] = []
        for part_row in parts:
            try:
                part = json.loads(part_row["data"] or "{}")
            except json.JSONDecodeError:
                continue
            ptype = part.get("type")
            if ptype == "text" and isinstance(part.get("text"), str):
                texts.append(part["text"])
            elif ptype == "tool" and role == "assistant":
                if texts:
                    turns.append(ExternalTurn(role="assistant", text="\n".join(texts), at=at))
                    texts = []
                turns.append(ExternalTurn(role="tool", text=_tool_summary(part), at=at))
        if texts:
            turns.append(ExternalTurn(role=role, text="\n".join(texts), at=at))
    return turns, model


def _summary_from_row(row: sqlite3.Row, turn_count: int, fallback_title: str) -> ExternalSessionSummary:
    title = str(row["title"] or "").strip() or fallback_title
    return ExternalSessionSummary(
        kind="opencode",
        id=str(row["id"]),
        title=clip(title, 72),
        cwd=str(row["directory"]) if row["directory"] else None,
        updated_at=ts_from_ms(row["time_updated"]),
        turns=turn_count,
    )


def list_sessions(cwd: str | None = None, *, limit: int = 50) -> list[ExternalSessionSummary]:
    connection = _connect()
    if connection is None:
        return []
    rows: list[ExternalSessionSummary] = []
    try:
        sessions = connection.execute(
            "SELECT id, directory, title, time_updated FROM session "
            "WHERE parent_id IS NULL AND time_archived IS NULL "
            "ORDER BY time_updated DESC LIMIT ?",
            (limit * 4,),
        ).fetchall()
        for row in sessions:
            if cwd and not same_dir(str(row["directory"] or ""), cwd):
                continue
            count = connection.execute(
                "SELECT COUNT(*) FROM message WHERE session_id = ?", (row["id"],)
            ).fetchone()[0]
            if not count:
                continue
            rows.append(_summary_from_row(row, int(count), "OpenCode session"))
            if len(rows) >= limit:
                break
    except sqlite3.Error:
        return rows
    finally:
        connection.close()
    return rows


def read_session(session_id: str) -> ExternalSession | None:
    connection = _connect()
    if connection is None:
        return None
    try:
        row = connection.execute(
            "SELECT id, directory, title, time_updated FROM session WHERE id = ?",
            (str(session_id),),
        ).fetchone()
        if row is None:
            return None
        turns, model = _turns_for(connection, str(row["id"]))
    except sqlite3.Error:
        return None
    finally:
        connection.close()
    summary = _summary_from_row(row, len(turns), title_from_turns(turns, "OpenCode session"))
    return ExternalSession(summary=summary, turns=turns, model=model)
