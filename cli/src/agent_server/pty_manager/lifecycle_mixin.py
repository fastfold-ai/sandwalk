"""PTY registry CRUD: list/get/create/resize/rename/remove/shutdown."""

from __future__ import annotations

import asyncio
import os
import signal
import uuid

from agent_server.pty_manager.shell_env import set_winsize
from agent_server.pty_manager.spawn import spawn_pty
from agent_server.pty_manager.types import PtyInfo, PtySession


class PtyLifecycleMixin:
    _sessions: dict[str, PtySession]
    _by_agent: dict[str, set[str]]
    _lock: asyncio.Lock

    def list(self, session_id: str) -> list[PtyInfo]:
        ids = self._by_agent.get(session_id, set())
        rows: list[PtyInfo] = []
        for pty_id in ids:
            session = self._sessions.get(pty_id)
            if session is None:
                continue
            self.refresh_agent(session)  # type: ignore[attr-defined]
            rows.append(session.info)
        return rows

    def get(self, session_id: str, pty_id: str) -> PtyInfo | None:
        session = self._sessions.get(pty_id)
        if session is None or session.info.session_id != session_id:
            return None
        self.refresh_agent(session)  # type: ignore[attr-defined]
        return session.info

    def get_session(self, session_id: str, pty_id: str) -> PtySession | None:
        """FAS-107 X4 Capa 2 · devuelve el `PtySession` completo (con
        acceso al `output_log`). Usado por el endpoint de snapshot para
        leer el log en memoria antes de fallback a disco.
        """
        session = self._sessions.get(pty_id)
        if session is None or session.info.session_id != session_id:
            return None
        return session

    async def create(
        self,
        *,
        session_id: str,
        cwd: str,
        title: str | None = None,
        cols: int = 80,
        rows: int = 24,
        startup: str | None = None,
    ) -> PtyInfo:
        pid, master_fd, workspace = spawn_pty(cwd=cwd, cols=cols, rows=rows)

        # Count only; `list()` would re-probe every sibling's foreground.
        next_number = len(self._by_agent.get(session_id, ())) + 1
        pty_id = uuid.uuid4().hex
        info = PtyInfo(
            id=pty_id,
            session_id=session_id,
            title=title or f"Terminal {next_number}",
            cwd=str(workspace),
            cols=cols,
            rows=rows,
            pid=pid,
        )
        session = PtySession(info=info, master_fd=master_fd)
        async with self._lock:
            self._sessions[pty_id] = session
            self._by_agent.setdefault(session_id, set()).add(pty_id)
            session.reader_task = asyncio.create_task(self._read_loop(pty_id))  # type: ignore[attr-defined]
        if startup:
            asyncio.create_task(self.type_startup(session, startup))  # type: ignore[attr-defined]
        return info

    async def resize(self, session_id: str, pty_id: str, *, cols: int, rows: int) -> PtyInfo | None:
        session = self._sessions.get(pty_id)
        if session is None or session.info.session_id != session_id:
            return None
        cols = max(1, min(cols, 500))
        rows = max(1, min(rows, 200))
        try:
            set_winsize(session.master_fd, rows, cols)
            os.kill(session.info.pid, signal.SIGWINCH)
        except OSError:
            pass
        session.info.cols = cols
        session.info.rows = rows
        return session.info

    async def update_title(self, session_id: str, pty_id: str, title: str) -> PtyInfo | None:
        session = self._sessions.get(pty_id)
        if session is None or session.info.session_id != session_id:
            return None
        session.info.title = title.strip() or session.info.title
        return session.info

    async def remove(self, session_id: str, pty_id: str) -> bool:
        session = self._sessions.get(pty_id)
        if session is None or session.info.session_id != session_id:
            return False
        await self._teardown(pty_id, session)  # type: ignore[attr-defined]
        return True

    async def remove_all(self, session_id: str) -> None:
        for pty_id in list(self._by_agent.get(session_id, set())):
            session = self._sessions.get(pty_id)
            if session:
                await self._teardown(pty_id, session)  # type: ignore[attr-defined]

    async def shutdown(self) -> None:
        for pty_id in list(self._sessions):
            await self._teardown(pty_id, self._sessions[pty_id])  # type: ignore[attr-defined]
