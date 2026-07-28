from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from agent_server.models.base import ApiModel


class SiteDeployment(ApiModel):
    id: str
    status: Literal["publishing", "published", "error"]
    slug: str
    public_url: str | None = None
    size_bytes: int | None = None
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None = None


class Site(ApiModel):
    id: str
    name: str
    slug: str | None = None
    status: Literal["draft", "ready", "publishing", "published", "error"] = "ready"
    source_session_id: str | None = None
    source_project_id: str | None = None
    source_path: str
    origin_session_id: str | None = None
    origin_project_id: str | None = None
    storage_path: str
    content_sha256: str
    file_count: int
    bytes: int
    size_bytes: int
    cloud_site_id: str | None = None
    cloud_url: str | None = None
    deployment: SiteDeployment | None = None
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None = None


class SiteList(ApiModel):
    data: list[Site]


class RegisterSiteRequest(ApiModel):
    name: str = Field(min_length=1)
    path: str = Field(min_length=1)
    session_id: str | None = None
    project_id: str | None = None


class RenameSiteRequest(ApiModel):
    name: str = Field(min_length=1)


class PublishSiteRequest(ApiModel):
    slug: str | None = None


class SitePreview(ApiModel):
    url: str
    expires_at: datetime


class SitePublishResult(ApiModel):
    site: Site
    url: str
    cloud_site_id: str | None = None


class DeleteSiteResponse(ApiModel):
    deleted: bool = True
