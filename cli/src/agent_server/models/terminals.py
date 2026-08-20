"""Terminal-as-first-class-item API models (FAS-107).

Terminal is a peer of Chat. Both share the tab strip / split / sidebar
lifecycle via the workspace_items index, but have their own detail table.
See ``store/terminal_sessions.py`` and ``store/workspace_items.py`` for the
persistence side.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from agent_server.models.base import ApiModel

TerminalStatus = Literal["idle", "running", "detached", "exited"]
TerminalTitleSource = Literal["pending", "auto", "user"]


class TerminalSession(ApiModel):
    """Persisted metadata for a terminal. The live PTY runtime (fd, buffer)
    is held in-memory by ``PtyManager`` on top of this row."""

    id: str
    title: str
    title_source: TerminalTitleSource = "pending"
    project_id: str | None = None
    workspace_path: str | None = None
    shell: str | None = None
    # Set when the terminal was opened from a chat's side-panel; NULL for
    # top-level "New terminal" panes. Purely informational — the terminal's
    # lifecycle is independent.
    origin_chat_id: str | None = None
    # Stable identity for user-assigned color / rename across shell respawns
    # in the same cwd. Precedent: WezTerm's pane_id vs pane role split.
    slot_key: str | None = None
    status: TerminalStatus = "idle"
    last_activity_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class TerminalSessionList(ApiModel):
    data: list[TerminalSession]


class CreateTerminalRequest(ApiModel):
    title: str | None = None
    project_id: str | None = None
    workspace_path: str | None = None
    shell: str | None = None
    origin_chat_id: str | None = None
    slot_key: str | None = None
    cols: int = Field(default=80, ge=1, le=500)
    rows: int = Field(default=24, ge=1, le=200)


class UpdateTerminalRequest(ApiModel):
    title: str | None = None
    project_id: str | None = None
    organize_label: str | None = None
