"""In-memory PTY session records."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

BUFFER_LIMIT = 2 * 1024 * 1024
# FAS-107 X4 Capa 2 · log de output persistente para restore visual.
# Guarda los últimos ~2MB de bytes crudos del PTY (independiente de si
# hay subscribers). Al reabrir la app, se hace replay al xterm nuevo
# con `xterm.write(log_bytes)` y las dims actuales del cliente — xterm
# aplica su reflow interno con las dims correctas.
OUTPUT_LOG_LIMIT = 2 * 1024 * 1024


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
    # FAS-107 X4 Capa 2 · log persistente del output. Diferente de
    # `buffer` (que se drenaba cuando el WS se conectaba). Este SIEMPRE
    # crece con todo lo que el PTY escupe y se trunca por el extremo
    # más viejo cuando alcanza `OUTPUT_LOG_LIMIT`. Es el "cuaderno
    # visual" que sobrevive Cmd+Q.
    output_log: bytearray = field(default_factory=bytearray)
    subscribers: set[Any] = field(default_factory=set)
    reader_task: asyncio.Task[None] | None = None
