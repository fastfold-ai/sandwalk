from __future__ import annotations

from typing import Literal

from pydantic import Field

from agent_server.models.base import ApiModel

PtyAgentKind = Literal["claude", "codex", "opencode", "fx", "hermes"]


class PtySessionInfo(ApiModel):
    id: str
    session_id: str
    title: str
    cwd: str
    cols: int = 80
    rows: int = 24
    pid: int
    status: Literal["running", "exited"] = "running"
    # Coding-agent CLI detected in the foreground, if any.
    agent: PtyAgentKind | None = None
    agent_cwd: str | None = None


class PtySessionList(ApiModel):
    data: list[PtySessionInfo]


class CreatePtyRequest(ApiModel):
    title: str | None = None
    cols: int = Field(default=80, ge=1, le=500)
    rows: int = Field(default=24, ge=1, le=200)
    # Typed into the shell once it is up, e.g. ``claude``. Used by server-side
    # launches (Capy, handoff); the UI has its own startup queue.
    startup: str | None = None


class UpdatePtyRequest(ApiModel):
    title: str | None = None
    cols: int | None = Field(default=None, ge=1, le=500)
    rows: int | None = Field(default=None, ge=1, le=200)
