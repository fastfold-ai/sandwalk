"""Resolve FastFold Cloud account details for the General settings page.

Split package — re-exports the public surface previously defined in
``agent_server/account_service.py`` so existing imports keep working.

NOTE: ``Config`` and ``_request_json`` stay bound at this package-root level
(not in a submodule) because tests patch them via the flat dotted path
``agent_server.account_service.<name>``, and the functions that call them
(``_resolve_user``, ``_resolve_plan_and_workspace``) must live in the same
module namespace for that patch to take effect.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from agent.config import Config
from agent_server.account_service.builder import build_summary
from agent_server.account_service.helpers import (
    api_key,
    cloud_base_url,
    format_plan_label,
    latest_pypi_version,
    normalize_plan_code,
    select_best_plan,
)
from agent_server.integrations_service import IntegrationsService
from agent_server.models import AccountAbout, AccountSummary

_BILLING_URL = "https://cloud.fastfold.ai/billing"

# Re-exported for backward-compat imports (e.g. tests importing this name directly).
_format_plan_label = format_plan_label


def _request_json(url: str, api_key_value: str, *, timeout: float = 4.0) -> dict[str, Any] | None:
    req = urllib.request.Request(
        url=url,
        headers={
            "Authorization": f"Bearer {api_key_value}",
            "X-API-Key": api_key_value,
            "Accept": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError):
        return None
    try:
        payload = json.loads(text) if text else {}
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _resolve_user(api_key_value: str, base_url: str) -> tuple[str | None, str | None, str | None]:
    """Return (user_id, email, username) from cloud identity endpoints.

    Prefer dual-auth: ``/v1/users/me`` is not routed on api.fastfold.ai (404) and
    only wastes a round-trip before the working fallback.
    """
    for path in ("/v1/example/dual-auth", "/v1/users/me"):
        payload = _request_json(f"{base_url}{path}", api_key_value)
        if not payload:
            continue
        user = payload.get("user") if isinstance(payload.get("user"), dict) else payload
        if not isinstance(user, dict):
            continue
        user_id = str(user.get("id") or "").strip() or None
        email = str(user.get("email") or "").strip() or None
        username = str(user.get("username") or "").strip() or None
        if email or user_id:
            return user_id, email, username
    return None, None, None


def _resolve_plan_and_workspace(
    api_key_value: str, base_url: str
) -> tuple[str | None, str | None, str | None]:
    """Return (plan_code, workspace_id, team_id) preferring the highest paid plan."""
    payload = _request_json(f"{base_url}/v1/billing/workspaces/plans", api_key_value)
    if not payload:
        return None, None, None
    items = payload.get("items")
    if not isinstance(items, list):
        return None, None, None

    best = select_best_plan(items)
    if best is None:
        return None, None, None
    return (
        normalize_plan_code(str(best.get("plan_code") or "")),
        str(best.get("workspace_id") or "").strip() or None,
        str(best.get("team_id") or "").strip() or None,
    )


class AccountService:
    def __init__(self, *, integrations: IntegrationsService | None = None) -> None:
        self._integrations = integrations or IntegrationsService()

    def get(self, *, version: str, check_updates: bool = False) -> AccountSummary:
        cfg = Config.load()
        key = api_key(cfg)
        about = self._about(version=version, check_updates=check_updates)
        if not key:
            return AccountSummary(
                configured=False,
                billing_url=_BILLING_URL,
                about=about,
            )

        base_url = cloud_base_url()
        # User + billing are independent — fetch in parallel (~max of both, not sum).
        with ThreadPoolExecutor(max_workers=2) as pool:
            user_future = pool.submit(_resolve_user, key, base_url)
            plan_future = pool.submit(_resolve_plan_and_workspace, key, base_url)
            user_id, email, username = user_future.result()
            plan_code, workspace_id, team_id = plan_future.result()

        return build_summary(
            user_id=user_id,
            email=email,
            username=username,
            plan_code=plan_code,
            workspace_id=workspace_id,
            team_id=team_id,
            billing_url=_BILLING_URL,
            about=about,
        )

    def logout(self) -> AccountSummary:
        try:
            self._integrations.remove("fastfold-cloud")
        except KeyError:
            cfg = Config.load()
            cfg.unset("api.fastfold_cloud_key")
            cfg.save()
        from _version import __version__

        return self.get(version=__version__, check_updates=False)

    @staticmethod
    def _about(*, version: str, check_updates: bool) -> AccountAbout:
        latest = latest_pypi_version() if check_updates else None
        up_to_date = None
        if latest:
            up_to_date = latest == version
        elif check_updates:
            up_to_date = True
        return AccountAbout(
            product="FastFold Agent",
            version=version,
            channel="default",
            latest_version=latest,
            up_to_date=up_to_date,
            licenses_url="https://github.com/fastfold-ai/sandwalk/blob/main/LICENSE",
        )


__all__ = ["AccountService", "_format_plan_label"]
