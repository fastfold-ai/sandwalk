"""In-memory PTY session records."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

BUFFER_LIMIT = 2 * 1024 * 1024


@dataclass
class PtyInfo:
    id: str
    session_id: str
    title: str
    cwd: str
    cols: int
    rows: int
    pid: int
    status: str = "running"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "sessionId": self.session_id,
            "title": self.title,
            "cwd": self.cwd,
            "cols": self.cols,
            "rows": self.rows,
            "pid": self.pid,
            "status": self.status,
        }


@dataclass
class PtySession:
    info: PtyInfo
    master_fd: int
    buffer: bytearray = field(default_factory=bytearray)
    subscribers: set[Any] = field(default_factory=set)
    reader_task: asyncio.Task[None] | None = None
