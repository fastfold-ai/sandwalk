"""Interactive PTY sessions for the local agent server (OpenScience-style).

Split package — re-exports the public surface previously defined in
``agent_server/pty_manager.py`` so existing imports keep working.
"""

from __future__ import annotations

import asyncio

from agent_server.pty_manager.agent_mixin import PtyAgentMixin
from agent_server.pty_manager.io_mixin import PtyIOMixin
from agent_server.pty_manager.lifecycle_mixin import PtyLifecycleMixin
from agent_server.pty_manager.shell_env import BASH_PS1, ZSH_PROMPT, preferred_shell
from agent_server.pty_manager.types import BUFFER_LIMIT, PtyInfo, PtySession


class PtyManager(PtyLifecycleMixin, PtyIOMixin, PtyAgentMixin):
    """In-memory PTY registry scoped by agent session id."""

    def __init__(self) -> None:
        self._sessions: dict[str, PtySession] = {}
        self._by_agent: dict[str, set[str]] = {}
        self._lock = asyncio.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Called at app startup so worker threads (Capy tools) can create PTYs."""
        self._loop = loop

    def run_sync(self, coro, *, timeout: float = 20.0):  # type: ignore[no-untyped-def]
        """Run a PTY coroutine from a non-loop thread and wait for the result.

        Reader tasks must live on the server loop, so a plain ``asyncio.run``
        is not an option: its loop would close as soon as this returns.
        """
        loop = self._loop
        if loop is None or loop.is_closed():
            raise RuntimeError("PTY manager is not bound to a running server loop.")
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is loop:
            raise RuntimeError("run_sync must not be called from the server loop thread.")
        return asyncio.run_coroutine_threadsafe(coro, loop).result(timeout=timeout)


__all__ = [
    "BUFFER_LIMIT",
    "ZSH_PROMPT",
    "BASH_PS1",
    "preferred_shell",
    "PtyInfo",
    "PtySession",
    "PtyManager",
]
