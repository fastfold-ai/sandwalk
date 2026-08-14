"""Default widget board layouts (Project Home + Dashboard Overview)."""

from __future__ import annotations

import json
import uuid
from typing import Any

WidgetSize = str  # "sm" | "md" | "lg"
LAYOUT_VERSION = 6
OVERVIEW_LAYOUT_VERSION = 7


def _item(widget_type: str, size: WidgetSize = "sm") -> dict[str, str]:
    return {"id": str(uuid.uuid4()), "type": widget_type, "size": size}


def default_project_home_layout() -> dict[str, Any]:
    """Seed: description → usage → streak metrics → activity → bench."""
    return {
        "version": LAYOUT_VERSION,
        "widgets": [
            _item("project-description", "lg"),
            _item("usage-hero", "lg"),
            _item("stat-longest-agent", "sm"),
            _item("stat-chats", "sm"),
            _item("stat-longest-streak", "sm"),
            _item("stat-current-streak", "sm"),
            _item("activity-heatmap", "lg"),
            _item("bench-results", "lg"),
        ],
    }


def default_overview_layout() -> dict[str, Any]:
    """Full seed: every overview catalog widget (4-wide metric rows)."""
    return {
        "version": OVERVIEW_LAYOUT_VERSION,
        "widgets": [
            _item("usage-hero", "lg"),
            _item("stat-longest-agent", "sm"),
            _item("stat-chats", "sm"),
            _item("stat-longest-streak", "sm"),
            _item("stat-current-streak", "sm"),
            _item("activity-heatmap", "lg"),
            _item("stat-peak-day", "sm"),
            _item("stat-models-used", "sm"),
            _item("stat-messages", "sm"),
            _item("stat-tokens-in", "sm"),
            _item("stat-tokens-out", "sm"),
            _item("stat-cache-hit", "sm"),
            _item("stat-avg-tokens-chat", "sm"),
            _item("stat-files-size", "sm"),
            _item("models-chart", "lg"),
            _item("models-top-list", "lg"),
        ],
    }


def default_project_home_layout_json() -> str:
    return json.dumps(default_project_home_layout(), separators=(",", ":"))


def parse_layout(raw: str | None) -> dict[str, Any] | None:
    if not raw or not str(raw).strip():
        return None
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(parsed, dict):
        return None
    widgets = parsed.get("widgets")
    if not isinstance(widgets, list):
        return None
    return parsed


def resolve_overview_layout(raw: str | None) -> dict[str, Any]:
    """Return stored overview layout, or reseed when missing/stale."""
    parsed = parse_layout(raw)
    if parsed is None:
        return default_overview_layout()
    version = parsed.get("version") or 1
    try:
        version_num = int(version)
    except (TypeError, ValueError):
        version_num = 1
    if version_num < OVERVIEW_LAYOUT_VERSION:
        return default_overview_layout()
    return parsed


DASHBOARD_LAYOUT_META_KEY = "dashboard_overview_layout"
