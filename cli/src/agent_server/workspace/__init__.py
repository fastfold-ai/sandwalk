"""Project-scoped local filesystem operations for web sessions.

Split package — re-exports the public surface previously defined in
``agent_server/workspace.py`` so existing imports keep working.
"""

from __future__ import annotations

from pathlib import Path

from agent_server.workspace.constants import MAX_FILE_SIZE, TEXT_SUFFIXES
from agent_server.workspace.errors import WorkspaceConflictError, WorkspacePathError
from agent_server.workspace.read_mixin import WorkspaceReadMixin
from agent_server.workspace.write_mixin import WorkspaceWriteMixin


class WorkspaceService(WorkspaceReadMixin, WorkspaceWriteMixin):
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()
        if not self.root.is_dir():
            raise WorkspacePathError(f"Workspace directory does not exist: {self.root}")


__all__ = [
    "MAX_FILE_SIZE",
    "TEXT_SUFFIXES",
    "WorkspacePathError",
    "WorkspaceConflictError",
    "WorkspaceService",
]
