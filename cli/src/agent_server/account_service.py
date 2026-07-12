"""Resolve FastFold Cloud account details for the General settings page."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from agent.config import Config
from agent_server.integrations_service import IntegrationsService
from agent_server.models import AccountAbout, AccountOrganization, AccountSummary, AccountUser

_DEFAULT_CLOUD_BASE = "https://api.fastfold.ai"
_BILLING_URL = "https://cloud.fastfold.ai/billing"
_PYPI_URL = "https://pypi.org/pypi/fastfold-agent-cli/json"


def _cloud_base_url() -> str:
    return (
        os.environ.get("FASTFOLD_API_BASE_URL", _DEFAULT_CLOUD_BASE).strip()
        or _DEFAULT_CLOUD_BASE
    ).rstrip("/")


def _api_key(cfg: Config | None = None) -> str:
    config = cfg or Config.load()
    return str(
        os.environ.get("FASTFOLD_API_KEY")
        or config.get("api.fastfold_cloud_key")
        or ""
    ).strip()


def _request_json(url: str, api_key: str, *, timeout: float = 4.0) -> dict[str, Any] | None:
    req = urllib.request.Request(
        url=url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "X-API-Key": api_key,
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


def _normalize_plan_code(raw: str) -> str:
    value = str(raw or "").strip().lower()
    if value in {"pro+", "pro-plus", "pro plus"}:
        return "pro_plus"
    return value


def _format_plan_label(plan_code: str) -> str:
    normalized = _normalize_plan_code(plan_code)
    if normalized == "pro_plus":
        return "Pro+"
    if not normalized:
        return ""
    return normalized.replace("_", " ").title()


def _plan_rank(plan_code: str) -> int:
    ranks = {"free": 0, "pro": 1, "pro_plus": 2, "ultra": 3}
    return ranks.get(_normalize_plan_code(plan_code), -1)


def _resolve_user(api_key: str, base_url: str) -> tuple[str | None, str | None, str | None]:
    """Return (user_id, email, username) from cloud identity endpoints.

    Prefer dual-auth: ``/v1/users/me`` is not routed on api.fastfold.ai (404) and
    only wastes a round-trip before the working fallback.
    """
    for path in ("/v1/example/dual-auth", "/v1/users/me"):
        payload = _request_json(f"{base_url}{path}", api_key)
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


def _resolve_plan_and_workspace(api_key: str, base_url: str) -> tuple[str | None, str | None, str | None]:
    """Return (plan_code, workspace_id, team_id) preferring the highest paid plan."""
    payload = _request_json(f"{base_url}/v1/billing/workspaces/plans", api_key)
    if not payload:
        return None, None, None
    items = payload.get("items")
    if not isinstance(items, list):
        return None, None, None

    best: dict[str, Any] | None = None
    best_rank = -1
    for item in items:
        if not isinstance(item, dict):
            continue
        plan_code = _normalize_plan_code(str(item.get("plan_code") or ""))
        if not plan_code:
            continue
        rank = _plan_rank(plan_code)
        if best is None or rank > best_rank:
            best = item
            best_rank = rank

    if best is None:
        return None, None, None
    return (
        _normalize_plan_code(str(best.get("plan_code") or "")),
        str(best.get("workspace_id") or "").strip() or None,
        str(best.get("team_id") or "").strip() or None,
    )


def _latest_pypi_version(*, timeout: float = 3.0) -> str | None:
    req = urllib.request.Request(url=_PYPI_URL, headers={"Accept": "application/json"}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8", errors="replace")
        payload = json.loads(text) if text else {}
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    info = payload.get("info")
    if not isinstance(info, dict):
        return None
    version = str(info.get("version") or "").strip()
    return version or None


class AccountService:
    def __init__(self, *, integrations: IntegrationsService | None = None) -> None:
        self._integrations = integrations or IntegrationsService()

    def get(self, *, version: str, check_updates: bool = False) -> AccountSummary:
        cfg = Config.load()
        api_key = _api_key(cfg)
        about = self._about(version=version, check_updates=check_updates)
        if not api_key:
            return AccountSummary(
                configured=False,
                billing_url=_BILLING_URL,
                about=about,
            )

        base_url = _cloud_base_url()
        # User + billing are independent — fetch in parallel (~max of both, not sum).
        with ThreadPoolExecutor(max_workers=2) as pool:
            user_future = pool.submit(_resolve_user, api_key, base_url)
            plan_future = pool.submit(_resolve_plan_and_workspace, api_key, base_url)
            user_id, email, username = user_future.result()
            plan_code, workspace_id, team_id = plan_future.result()
        plan_label = _format_plan_label(plan_code or "")
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
        latest = _latest_pypi_version() if check_updates else None
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
            licenses_url="https://github.com/fastfold-ai/fastfold-agent-cli/blob/main/LICENSE",
        )
