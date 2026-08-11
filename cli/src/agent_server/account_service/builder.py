"""Pure builder for AccountSummary given already-resolved identity/plan data."""

from __future__ import annotations

from agent_server.account_service.helpers import format_plan_label
from agent_server.models import AccountAbout, AccountOrganization, AccountSummary, AccountUser


def build_summary(
    *,
    user_id: str | None,
    email: str | None,
    username: str | None,
    plan_code: str | None,
    workspace_id: str | None,
    team_id: str | None,
    billing_url: str,
    about: AccountAbout,
) -> AccountSummary:
    plan_label = format_plan_label(plan_code or "")
    if plan_label and not plan_label.lower().endswith("plan"):
        plan_label = f"{plan_label} plan"

    org_name = None
    if email:
        org_name = f"{email}'s Organization"
    elif username:
        org_name = f"{username}'s Organization"

    return AccountSummary(
        configured=True,
        user=AccountUser(
            id=user_id,
            email=email,
            username=username,
            plan_code=plan_code,
            plan_label=plan_label or None,
        )
        if (email or username or user_id or plan_code)
        else None,
        organization=AccountOrganization(
            id=workspace_id or team_id or user_id,
            name=org_name,
            team_id=team_id,
        )
        if (workspace_id or team_id or user_id or org_name)
        else None,
        billing_url=billing_url,
        about=about,
    )
