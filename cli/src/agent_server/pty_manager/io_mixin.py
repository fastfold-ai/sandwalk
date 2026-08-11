"""PTY byte-stream plumbing: websocket attach, reader loop, teardown."""

from __future__ import annotations

import asyncio
import os
import signal
from typing import Any

from agent_server.pty_manager.shell_env import set_winsize
from agent_server.pty_manager.types import BUFFER_LIMIT, PtySession


class PtyIOMixin:
    _sessions: dict[str, PtySession]
    _by_agent: dict[str, set[str]]
    _lock: asyncio.Lock

    async def attach(self, session_id: str, pty_id: str, websocket: Any) -> None:
        session = self._sessions.get(pty_id)
        if session is None or session.info.session_id != session_id:
            await websocket.close(code=4404)
            return
        session.subscribers.add(websocket)
        if session.buffer:
            chunk = bytes(session.buffer)
            session.buffer.clear()
            try:
                await websocket.send_bytes(chunk)
            except Exception:
                pass
        # Wake shells that are waiting on terminal size / cursor queries.
        try:
            set_winsize(session.master_fd, session.info.rows, session.info.cols)
            os.kill(session.info.pid, signal.SIGWINCH)
        except OSError:
            pass
        try:
            while True:
                message = await websocket.receive()
                if message.get("type") == "websocket.disconnect":
                    break
                data = message.get("bytes")
                text = message.get("text")
                payload = data if data is not None else (text.encode("utf-8") if text else None)
                if payload is None:
                    continue
                try:
                    os.write(session.master_fd, payload)
                except OSError:
                    break
        finally:
            session.subscribers.discard(websocket)

    async def _read_loop(self, pty_id: str) -> None:
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[bytes | None] = asyncio.Queue()

        def on_readable() -> None:
            session = self._sessions.get(pty_id)
            if session is None:
                queue.put_nowait(None)
                return
            try:
                data = os.read(session.master_fd, 8192)
            except BlockingIOError:
                return
            except OSError:
                queue.put_nowait(None)
                return
            if not data:
                queue.put_nowait(None)
                return
            queue.put_nowait(data)

        session = self._sessions.get(pty_id)
        if session is None:
            return
        loop.add_reader(session.master_fd, on_readable)
        try:
            while True:
                data = await queue.get()
                session = self._sessions.get(pty_id)
                if session is None or data is None:
                    if session is not None:
                        session.info.status = "exited"
                        dead = list(session.subscribers)
                        session.subscribers.clear()
                        for ws in dead:
                            try:
                                await ws.close(code=1000)
                            except Exception:
                                pass
                    return
                if session.subscribers:
                    stale: list[Any] = []
                    for ws in list(session.subscribers):
                        try:
                            await ws.send_bytes(data)
                        except Exception:
                            stale.append(ws)
                    for ws in stale:
                        session.subscribers.discard(ws)
                else:
                    session.buffer.extend(data)
                    if len(session.buffer) > BUFFER_LIMIT:
                        session.buffer = session.buffer[-BUFFER_LIMIT:]
        finally:
            session = self._sessions.get(pty_id)
            if session is not None:
                try:
                    loop.remove_reader(session.master_fd)
                except Exception:
                    pass

    async def _teardown(self, pty_id: str, session: PtySession) -> None:
        if session.reader_task and not session.reader_task.done():
            session.reader_task.cancel()
            try:
                await session.reader_task
            except asyncio.CancelledError:
                pass
        for ws in list(session.subscribers):
            try:
                await ws.close(code=1000)
            except Exception:
                pass
        session.subscribers.clear()
        try:
            os.kill(session.info.pid, signal.SIGHUP)
        except OSError:
            pass
        try:
            os.close(session.master_fd)
        except OSError:
            pass
        async with self._lock:
            self._sessions.pop(pty_id, None)
            ids = self._by_agent.get(session.info.session_id)
            if ids:
                ids.discard(pty_id)
                if not ids:
                    self._by_agent.pop(session.info.session_id, None)
        try:
            os.waitpid(session.info.pid, os.WNOHANG)
        except ChildProcessError:
            pass
