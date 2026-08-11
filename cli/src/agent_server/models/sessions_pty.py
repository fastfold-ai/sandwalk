from __future__ import annotations

from typing import Literal

from pydantic import Field

from agent_server.models.base import ApiModel


class PtySessionInfo(ApiModel):
    id: str
    session_id: str
    title: str
    cwd: str
    cols: int = 80
    rows: int = 24
    pid: int
    status: Literal["running", "exited"] = "running"


class PtySessionList(ApiModel):
    data: list[PtySessionInfo]


class CreatePtyRequest(ApiModel):
    title: str | None = None
    cols: int = Field(default=80, ge=1, le=500)
    rows: int = Field(default=24, ge=1, le=200)


class UpdatePtyRequest(ApiModel):
    title: str | None = None
    cols: int | None = Field(default=None, ge=1, le=500)
    rows: int | None = Field(default=None, ge=1, le=200)
