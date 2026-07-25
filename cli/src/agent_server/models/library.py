"""Library (shared content-addressed file index) API models."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from agent_server.models.base import ApiModel

LibraryKind = Literal["image", "document", "structure", "code", "other"]


class LibraryItem(ApiModel):
    id: str
    sha256: str
    bytes: int
    mime: str | None = None
    original_name: str
    display_name: str
    kind: LibraryKind
    origin_session_id: str | None = None
    created_at: datetime
    updated_at: datetime


class LibraryPagination(ApiModel):
    """skills.sh-style page metadata for Library list responses."""

    page: int = 0
    per_page: int = 48
    total: int = 0
    has_more: bool = False


class LibraryItemList(ApiModel):
    data: list[LibraryItem]
    pagination: LibraryPagination


class UpdateLibraryItemRequest(ApiModel):
    display_name: str = Field(min_length=1)


class WriteLibraryContentRequest(ApiModel):
    content: str
    encoding: Literal["text", "base64"] = "text"


class LibraryFileContent(ApiModel):
    """Editor-facing file payload (same shape as workspace file content)."""

    path: str
    content: str
    encoding: Literal["text", "base64"] = "text"
    mime_type: str
    version: str
    size: int
    mtime: datetime


class DeleteLibraryItemResponse(ApiModel):
    deleted: bool = True


class UseLibraryInChatRequest(ApiModel):
    item_ids: list[str] = Field(min_length=1)
    project_id: str | None = None
    title: str | None = None


class UseLibraryInChatResponse(ApiModel):
    session_id: str
    paths: list[str]


class LibrarySyncResponse(ApiModel):
    scanned_sessions: int = 0
    ingested: int = 0
    linked: int = 0
    skipped: int = 0
