"""Write a Sandwalk transcript as a native Claude Code or Codex session.

Both tools store append-only JSONL that their ``--resume`` / ``resume``
commands replay. Neither format is public, so these writers only emit the
fields the installed versions (Claude Code 2.1.x, Codex 0.16x) read back:
message role + text, the parent chain, cwd, and timestamps. Tool calls are
folded into assistant text; nothing here pretends to be a tool result.

Callers should present this as experimental and fall back to the Markdown
handoff when a CLI rejects the file.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime, timezone
from pathlib import Path
from typing import Any

from agent.external_agents import claude as claude_reader
from agent.external_agents import codex as codex_reader

# Written into Claude records; the value Claude itself writes for turns it
# did not generate (seen in real transcripts).
CLAUDE_SYNTHETIC_MODEL = "<synthetic>"
CLAUDE_VERSION_HINT = "2.1.0"


def _utc(dt: datetime | None) -> datetime:
    if dt is None:
        return datetime.now(tz=UTC)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _iso_ms(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def _transcript(messages: list[Any]) -> list[tuple[str, str, datetime]]:
    rows: list[tuple[str, str, datetime]] = []
    for message in messages:
        role = str(getattr(message, "role", "") or "")
        text = str(getattr(message, "content", "") or "").strip()
        if role not in ("user", "assistant") or not text:
            continue
        rows.append((role, text, _utc(getattr(message, "created_at", None))))
    return rows


def _uuid7_like(at: datetime) -> str:
    """Time-ordered UUID in the shape Codex uses (48-bit ms timestamp prefix)."""
    ms = int(at.timestamp() * 1000)
    rand = uuid.uuid4().int & ((1 << 74) - 1)
    value = (ms << 80) | (0x7 << 76) | rand
    # force RFC variant bits
    value = (value & ~(0x3 << 62)) | (0x2 << 62)
    return str(uuid.UUID(int=value & ((1 << 128) - 1)))


# --- Claude Code ------------------------------------------------------------


def write_claude_session(*, cwd: str, title: str, messages: list[Any]) -> tuple[str, Path]:
    """Create ``~/.claude/projects/<encoded cwd>/<id>.jsonl``. Returns (session_id, path)."""
    rows = _transcript(messages)
    if not rows:
        raise ValueError("Nothing to export: the session has no user or assistant messages.")
    # Claude resolves symlinks before encoding the project folder (``/tmp`` is
    # ``/private/tmp`` on macOS) and only looks there for ``--resume``.
    cwd = os.path.realpath(cwd)
    session_id = str(uuid.uuid4())
    folder = claude_reader.projects_dir() / claude_reader.encode_cwd(cwd)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{session_id}.jsonl"
    lines: list[dict[str, Any]] = [
        {"type": "mode", "mode": "normal", "sessionId": session_id},
        {"type": "permission-mode", "permissionMode": "default", "sessionId": session_id},
    ]
    parent: str | None = None
    last_prompt = ""
    leaf = ""
    for role, text, at in rows:
        record_id = str(uuid.uuid4())
        base = {
            "parentUuid": parent,
            "isSidechain": False,
            "type": role,
            "uuid": record_id,
            "timestamp": _iso_ms(at),
            "cwd": cwd,
            "sessionId": session_id,
            "version": CLAUDE_VERSION_HINT,
            "userType": "external",
            "entrypoint": "cli",
        }
        if role == "user":
            base["message"] = {"role": "user", "content": text}
            base["permissionMode"] = "default"
            base["promptId"] = str(uuid.uuid4())
            base["origin"] = {"kind": "human"}
            base["promptSource"] = "typed"
            last_prompt = text
        else:
            base["message"] = {
                "id": str(uuid.uuid4()),
                "role": "assistant",
                "type": "message",
                "model": CLAUDE_SYNTHETIC_MODEL,
                "content": [{"type": "text", "text": text}],
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {"input_tokens": 0, "output_tokens": 0},
            }
        lines.append(base)
        parent = record_id
        leaf = record_id
    lines.append({"type": "summary", "summary": title, "leafUuid": leaf})
    lines.append({"type": "last-prompt", "lastPrompt": last_prompt, "leafUuid": leaf, "sessionId": session_id})
    with path.open("w", encoding="utf-8") as handle:
        for line in lines:
            handle.write(json.dumps(line, ensure_ascii=False) + "\n")
    os.chmod(path, 0o600)
    return session_id, path


# --- Codex ------------------------------------------------------------------


def write_codex_session(*, cwd: str, title: str, messages: list[Any]) -> tuple[str, Path]:
    """Create a Codex rollout under ``$CODEX_HOME/sessions/YYYY/MM/DD``. Returns (session_id, path)."""
    rows = _transcript(messages)
    if not rows:
        raise ValueError("Nothing to export: the session has no user or assistant messages.")
    cwd = os.path.realpath(cwd)
    started = rows[0][2]
    session_id = _uuid7_like(started)
    folder = codex_reader.sessions_dir() / started.strftime("%Y") / started.strftime("%m") / started.strftime("%d")
    folder.mkdir(parents=True, exist_ok=True)
    stamp = started.strftime("%Y-%m-%dT%H-%M-%S")
    path = folder / f"rollout-{stamp}-{session_id}.jsonl"

    ordinal = 0

    def env(kind: str, payload: dict[str, Any], at: datetime) -> dict[str, Any]:
        nonlocal ordinal
        record = {"timestamp": _iso_ms(at), "ordinal": ordinal, "type": kind, "payload": payload}
        ordinal += 1
        return record

    lines: list[dict[str, Any]] = [
        env(
            "session_meta",
            {
                "id": session_id,
                "session_id": session_id,
                "timestamp": _iso_ms(started),
                "cwd": cwd,
                "originator": "sandwalk",
                "cli_version": "sandwalk-handoff",
                "source": "cli",
                "thread_name": title,
            },
            started,
        )
    ]
    turn_id: str | None = None
    for role, text, at in rows:
        if role == "user":
            turn_id = _uuid7_like(at)
            lines.append(env("turn_context", {"turn_id": turn_id, "root_turn_id": turn_id, "cwd": cwd}, at))
            lines.append(
                env(
                    "response_item",
                    {
                        "type": "message",
                        "id": f"msg_{uuid.uuid4()}",
                        "role": "user",
                        "content": [{"type": "input_text", "text": text}],
                    },
                    at,
                )
            )
        else:
            lines.append(
                env(
                    "response_item",
                    {
                        "type": "message",
                        "id": f"msg_{uuid.uuid4()}",
                        "role": "assistant",
                        "status": "completed",
                        "content": [{"type": "output_text", "text": text}],
                    },
                    at,
                )
            )
    with path.open("w", encoding="utf-8") as handle:
        for line in lines:
            handle.write(json.dumps(line, ensure_ascii=False) + "\n")
    os.chmod(path, 0o600)
    # Codex's picker reads session_index.jsonl for names; append so the
    # imported thread shows up with a title instead of its first line.
    index = codex_reader.codex_home() / "session_index.jsonl"
    try:
        with index.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {"id": session_id, "thread_name": title, "updated_at": _iso_ms(rows[-1][2])},
                    ensure_ascii=False,
                )
                + "\n"
            )
    except OSError:
        pass
    return session_id, path


def write_native_session(kind: str, *, cwd: str, title: str, messages: list[Any]) -> tuple[str, Path]:
    if kind == "claude":
        return write_claude_session(cwd=cwd, title=title, messages=messages)
    if kind == "codex":
        return write_codex_session(cwd=cwd, title=title, messages=messages)
    raise ValueError(f"Native export is not supported for {kind}; use the handoff file.")


NATIVE_WRITERS = ("claude", "codex")
