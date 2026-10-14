"""Shared records for sessions that live in other coding-agent CLIs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from typing import Any, Literal

ExternalAgentKind = Literal["claude", "codex", "opencode", "fx"]

AGENT_KINDS: tuple[ExternalAgentKind, ...] = ("claude", "codex", "opencode", "fx")

AGENT_LABELS: dict[str, str] = {
    "claude": "Claude Code",
    "codex": "Codex",
    "opencode": "OpenCode",
    "fx": "fx",
}

# The executable name each agent installs on PATH.
AGENT_BINARIES: dict[str, str] = {
    "claude": "claude",
    "codex": "codex",
    "opencode": "opencode",
    "fx": "fx",
}


@dataclass
class ExternalTurn:
    """One line of a normalized transcript.

    ``role`` is ``user`` or ``assistant`` for text, ``tool`` for a one-line
    summary of a tool call (``Read src/app.py``). Raw tool payloads are not
    kept; the import is history for a new Sandwalk session, not a replay.
    """

    role: Literal["user", "assistant", "tool"]
    text: str
    at: datetime | None = None


@dataclass
class ExternalSessionSummary:
    kind: ExternalAgentKind
    id: str
    title: str
    cwd: str | None
    updated_at: datetime | None
    turns: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "label": AGENT_LABELS[self.kind],
            "id": self.id,
            "title": self.title,
            "cwd": self.cwd,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
            "turns": self.turns,
        }


@dataclass
class ExternalSession:
    summary: ExternalSessionSummary
    turns: list[ExternalTurn] = field(default_factory=list)
    model: str | None = None


def ts_from_ms(value: Any) -> datetime | None:
    try:
        ms = float(value)
    except (TypeError, ValueError):
        return None
    if ms <= 0:
        return None
    return datetime.fromtimestamp(ms / 1000.0, tz=UTC)


def ts_from_iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def clip(text: str, limit: int = 160) -> str:
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def title_from_turns(turns: list[ExternalTurn], fallback: str) -> str:
    for turn in turns:
        if turn.role == "user" and turn.text.strip():
            return clip(turn.text, 72)
    return fallback


def same_dir(a: str | None, b: str | None) -> bool:
    """Compare two directories, tolerating macOS ``/private`` and trailing slashes."""
    if not a or not b:
        return False

    def norm(p: str) -> str:
        p = p.rstrip("/") or "/"
        if p.startswith("/private/"):
            p = p[len("/private") :]
        return p

    return norm(a) == norm(b)
