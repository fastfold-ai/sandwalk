"""fx sessions (fx.sh): read through the CLI's own JSON commands.

``fx sessions --all --json`` lists sessions; ``fx session <id> --json`` returns
the history. Both are documented, so we do not parse ``~/.fx/sessions``.
"""

from __future__ import annotations

import json
import shutil
import subprocess
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

_TIMEOUT_S = 8.0


def binary() -> str | None:
    return shutil.which("fx")


def _run_json(args: list[str]) -> Any:
    exe = binary()
    if not exe:
        return None
    try:
        completed = subprocess.run(
            [exe, *args],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0 or not completed.stdout.strip():
        return None
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError:
        return None


def _summary_from_entry(entry: dict[str, Any]) -> ExternalSessionSummary | None:
    sid = str(entry.get("id") or "").strip()
    if not sid:
        return None
    title = str(entry.get("title") or "").strip() or "fx session"
    return ExternalSessionSummary(
        kind="fx",
        id=sid,
        title=clip(title, 72),
        cwd=str(entry.get("workspace_root")) if entry.get("workspace_root") else None,
        updated_at=ts_from_ms(entry.get("updated_at_ms")),
        turns=int(entry.get("history_len") or 0),
    )


def list_sessions(cwd: str | None = None, *, limit: int = 50) -> list[ExternalSessionSummary]:
    payload = _run_json(["sessions", "--all", "--limit", str(min(100, max(1, limit * 2))), "--json"])
    if not isinstance(payload, dict):
        return []
    rows: list[ExternalSessionSummary] = []
    for entry in payload.get("sessions") or []:
        if not isinstance(entry, dict):
            continue
        summary = _summary_from_entry(entry)
        if summary is None or summary.turns == 0:
            continue
        if cwd and not same_dir(summary.cwd, cwd):
            continue
        rows.append(summary)
    rows.sort(key=lambda s: s.updated_at.timestamp() if s.updated_at else 0, reverse=True)
    return rows[:limit]


def _tool_summary(step: dict[str, Any]) -> str:
    name = str(step.get("tool") or step.get("name") or "tool")
    args = step.get("input") if isinstance(step.get("input"), dict) else step.get("args")
    if isinstance(args, dict):
        for key in ("command", "cmd", "path", "file", "pattern", "query"):
            value = args.get(key)
            if isinstance(value, str) and value.strip():
                return f"{name} {clip(value, 100)}"
    return name


def read_session(session_id: str) -> ExternalSession | None:
    sid = str(session_id or "").strip()
    if not sid or sid.startswith("-"):
        return None
    detail = _run_json(["session", sid, "--json"])
    if not isinstance(detail, dict):
        return None
    turns: list[ExternalTurn] = []
    for entry in detail.get("history") or []:
        if not isinstance(entry, dict):
            continue
        user = entry.get("user") if isinstance(entry.get("user"), dict) else {}
        text = user.get("text")
        if isinstance(text, str) and text.strip():
            turns.append(ExternalTurn(role="user", text=text))
        execution = entry.get("execution") if isinstance(entry.get("execution"), dict) else {}
        for step in execution.get("tool_steps") or []:
            if isinstance(step, dict):
                turns.append(ExternalTurn(role="tool", text=_tool_summary(step)))
        assistant = entry.get("assistant")
        if isinstance(assistant, str) and assistant.strip():
            turns.append(ExternalTurn(role="assistant", text=assistant))
    if not turns:
        return None
    workspace = None
    listing = _run_json(["sessions", "--all", "--limit", "100", "--json"])
    if isinstance(listing, dict):
        for entry in listing.get("sessions") or []:
            if isinstance(entry, dict) and str(entry.get("id")) == sid:
                workspace = entry.get("workspace_root")
                break
    summary = ExternalSessionSummary(
        kind="fx",
        id=sid,
        title=title_from_turns(turns, "fx session"),
        cwd=str(workspace) if workspace else None,
        updated_at=ts_from_ms(detail.get("updated_at_ms")),
        turns=len(turns),
    )
    return ExternalSession(summary=summary, turns=turns, model=None)
