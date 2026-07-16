"""Shared helpers and result type for CLI JSONL <-> AgentStore sync."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class SyncResult:
    scanned: int = 0
    imported: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    details: list[str] = field(default_factory=list)


def timestamp_to_datetime(value: object) -> datetime:
    if isinstance(value, (int, float)) and value > 0:
        return datetime.fromtimestamp(float(value), tz=UTC)
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip())
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=UTC)
            return parsed
        except ValueError:
            pass
    return datetime.now(UTC)


def messages_to_turns(messages: Any) -> list[tuple[str, str]]:
    """Pair store user/assistant messages into trajectory turns."""
    turns: list[tuple[str, str]] = []
    pending_user: str | None = None
    for message in messages:
        role = str(getattr(message, "role", "") or "").strip().lower()
        content = str(getattr(message, "content", "") or "")
        if role == "user":
            pending_user = content
        elif role == "assistant" and pending_user is not None:
            turns.append((pending_user, content))
            pending_user = None
    return turns
