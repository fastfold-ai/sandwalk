from __future__ import annotations

from typing import Literal

from pydantic import Field

from agent_server.models.base import ApiModel


class SkillSummary(ApiModel):
    name: str
    description: str
    tags: list[str] = Field(default_factory=list)
    source: str
    author: str
    category: str = ""
    version: str | None = None
    updated_at: str | None = None
    icon_src: str | None = None
    enabled: bool = True


class SkillList(ApiModel):
    data: list[SkillSummary]


class SkillDetail(SkillSummary):
    content: str
    directory: str | None = None


class InstallSkillRequest(ApiModel):
    source: str = Field(min_length=1)


class UpdateSkillRequest(ApiModel):
    enabled: bool | None = None


class SkillMutationResponse(ApiModel):
    ok: bool
    summary: str
    installed: list[str] = Field(default_factory=list)


SkillBatchAction = Literal["enable", "disable", "remove"]


class SkillBatchActionRequest(ApiModel):
    action: SkillBatchAction
    names: list[str] = Field(default_factory=list)


class SkillBatchActionFailure(ApiModel):
    name: str
    reason: str


class SkillBatchActionResponse(ApiModel):
    ok: bool
    action: SkillBatchAction
    requested: int
    succeeded: list[str] = Field(default_factory=list)
    failed: list[SkillBatchActionFailure] = Field(default_factory=list)
    summary: str


class SkillSource(ApiModel):
    provider: str
    source: str
    url: str
    description: str


class SkillSourceList(ApiModel):
    data: list[SkillSource]


class CatalogSkill(ApiModel):
    id: str
    slug: str
    name: str
    source: str
    installs: int = 0
    source_type: str = ""
    install_url: str | None = None
    url: str | None = None


class CatalogSkillList(ApiModel):
    data: list[CatalogSkill]
    query: str
    count: int = 0


class CatalogLeaderboard(ApiModel):
    data: list[CatalogSkill]
    view: str = "all-time"
    page: int = 0
    per_page: int = 50
    # Unique skills in the ranked list (API pagination.total — ~9.6K today).
    total: int = 0
    # Homepage "All Time (986,330)" badge — distinct from ``total``.
    all_time_total: int = 0
    has_more: bool = False
    count: int = 0


class CatalogSkillFile(ApiModel):
    path: str
    contents: str


class CatalogSkillDetail(ApiModel):
    id: str
    source: str
    slug: str
    installs: int = 0
    hash: str | None = None
    files: list[CatalogSkillFile] | None = None
    # skills.sh page Summary (rich markdown; distinct from SKILL.md description).
    summary: str | None = None
    github_stars: int | None = None
    first_seen: str | None = None


class CatalogSkillAuditEntry(ApiModel):
    provider: str
    slug: str
    status: str
    summary: str
    audited_at: str | None = None
    risk_level: str | None = None
    categories: list[str] = Field(default_factory=list)


class CatalogSkillAudit(ApiModel):
    id: str
    source: str
    slug: str
    audits: list[CatalogSkillAuditEntry] = Field(default_factory=list)
