"""Import legacy CLI JSONL sessions into the shared AgentStore (SQLite).

Split package — re-exports the public surface previously defined in
``agent_server/session_sync.py`` so existing imports keep working.
"""

from __future__ import annotations

from agent_server.session_sync.core import SyncResult, messages_to_turns
from agent_server.session_sync.export import export_store_to_trajectory
from agent_server.session_sync.importer import import_trajectory
from agent_server.session_sync.scan import sync_jsonl_sessions

__all__ = [
    "SyncResult",
    "messages_to_turns",
    "export_store_to_trajectory",
    "import_trajectory",
    "sync_jsonl_sessions",
]
