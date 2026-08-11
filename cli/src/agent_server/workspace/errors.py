"""Errors raised by the workspace filesystem service."""

from __future__ import annotations

from agent_server.models import WorkspaceFileContent


class WorkspacePathError(ValueError):
    pass


class WorkspaceConflictError(RuntimeError):
    def __init__(self, current: WorkspaceFileContent) -> None:
        super().__init__("Workspace file changed since it was loaded.")
        self.current = current
