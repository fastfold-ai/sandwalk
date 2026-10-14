"""Codex sessions: ``$CODEX_HOME/sessions/YYYY/MM/DD/rollout-<ts>-<id>.jsonl``.

Each line is ``{timestamp, ordinal, type, payload}``. We read ``session_meta``
for cwd, and ``response_item`` for user / assistant text and tool calls.
Reasoning items are opaque (``encrypted_content``) and skipped.
"""

from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime, timezone
from pathlib import Path
from typing import Any

from agent.external_agents.types import (
    ExternalSession,
    ExternalSessionSummary,
    ExternalTurn,
    clip,
    same_dir,
    title_from_turns,
    ts_from_iso,
)

_ROLLOUT_RE = re.compile(r"^rollout-(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2})-(?P<id>[0-9a-fA-F-]{36})\.jsonl$")


def codex_home() -> Path:
    override = os.environ.get("CODEX_HOME", "").strip()
    return Path(override).expanduser() if override else Path.home() / ".codex"


def sessions_dir() -> Path:
    return codex_home() / "sessions"


def _items_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if isinstance(block, dict) and block.get("type") in ("input_text", "output_text", "text"):
            text = block.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(p for p in parts if p)


_WRAPPER_RE = re.compile(r"^<(?P<tag>[a-z][a-z0-9_-]*)>[\s\S]*</(?P=tag)>\s*$", re.IGNORECASE)


def _is_app_context(text: str) -> bool:
    """Codex injects context as user turns wrapped in one XML-ish tag.

    ``<app-context>…</app-context>``, ``<environment_context>…``,
    ``<external_codex_apps_open_page>…``. A typed prompt that is exactly one
    such wrapper is rare enough that we drop every match.
    """
    return bool(_WRAPPER_RE.match(text.strip()))


def _tool_summary(payload: dict[str, Any]) -> str:
    name = str(payload.get("name") or payload.get("type") or "tool")
    raw = payload.get("arguments") if "arguments" in payload else payload.get("input")
    args: Any = raw
    if isinstance(raw, str):
        try:
            args = json.loads(raw)
        except json.JSONDecodeError:
            args = raw
    if isinstance(args, dict):
        for key in ("cmd", "command", "path", "file_path", "pattern", "query"):
            value = args.get(key)
            if isinstance(value, list):
                value = " ".join(str(v) for v in value)
            if isinstance(value, str) and value.strip():
                return f"{name} {clip(value, 100)}"
    elif isinstance(args, str) and args.strip():
        return f"{name} {clip(args, 100)}"
    return name


def _parse_file(path: Path) -> tuple[list[ExternalTurn], dict[str, Any]]:
    turns: list[ExternalTurn] = []
    meta: dict[str, Any] = {}
    try:
        handle = path.open(encoding="utf-8")
    except OSError:
        return turns, meta
    with handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            kind = record.get("type")
            payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
            at = ts_from_iso(record.get("timestamp"))
            if kind == "session_meta":
                meta = payload
                continue
            if kind == "turn_context" and "model" in payload and "model" not in meta:
                meta["model"] = payload.get("model")
                continue
            if kind != "response_item":
                continue
            ptype = payload.get("type")
            if ptype == "message":
                role = payload.get("role")
                text = _items_text(payload.get("content"))
                if not text.strip():
                    continue
                if role == "user":
                    if _is_app_context(text):
                        continue
                    turns.append(ExternalTurn(role="user", text=text, at=at))
                elif role == "assistant":
                    turns.append(ExternalTurn(role="assistant", text=text, at=at))
                continue
            if ptype in ("function_call", "custom_tool_call", "local_shell_call", "web_search_call"):
                turns.append(ExternalTurn(role="tool", text=_tool_summary(payload), at=at))
    return turns, meta


def _summary_for(path: Path) -> ExternalSessionSummary | None:
    match = _ROLLOUT_RE.match(path.name)
    if not match:
        return None
    turns, meta = _parse_file(path)
    if not turns:
        return None
    try:
        updated = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    except OSError:
        updated = None
    session_id = str(meta.get("id") or meta.get("session_id") or match.group("id"))
    return ExternalSessionSummary(
        kind="codex",
        id=session_id,
        title=title_from_turns(turns, "Codex session"),
        cwd=str(meta.get("cwd")) if meta.get("cwd") else None,
        updated_at=updated,
        turns=len(turns),
    )


def _all_rollouts() -> list[Path]:
    root = sessions_dir()
    if not root.is_dir():
        return []
    files = [p for p in root.rglob("rollout-*.jsonl") if p.is_file()]
    # Timestamp is embedded in the name; newest first.
    files.sort(key=lambda p: p.name, reverse=True)
    return files


def list_sessions(cwd: str | None = None, *, limit: int = 50) -> list[ExternalSessionSummary]:
    rows: list[ExternalSessionSummary] = []
    for path in _all_rollouts():
        summary = _summary_for(path)
        if summary is None:
            continue
        if cwd and not same_dir(summary.cwd, cwd):
            continue
        rows.append(summary)
        if len(rows) >= limit * 3:
            break
    rows.sort(key=lambda s: s.updated_at.timestamp() if s.updated_at else 0, reverse=True)
    return rows[:limit]


def _find_file(session_id: str) -> Path | None:
    safe = str(session_id or "").strip().lower()
    if not safe or "/" in safe:
        return None
    for path in _all_rollouts():
        if safe in path.name.lower():
            return path
    return None


def read_session(session_id: str) -> ExternalSession | None:
    path = _find_file(session_id)
    if path is None:
        return None
    summary = _summary_for(path)
    if summary is None:
        return None
    turns, meta = _parse_file(path)
    model = meta.get("model") if isinstance(meta.get("model"), str) else None
    return ExternalSession(summary=summary, turns=turns, model=model)
