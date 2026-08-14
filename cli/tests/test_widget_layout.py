"""Widget layout defaults and dashboard preference persistence."""

from __future__ import annotations

from pathlib import Path

from agent_server.store import AgentStore
from agent_server.widget_layout import (
    DASHBOARD_LAYOUT_META_KEY,
    default_overview_layout,
    default_project_home_layout,
    parse_layout,
    resolve_overview_layout,
)


def test_default_layouts_include_expected_widgets():
    home = default_project_home_layout()
    overview = default_overview_layout()
    assert home["version"] == 6
    assert overview["version"] == 7
    home_types = [w["type"] for w in home["widgets"]]
    overview_types = [w["type"] for w in overview["widgets"]]
    assert home_types == [
        "project-description",
        "usage-hero",
        "stat-longest-agent",
        "stat-chats",
        "stat-longest-streak",
        "stat-current-streak",
        "activity-heatmap",
        "bench-results",
    ]
    assert home["widgets"][0]["size"] == "lg"
    assert "bench-results" not in overview_types
    assert overview_types == [
        "usage-hero",
        "stat-longest-agent",
        "stat-chats",
        "stat-longest-streak",
        "stat-current-streak",
        "activity-heatmap",
        "stat-peak-day",
        "stat-models-used",
        "stat-messages",
        "stat-tokens-in",
        "stat-tokens-out",
        "stat-cache-hit",
        "stat-avg-tokens-chat",
        "stat-files-size",
        "models-chart",
        "models-top-list",
    ]
    assert "stat-runs" not in overview_types
    assert all("size" in w for w in home["widgets"])
    assert all("size" in w for w in overview["widgets"])


def test_resolve_overview_layout_reseeds_stale_version():
    stale = {
        "version": 5,
        "widgets": [{"id": "a", "type": "usage-hero", "size": "lg"}],
    }
    resolved = resolve_overview_layout(__import__("json").dumps(stale))
    assert resolved["version"] == 7
    assert "stat-files-size" in [w["type"] for w in resolved["widgets"]]
    assert "stat-runs" not in [w["type"] for w in resolved["widgets"]]
    assert "models-chart" in [w["type"] for w in resolved["widgets"]]


def test_create_project_sets_default_home_layout(tmp_path: Path):
    store = AgentStore(tmp_path / "layout.db", exclusive=True)
    project = store.create_project(name="Widgets", folder_path=None)
    assert project.home_layout is not None
    assert project.home_layout["version"] == 6
    assert project.home_layout["widgets"][0]["type"] == "project-description"
    assert project.home_layout["widgets"][0]["size"] == "lg"
    assert project.home_layout["widgets"][1]["type"] == "usage-hero"
    assert [w["type"] for w in project.home_layout["widgets"]][-1] == (
        "bench-results"
    )


def test_dashboard_layout_meta_roundtrip(tmp_path: Path):
    store = AgentStore(tmp_path / "layout.db", exclusive=True)
    layout = default_overview_layout()
    layout["widgets"] = layout["widgets"][::-1]
    store.set_usage_meta(DASHBOARD_LAYOUT_META_KEY, __import__("json").dumps(layout))
    parsed = parse_layout(store.get_usage_meta(DASHBOARD_LAYOUT_META_KEY))
    assert parsed is not None
    assert [w["type"] for w in parsed["widgets"]] == [
        w["type"] for w in layout["widgets"]
    ]
