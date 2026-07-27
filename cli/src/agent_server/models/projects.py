from __future__ import annotations

from datetime import datetime

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


class UpdateProjectRequest(ApiModel):
    name: str | None = None
    description: str | None = None
    agent_context: str | None = None
    folder_path: str | None = None
    icon: str | None = None
    color: str | None = None
    pinned: bool | None = None
    clear_description: bool = False
    clear_agent_context: bool = False
    clear_folder_path: bool = False


class ProjectList(ApiModel):
    data: list[AgentProject]


class DeleteProjectResponse(ApiModel):
    deleted: bool = True
