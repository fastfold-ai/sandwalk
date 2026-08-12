"""Usage ledger + overview aggregation."""

from __future__ import annotations

from pathlib import Path

from agent_server.store import AgentStore
from agent_server.usage_service.backfill import run_backfill
from agent_server.usage_service.overview import _streaks, build_usage_overview
from agent_server.usage_service.parse import (
    canonicalize_usage_model,
    parse_usage_tokens,
    resolve_client_surface,
)


def test_parse_usage_tokens_accepts_snake_and_camel():
    assert parse_usage_tokens(
        {"input_tokens": 10, "outputTokens": 3, "cacheReadInputTokens": 2}
    ) == {
        "input_tokens": 10,
        "output_tokens": 3,
        "cache_read_tokens": 2,
        "cache_creation_tokens": 0,
    }


def test_resolve_client_surface_prefers_body_then_header():
    assert resolve_client_surface(body="ui", header="cli") == "ui"
    assert resolve_client_surface(body=None, header="cli") == "cli"
    assert resolve_client_surface(source="slack") == "slack"


def test_streaks_longest_and_current():
    from datetime import date, timedelta

    today = date(2026, 8, 7)
    active = {
        today - timedelta(days=offset)
        for offset in (0, 1, 2, 5, 6, 7, 8)
    }
    longest, current = _streaks(active, today)
    assert longest == 4
    assert current == 3


def test_canonicalize_bench_aliases_to_registered_models():
    assert canonicalize_usage_model("luna-pro") == ("openai", "gpt-5.6-luna-pro")
    assert canonicalize_usage_model("deepseek-pro") == ("deepseek", "deepseek-v4-pro")
    assert canonicalize_usage_model("deepseek-flash") == (
        "qwen",
        "deepseek-v4-flash-0731",
    )
    assert canonicalize_usage_model("openai/gpt-5.6-luna-pro") == (
        "openai",
        "gpt-5.6-luna-pro",
    )
    assert canonicalize_usage_model("moonshotai/kimi-k3") == ("moonshot", "kimi-k3")


