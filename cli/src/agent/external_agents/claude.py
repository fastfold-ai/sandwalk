"""Claude Code sessions: ``~/.claude/projects/<encoded cwd>/<id>.jsonl``.

Anthropic documents the layout but calls the record format internal. This
reader only depends on the fields that have been stable across versions:
``type`` (``user`` / ``assistant``), ``message.content``, ``cwd``,
``sessionId``, and ``timestamp``.
"""

from __future__ import annotations

import json
import os
import re
from datetime import UTC
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


def config_dir() -> Path:
    override = os.environ.get("CLAUDE_CONFIG_DIR", "").strip()
    return Path(override).expanduser() if override else Path.home() / ".claude"


def projects_dir() -> Path:
    return config_dir() / "projects"


def encode_cwd(cwd: str) -> str:
    """Claude replaces every character outside ``[A-Za-z0-9]`` with ``-``."""
    return re.sub(r"[^A-Za-z0-9]", "-", cwd)


def _project_dirs(cwd: str | None) -> list[Path]:
    root = projects_dir()
    if not root.is_dir():
        return []
    if cwd:
        names = {encode_cwd(cwd), encode_cwd(os.path.realpath(cwd))}
        if cwd.startswith("/private/"):
            names.add(encode_cwd(cwd.replace("/private/", "/", 1)))
        return [root / name for name in sorted(names) if (root / name).is_dir()]
    return [p for p in root.iterdir() if p.is_dir()]


def _block_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            text = block.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(p for p in parts if p)


def _tool_summary(block: dict[str, Any]) -> str:
    name = str(block.get("name") or "tool")
    inputs = block.get("input") if isinstance(block.get("input"), dict) else {}
    for key in ("file_path", "path", "command", "pattern", "query", "url"):
        value = inputs.get(key)
        if isinstance(value, str) and value.strip():
            return f"{name} {clip(value, 100)}"
    return name


def _parse_file(path: Path) -> tuple[list[ExternalTurn], str | None, str | None]:
    """Return (turns, cwd, model) for one transcript."""
    turns: list[ExternalTurn] = []
    cwd: str | None = None
    model: str | None = None
    try:
        handle = path.open(encoding="utf-8")
    except OSError:
        return turns, cwd, model
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
            if cwd is None and isinstance(record.get("cwd"), str):
                cwd = record["cwd"]
            kind = record.get("type")
            if kind not in ("user", "assistant"):
                continue
            if record.get("isSidechain") or record.get("isMeta"):
                continue
            message = record.get("message") if isinstance(record.get("message"), dict) else {}
            at = ts_from_iso(record.get("timestamp"))
            content = message.get("content")
            if kind == "assistant":
                if model is None and isinstance(message.get("model"), str):
                    if not message["model"].startswith("<"):
                        model = message["model"]
                text = _block_text(content)
                if text.strip():
                    turns.append(ExternalTurn(role="assistant", text=text, at=at))
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_use":
                            turns.append(ExternalTurn(role="tool", text=_tool_summary(block), at=at))
                continue
            # user: skip tool_result-only entries, keep typed prompts.
            if isinstance(content, list) and all(
                isinstance(b, dict) and b.get("type") == "tool_result" for b in content
            ):
                continue
            text = _block_text(content)
            if text.strip():
                turns.append(ExternalTurn(role="user", text=text, at=at))
    return turns, cwd, model


def _summary_for(path: Path, *, cwd_hint: str | None) -> ExternalSessionSummary | None:
    turns, cwd, _model = _parse_file(path)
    if not turns:
        return None
    try:
        stat = path.stat()
        from datetime import datetime, timezone

        updated = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
    except OSError:
        updated = None
    return ExternalSessionSummary(
        kind="claude",
        id=path.stem,
        title=title_from_turns(turns, "Claude Code session"),
        cwd=cwd or cwd_hint,
        updated_at=updated,
        turns=len(turns),
    )


def list_sessions(cwd: str | None = None, *, limit: int = 50) -> list[ExternalSessionSummary]:
    rows: list[ExternalSessionSummary] = []
    for project in _project_dirs(cwd):
        for path in project.glob("*.jsonl"):
            summary = _summary_for(path, cwd_hint=None)
            if summary is None:
                continue
            if cwd and summary.cwd and not same_dir(summary.cwd, cwd):
                continue
            rows.append(summary)
    rows.sort(key=lambda s: s.updated_at.timestamp() if s.updated_at else 0, reverse=True)
    return rows[:limit]


def _find_file(session_id: str) -> Path | None:
    safe = str(session_id or "").strip()
    if not safe or "/" in safe or safe.startswith("."):
        return None
    for project in _project_dirs(None):
        candidate = project / f"{safe}.jsonl"
        if candidate.is_file():
            return candidate
    return None


def read_session(session_id: str) -> ExternalSession | None:
    path = _find_file(session_id)
    if path is None:
        return None
    summary = _summary_for(path, cwd_hint=None)
    if summary is None:
        return None
    turns, _cwd, model = _parse_file(path)
    return ExternalSession(summary=summary, turns=turns, model=model)
