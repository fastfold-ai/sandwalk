"""Error types raised by :class:`agent_server.store.AgentStore`."""

from __future__ import annotations


class AgentStoreError(RuntimeError):
    """Base error for agent store open/lifecycle failures."""


class AgentStoreCorruptedError(AgentStoreError):
    """SQLite file exists but fails integrity_check — refuse to open or rewrite it."""


class AgentStoreLockError(AgentStoreError):
    """Another process already holds the exclusive serve lock for this database."""
