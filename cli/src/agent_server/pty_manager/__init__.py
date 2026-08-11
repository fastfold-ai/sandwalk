"""Interactive PTY sessions for the local agent server (OpenScience-style).

Split package — re-exports the public surface previously defined in
``agent_server/pty_manager.py`` so existing imports keep working.
"""

from __future__ import annotations

import asyncio

from agent_server.pty_manager.io_mixin import PtyIOMixin
from agent_server.pty_manager.lifecycle_mixin import PtyLifecycleMixin
from agent_server.pty_manager.shell_env import BASH_PS1, ZSH_PROMPT, preferred_shell
from agent_server.pty_manager.types import BUFFER_LIMIT, PtyInfo, PtySession


class PtyManager(PtyLifecycleMixin, PtyIOMixin):
    """In-memory PTY registry scoped by agent session id."""

    def __init__(self) -> None:
        self._sessions: dict[str, PtySession] = {}
        self._by_agent: dict[str, set[str]] = {}
        self._lock = asyncio.Lock()


__all__ = [
    "BUFFER_LIMIT",
    "ZSH_PROMPT",
    "BASH_PS1",
    "preferred_shell",
    "PtyInfo",
    "PtySession",
    "PtyManager",
]
