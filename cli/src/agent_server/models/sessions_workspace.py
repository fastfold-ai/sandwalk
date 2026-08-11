from __future__ import annotations

from datetime import datetime
from typing import Literal

from agent_server.models.base import ApiModel


class WorkspaceFile(ApiModel):
    path: str
    name: str
    type: Literal["file", "directory"]
    size: int | None = None
    mtime: datetime | None = None


class WorkspaceFileList(ApiModel):
    data: list[WorkspaceFile]


class WorkspaceFileContent(ApiModel):
    path: str
    content: str
    encoding: Literal["text", "base64"] = "text"
    mime_type: str
    version: str
    size: int
    mtime: datetime


class WriteWorkspaceFileRequest(ApiModel):
    path: str
    content: str
    encoding: Literal["text", "base64"] = "text"
    base_version: str | None = None


class CreateWorkspaceFolderRequest(ApiModel):
    path: str


class MoveWorkspaceFileRequest(ApiModel):
    source_path: str
    target_path: str


class WorkspaceMutationResponse(ApiModel):
    path: str
