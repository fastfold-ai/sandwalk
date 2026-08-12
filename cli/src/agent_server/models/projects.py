from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from agent_server.models.base import ApiModel

DEFAULT_PROJECT_ICON = "folder"
DEFAULT_PROJECT_COLOR = "neutral"


class AgentProject(ApiModel):
    id: str
    name: str
    description: str | None = None
    agent_context: str | None = None
    folder_path: str | None = None
    icon: str = DEFAULT_PROJECT_ICON
    color: str = DEFAULT_PROJECT_COLOR
    pinned: bool = False
    home_layout: dict[str, Any] | None = None
    session_count: int = 0
    created_at: datetime
    updated_at: datetime


class CreateProjectRequest(ApiModel):
    name: str = Field(min_length=1)
    description: str | None = None
    agent_context: str | None = None
    folder_path: str | None = None
    icon: str | None = None
    color: str | None = None
    pinned: bool = False
    home_layout: dict[str, Any] | None = None


class UpdateProjectRequest(ApiModel):
    name: str | None = None
    description: str | None = None
    agent_context: str | None = None
    folder_path: str | None = None
    icon: str | None = None
    color: str | None = None
    pinned: bool | None = None
    home_layout: dict[str, Any] | None = None
    clear_description: bool = False
    clear_agent_context: bool = False
    clear_folder_path: bool = False
    clear_home_layout: bool = False


class ProjectList(ApiModel):
    data: list[AgentProject]


class DeleteProjectResponse(ApiModel):
    deleted: bool = True


class ProjectFolderFile(ApiModel):
    """A file under the project's linked folder (not a Library blob)."""

    path: str
    name: str
    kind: str = "other"
    size: int | None = None
    mtime: datetime | None = None


class ProjectFolderListing(ApiModel):
    folder_path: str
    truncated: bool = False
    data: list[ProjectFolderFile]


class RenameProjectFolderFileRequest(ApiModel):
    path: str = Field(min_length=1)
    name: str = Field(min_length=1)


class UseProjectFolderInChatRequest(ApiModel):
    paths: list[str] = Field(min_length=1)
    title: str | None = None


class DeleteProjectFolderFileResponse(ApiModel):
    deleted: bool = True