def test_usage_overview_merges_bench_alias_into_registered_model(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setenv("SANDWALK_SETTINGS_PATH", str(tmp_path / "auth.json"))
    monkeypatch.setattr(
        "agent_server.usage_service.backfill._trajectory_paths",
        lambda: [],
    )
    store = AgentStore(tmp_path / "usage.db", exclusive=True)
    for key in (
        "usage_backfill_v1",
        "usage_model_repair_v1",
        "usage_provider_repair_v1",
        "usage_alias_repair_v1",
    ):
        store.set_usage_meta(key, "done")
    today = __import__("datetime").date.today().isoformat()
    store.upsert_usage_run(
        run_id="r-real",
        session_id="s-real",
        day=today,
        surface="ui",
        model_id="gpt-5.6-luna-pro",
        provider="openai",
        input_tokens=100,
        output_tokens=0,
    )
    store.upsert_usage_run(
        run_id="r-alias",
        session_id="s-alias",
        day=today,
        surface="ui",
        model_id="luna-pro",
        input_tokens=50,
        output_tokens=0,
    )
    overview = build_usage_overview(store)
    assert overview.models_used == 1
    assert overview.top_models[0].model_id == "gpt-5.6-luna-pro"
    assert overview.top_models[0].provider == "openai"
    assert overview.top_models[0].tokens == 150


def test_usage_overview_aggregates(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SANDWALK_SETTINGS_PATH", str(tmp_path / "auth.json"))
    # Avoid importing real ~/.sandwalk trajectories into this hermetic DB.
    monkeypatch.setattr(
        "agent_server.usage_service.backfill._trajectory_paths",
        lambda: [],
    )
    store = AgentStore(tmp_path / "usage.db", exclusive=True)
    store.set_usage_meta("usage_backfill_v1", "done")
    store.set_usage_meta("usage_model_repair_v1", "done")
    store.set_usage_meta("usage_provider_repair_v1", "done")
    store.set_usage_meta("usage_alias_repair_v1", "done")
    today = __import__("datetime").date.today().isoformat()
    store.upsert_usage_run(
        run_id="r-ui",
        session_id="s-ui",
        day=today,
        surface="ui",
        model_id="model-a",
        provider="openai",
        input_tokens=100,
        output_tokens=20,
    )
    store.upsert_usage_run(
        run_id="r-cli",
        session_id="s-cli",
        day=today,
        surface="cli",
        model_id="model-b",
        provider="anthropic",
        input_tokens=50,
        output_tokens=10,
    )
    store.upsert_usage_run(
        run_id="r-cli-2",
        session_id="s-cli-2",
        day=today,
        surface="cli",
        model_id="model-a",
        provider="openrouter",
        input_tokens=30,
        output_tokens=5,
    )
    overview = build_usage_overview(store)
    assert overview.lifetime_tokens == 215
    assert overview.ui_tokens == 120
    assert overview.cli_tokens == 95
    assert overview.models_used == 3
    assert overview.top_models[0].model_id == "model-a"
    assert overview.top_models[0].provider == "openai"
    assert any(
        row.model_id == "model-a" and row.provider == "openrouter"
        for row in overview.top_models
    )
    assert overview.cli_share == round(95 / 215, 4)
    assert overview.ui_share == round(120 / 215, 4)
    assert overview.current_streak_days >= 1
    assert overview.longest_streak_days >= 1
    assert any(
        item.model_id == "model-a" and item.provider == "openai"
        for item in overview.chart_models
    )
    assert any(
        point.day == today
        and point.model_id == "model-a"
        and point.provider == "openai"
        for point in overview.model_days
    )


def test_backfill_from_events_uses_last_cumulative(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SANDWALK_SETTINGS_PATH", str(tmp_path / "auth.json"))
    monkeypatch.setattr(
        "agent_server.usage_service.backfill._trajectory_paths",
        lambda: [],
    )
    store = AgentStore(tmp_path / "usage.db", exclusive=True)
    session = store.create_session(
        title="t",
        workspace_path=None,
        client_surface="ui",
    )
    store.set_session_status(session.id, "running")
    store.append_event(
        session_id=session.id,
        run_id="run-1",
        event_type="run.usage",
        payload={"input_tokens": 10, "output_tokens": 1},
    )
    store.append_event(
        session_id=session.id,
        run_id="run-1",
        event_type="run.usage",
        payload={"input_tokens": 40, "output_tokens": 5, "modelId": "m1"},
    )
    result = run_backfill(store, force=True)
    assert result.from_events == 1
    rows = store.list_usage_runs()
    assert len(rows) == 1
    assert rows[0]["input_tokens"] == 40
    assert rows[0]["output_tokens"] == 5
    assert rows[0]["model_id"] == "m1"
    assert rows[0]["surface"] == "ui"


def test_backfill_recovers_model_from_session_title(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SANDWALK_SETTINGS_PATH", str(tmp_path / "auth.json"))
    monkeypatch.setattr(
        "agent_server.usage_service.backfill._trajectory_paths",
        lambda: [],
    )
    store = AgentStore(tmp_path / "usage.db", exclusive=True)
    session = store.create_session(
        title="ARC Challenge · deepseek-v4-flash-0731",
        workspace_path=None,
        client_surface="ui",
    )
    store.set_session_status(session.id, "running")
    store.append_event(
        session_id=session.id,
        run_id="run-title",
        event_type="run.usage",
        payload={"input_tokens": 100, "output_tokens": 5},
    )
    run_backfill(store, force=True)
    rows = store.list_usage_runs()
    assert len(rows) == 1
    assert rows[0]["model_id"] == "deepseek-v4-flash-0731"


def test_usage_overview_filters_by_project(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SANDWALK_SETTINGS_PATH", str(tmp_path / "auth.json"))
    monkeypatch.setattr(
        "agent_server.usage_service.backfill._trajectory_paths",
        lambda: [],
    )
    store = AgentStore(tmp_path / "usage.db", exclusive=True)
    for key in (
        "usage_backfill_v1",
        "usage_model_repair_v1",
        "usage_provider_repair_v1",
        "usage_alias_repair_v1",
    ):
        store.set_usage_meta(key, "done")
    project_a = store.create_project(name="A", folder_path=None)
    project_b = store.create_project(name="B", folder_path=None)
    session_a = store.create_session(
        title="in-a", workspace_path=None, project_id=project_a.id
    )
    session_b = store.create_session(
        title="in-b", workspace_path=None, project_id=project_b.id
    )
    today = __import__("datetime").date.today().isoformat()
    store.upsert_usage_run(
        run_id="r-a",
        session_id=session_a.id,
        day=today,
        surface="ui",
        model_id="model-a",
        provider="openai",
        input_tokens=100,
        output_tokens=0,
    )
    store.upsert_usage_run(
        run_id="r-b",
        session_id=session_b.id,
        day=today,
        surface="ui",
        model_id="model-b",
        provider="openai",
        input_tokens=50,
        output_tokens=0,
    )
    global_overview = build_usage_overview(store)
    assert global_overview.lifetime_tokens == 150
    scoped = build_usage_overview(store, project_id=project_a.id)
    assert scoped.lifetime_tokens == 100
    assert scoped.models_used == 1
    empty = build_usage_overview(store, project_id="missing-project")
    assert empty.lifetime_tokens == 0
