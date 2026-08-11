"""Pure helpers for account/plan formatting and cloud URL resolution."""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

from agent.config import Config

_DEFAULT_CLOUD_BASE = "https://api.fastfold.ai"
_PYPI_URL = "https://pypi.org/pypi/sandwalk/json"


def cloud_base_url() -> str:
    return (
        os.environ.get("FASTFOLD_API_BASE_URL", _DEFAULT_CLOUD_BASE).strip()
        or _DEFAULT_CLOUD_BASE
    ).rstrip("/")


def api_key(cfg: Config | None = None) -> str:
    config = cfg or Config.load()
    return str(
        os.environ.get("FASTFOLD_API_KEY")
        or config.get("api.fastfold_cloud_key")
        or ""
    ).strip()


def normalize_plan_code(raw: str) -> str:
    value = str(raw or "").strip().lower()
    if value in {"pro+", "pro-plus", "pro plus"}:
        return "pro_plus"
    return value


def format_plan_label(plan_code: str) -> str:
    normalized = normalize_plan_code(plan_code)
    if normalized == "pro_plus":
        return "Pro+"
    if not normalized:
        return ""
    return normalized.replace("_", " ").title()


def plan_rank(plan_code: str) -> int:
    ranks = {"free": 0, "pro": 1, "pro_plus": 2, "ultra": 3}
    return ranks.get(normalize_plan_code(plan_code), -1)


def select_best_plan(items: list[Any]) -> dict[str, Any] | None:
    """Pick the highest-ranked plan item (personal + team workspaces mixed)."""
    best: dict[str, Any] | None = None
    best_rank = -1
    for item in items:
        if not isinstance(item, dict):
            continue
        plan_code = normalize_plan_code(str(item.get("plan_code") or ""))
        if not plan_code:
            continue
        rank = plan_rank(plan_code)
        if best is None or rank > best_rank:
            best = item
            best_rank = rank
    return best


def latest_pypi_version(*, timeout: float = 3.0) -> str | None:
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
