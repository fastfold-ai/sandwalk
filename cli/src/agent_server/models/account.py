from __future__ import annotations

from agent_server.models.base import ApiModel


class AccountUser(ApiModel):
    id: str | None = None
    email: str | None = None
    username: str | None = None
    plan_code: str | None = None
    plan_label: str | None = None


class AccountOrganization(ApiModel):
    id: str | None = None
    name: str | None = None
    team_id: str | None = None


class AccountAbout(ApiModel):
    product: str = "FastFold Agent"
    version: str
    channel: str = "default"
    latest_version: str | None = None
    up_to_date: bool | None = None
    licenses_url: str | None = None


class AccountSummary(ApiModel):
    configured: bool = False
    user: AccountUser | None = None
    organization: AccountOrganization | None = None
    billing_url: str | None = None
    about: AccountAbout
