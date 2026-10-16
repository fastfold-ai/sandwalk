"""Read, launch, and hand off sessions from other coding-agent CLIs.

Supported: Claude Code, Codex, OpenCode, fx, Hermes. Each reader turns the tool's own
storage into the same ``ExternalSession`` so the import path, Capy, and the
UI picker do not care which CLI produced it.
"""

from __future__ import annotations

from typing import Any

from agent.external_agents import claude, codex, fx, hermes, opencode
from agent.external_agents.detect import binary_for, foreground_agent, installed_agents
from agent.external_agents.types import (
    AGENT_BINARIES,
    AGENT_KINDS,
    AGENT_LABELS,
    ExternalAgentKind,
    ExternalSession,
    ExternalSessionSummary,
    ExternalTurn,
)

__all__ = [
    "AGENT_BINARIES",
    "AGENT_KINDS",
    "AGENT_LABELS",
    "ExternalAgentKind",
    "ExternalSession",
    "ExternalSessionSummary",
    "ExternalTurn",
    "binary_for",
    "foreground_agent",
    "installed_agents",
    "list_sessions",
    "normalize_kind",
    "read_session",
]

_READERS: dict[str, Any] = {
    "claude": claude,
    "codex": codex,
    "opencode": opencode,
    "fx": fx,
    "hermes": hermes,
}


def normalize_kind(value: str | None) -> ExternalAgentKind | None:
    key = str(value or "").strip().lower()
    aliases = {
        "claude-code": "claude",
        "claudecode": "claude",
        "openai-codex": "codex",
        "open-code": "opencode",
        "fx.sh": "fx",
        "hermes-agent": "hermes",
    }
    key = aliases.get(key, key)
    if key in AGENT_KINDS:
        return key  # type: ignore[return-value]
    return None


def list_sessions(
    kind: str | None = None,
    *,
    cwd: str | None = None,
    limit: int = 50,
) -> list[ExternalSessionSummary]:
    kinds = [normalize_kind(kind)] if kind else list(AGENT_KINDS)
    rows: list[ExternalSessionSummary] = []
    for item in kinds:
        if item is None:
            continue
        try:
            rows.extend(_READERS[item].list_sessions(cwd, limit=limit))
        except Exception:  # noqa: BLE001 — one broken store must not hide the others
            continue
    rows.sort(key=lambda s: s.updated_at.timestamp() if s.updated_at else 0, reverse=True)
    return rows[:limit]


def read_session(kind: str, session_id: str) -> ExternalSession | None:
    item = normalize_kind(kind)
    if item is None:
        return None
    try:
        return _READERS[item].read_session(session_id)
    except Exception:  # noqa: BLE001
        return None
