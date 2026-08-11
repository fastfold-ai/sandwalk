"""SQLite persistence for sessions, messages, and replayable events.

This is a package so each domain (sessions, projects, specialists, messages,
events, MCP servers) can live in its own module; :class:`AgentStore` composes
them via mixins in :mod:`agent_server.store.core`. Import from
``agent_server.store`` as before — this module re-exports the public API.
"""

from __future__ import annotations

from agent_server.store.core import AgentStore
from agent_server.store.errors import (
    AgentStoreCorruptedError,
    AgentStoreError,
    AgentStoreLockError,
)
from agent_server.store.util import utc_now

__all__ = [
    "AgentStore",
    "AgentStoreCorruptedError",
    "AgentStoreError",
    "AgentStoreLockError",
    "utc_now",
]
