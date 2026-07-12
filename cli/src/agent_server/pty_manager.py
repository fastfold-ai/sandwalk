"""Interactive PTY sessions for the local agent server (OpenScience-style)."""

from __future__ import annotations

import asyncio
import fcntl
import os
import signal
import struct
import termios
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


BUFFER_LIMIT = 2 * 1024 * 1024

# Match terminal tab accent (Tailwind emerald-500 / #10B981); gray cwd basename.
ZSH_PROMPT = "%B%F{#10B981}%n@%m%f%b %F{245}%1~%f %# "
BASH_PS1 = (
    r"\[\e[1;38;2;16;185;129m\]\u@\h\[\e[0m\] "
    r"\[\e[38;5;245m\]\W\[\e[0m\] \$ "
)


def preferred_shell() -> str:
    shell = os.environ.get("SHELL") or "/bin/zsh"
    if Path(shell).exists():
        return shell
    for candidate in ("/bin/zsh", "/bin/bash", "/bin/sh"):
        if Path(candidate).exists():
            return candidate
    return "/bin/sh"


def _terminal_dot_dir() -> Path:
    """Shell startup dir that applies FastFold prompt colors after the user rc."""
    from agent.config import CONFIG_DIR

    zdot = CONFIG_DIR / "terminal-dot"
    zdot.mkdir(parents=True, exist_ok=True)
    zshrc = zdot / ".zshrc"
    zshrc.write_text(
        "# Managed by FastFold agent terminal — do not edit.\n"
        '[[ -r "${HOME}/.zshrc" ]] && source "${HOME}/.zshrc"\n'
        "_fastfold_set_prompt() {\n"
        f"  PROMPT='{ZSH_PROMPT}'\n"
        "  RPROMPT=''\n"
        "}\n"
        "_fastfold_set_prompt\n"
        "if typeset -f add-zsh-hook >/dev/null 2>&1; then\n"
        "  autoload -Uz add-zsh-hook\n"
        "  add-zsh-hook precmd _fastfold_set_prompt\n"
        "elif [[ -n ${precmd_functions+x} ]]; then\n"
        "  precmd_functions+=(_fastfold_set_prompt)\n"
        "fi\n"
    )
    bashrc = zdot / ".bashrc"
    bashrc.write_text(
        "# Managed by FastFold agent terminal — do not edit.\n"
        '[[ -r "${HOME}/.bashrc" ]] && source "${HOME}/.bashrc"\n'
        f"PS1='{BASH_PS1}'\n"
    )
    return zdot


def _set_winsize(fd: int, rows: int, cols: int) -> None:
    packed = struct.pack("HHHH", max(1, rows), max(1, cols), 0, 0)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, packed)


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


class PtyManager:
    """In-memory PTY registry scoped by agent session id."""

    def __init__(self) -> None:
        self._sessions: dict[str, PtySession] = {}
        self._by_agent: dict[str, set[str]] = {}
        self._lock = asyncio.Lock()

    def list(self, session_id: str) -> list[PtyInfo]:
        ids = self._by_agent.get(session_id, set())
        return [
            self._sessions[pty_id].info
            for pty_id in ids
            if pty_id in self._sessions
        ]

    def get(self, session_id: str, pty_id: str) -> PtyInfo | None:
        session = self._sessions.get(pty_id)
        if session is None or session.info.session_id != session_id:
            return None
        return session.info

    async def create(
        self,
        *,
        session_id: str,
        cwd: str,
        title: str | None = None,
        cols: int = 80,
        rows: int = 24,
    ) -> PtyInfo:
        workspace = Path(cwd).expanduser().resolve()
        workspace.mkdir(parents=True, exist_ok=True)

        master_fd, slave_fd = os.openpty()
        _set_winsize(master_fd, rows, cols)

        pid = os.fork()
        if pid == 0:
            try:
                os.close(master_fd)
                os.setsid()
                fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)
                os.dup2(slave_fd, 0)
                os.dup2(slave_fd, 1)
                os.dup2(slave_fd, 2)
                if slave_fd > 2:
                    os.close(slave_fd)
                os.chdir(workspace)
                env = os.environ.copy()
                env["TERM"] = "xterm-256color"
                env["COLORTERM"] = "truecolor"
                env["CLICOLOR"] = "1"
                env["CLICOLOR_FORCE"] = "1"
                env["FORCE_COLOR"] = "1"
                # BSD ls colors: dirs bold blue, executables green, symlinks magenta
                env.setdefault(
                    "LSCOLORS",
                    "ExGxFxdxCxegedabagacad",
                )
                env["FASTFOLD_TERMINAL"] = "1"
                shell = preferred_shell()
                shell_name = Path(shell).name
                dot = _terminal_dot_dir()
                if shell_name == "zsh":
                    env["ZDOTDIR"] = str(dot)
                    argv = [shell, "-i"]
                elif shell_name == "bash":
                    argv = [shell, "--rcfile", str(dot / ".bashrc"), "-i"]
                else:
                    env["PS1"] = BASH_PS1
                    argv = [shell, "-i"]
                os.execvpe(shell, argv, env)
            except Exception:
                os._exit(1)

        os.close(slave_fd)
        flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
        fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        existing = self.list(session_id)
        next_number = len(existing) + 1
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
            session.reader_task = asyncio.create_task(self._read_loop(pty_id))
        return info

    async def resize(
        self, session_id: str, pty_id: str, *, cols: int, rows: int
    ) -> PtyInfo | None:
        session = self._sessions.get(pty_id)
        if session is None or session.info.session_id != session_id:
            return None
        cols = max(1, min(cols, 500))
        rows = max(1, min(rows, 200))
        try:
            _set_winsize(session.master_fd, rows, cols)
            os.kill(session.info.pid, signal.SIGWINCH)
        except OSError:
            pass
        session.info.cols = cols
        session.info.rows = rows
        return session.info

    async def update_title(
        self, session_id: str, pty_id: str, title: str
    ) -> PtyInfo | None:
        session = self._sessions.get(pty_id)
        if session is None or session.info.session_id != session_id:
            return None
        session.info.title = title.strip() or session.info.title
        return session.info

    async def remove(self, session_id: str, pty_id: str) -> bool:
        session = self._sessions.get(pty_id)
        if session is None or session.info.session_id != session_id:
            return False
        await self._teardown(pty_id, session)
        return True

    async def remove_all(self, session_id: str) -> None:
        for pty_id in list(self._by_agent.get(session_id, set())):
            session = self._sessions.get(pty_id)
            if session:
                await self._teardown(pty_id, session)

    async def shutdown(self) -> None:
        for pty_id in list(self._sessions):
            await self._teardown(pty_id, self._sessions[pty_id])

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
            _set_winsize(session.master_fd, session.info.rows, session.info.cols)
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
