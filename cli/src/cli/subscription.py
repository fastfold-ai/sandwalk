"""Fastfold subscription tier resolution (billing API + local fallback)."""

import json
import os
import urllib.error
import urllib.request


def _resolve_fastfold_subscription_tier(cfg) -> str:
    """Resolve Fastfold subscription tier from API, with local fallback."""
    fallback_raw = str(
        os.environ.get("FASTFOLD_SUBSCRIPTION_TIER")
        or cfg.get("fastfold.subscription_tier", "")
        or ""
    ).strip().lower()

    def _normalize_plan_code(raw: str) -> str:
        value = str(raw or "").strip().lower()
        if value in {"pro+", "pro-plus", "pro plus"}:
            return "pro_plus"
        return value

    def _plan_rank(plan_code: str) -> int:
        ranks = {
            "free": 0,
            "pro": 1,
            "pro_plus": 2,
            "ultra": 3,
        }
        return ranks.get(plan_code, -1)

    fallback = _normalize_plan_code(fallback_raw)
    if _plan_rank(fallback) < 0:
        fallback = ""

    api_key = str(
        os.environ.get("FASTFOLD_API_KEY")
        or cfg.get("api.fastfold_cloud_key")
        or ""
    ).strip()
    if not api_key:
        return fallback

    base_url = (
        os.environ.get("FASTFOLD_API_BASE_URL", "https://api.fastfold.ai").strip()
        or "https://api.fastfold.ai"
    )
    url = f"{base_url.rstrip('/')}/v1/billing/workspaces/plans"
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
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            text = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        # Billing endpoints are currently cookie-auth only. For API-key callers,
        # avoid showing a misleading default plan when backend returns 401.
        if exc.code == 401:
            return fallback
        return fallback
    except (urllib.error.URLError, TimeoutError):
        return fallback

    try:
        payload = json.loads(text) if text else {}
    except Exception:
        return fallback
    if not isinstance(payload, dict):
        return fallback

    items = payload.get("items")
    if not isinstance(items, list):
        return fallback

    best_plan = None
    for item in items:
        if not isinstance(item, dict):
            continue
        raw_plan = _normalize_plan_code(str(item.get("plan_code") or ""))
        if not raw_plan:
            continue
        if best_plan is None or _plan_rank(raw_plan) > _plan_rank(best_plan):
            best_plan = raw_plan

    resolved = best_plan or fallback
    return resolved if _plan_rank(resolved) >= 0 else fallback


def _format_plan_label(plan_code: str) -> str:
    """Convert normalized plan code to friendly display label."""
    normalized = str(plan_code or "").strip().lower()
    if normalized == "pro_plus":
        return "Pro+"
    if not normalized:
        return ""
    return normalized.replace("_", " ").title()


def _resolve_fastfold_subscription_tier_local(cfg) -> str:
    """Resolve tier from local/env hints only (no network)."""
    raw = str(
        os.environ.get("FASTFOLD_SUBSCRIPTION_TIER")
        or cfg.get("fastfold.subscription_tier", "")
        or ""
    ).strip().lower()
    if raw in {"pro+", "pro-plus", "pro plus"}:
        return "pro_plus"
    return raw
