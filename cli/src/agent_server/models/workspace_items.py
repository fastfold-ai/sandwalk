"""Workspace-items index API models (FAS-107).

The workspace_items table is the denormalized index over every "thing that
can appear in a tab or split" — chats today, terminals starting with
FAS-107, files/preview/structure later. The tab strip / sidebar / split
picker query this one endpoint instead of UNIONing across N kind tables.

Rows here are pointers; detail (title, cwd, model, tokens) lives in the
kind's own table and is hydrated with a follow-up batched SELECT.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from agent_server.models.base import ApiModel

WorkspaceItemKind = Literal["chat", "terminal"]
# Extensible: | "files" | "preview" | "structure" — add here + a new
# per-kind table + one branch in the tab-strip renderer.


class WorkspaceItem(ApiModel):
    """One row per pane-able thing. Cheap to list; the UI hydrates detail
    per-kind on demand."""

    id: str
    kind: WorkspaceItemKind
    project_id: str | None = None
    organize_label: str | None = None
    title: str
    updated_at: datetime


class WorkspaceItemList(ApiModel):
    data: list[WorkspaceItem]
