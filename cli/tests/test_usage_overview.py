"""Usage ledger + overview aggregation."""

from __future__ import annotations

import sqlite3
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


def test_usage_overview_excludes_bench_sessions(tmp_path: Path, monkeypatch):
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
    chat = store.create_session(title="hi", workspace_path=None)
    cell = store.create_session(
        title="MMLU · anatomy", workspace_path=None, source="bench"
    )
    today = __import__("datetime").date.today().isoformat()
    store.upsert_usage_run(
        run_id="r-chat",
        session_id=chat.id,
        day=today,
        surface="ui",
        model_id="model-a",
        provider="openai",
        input_tokens=10,
        output_tokens=0,
    )
    store.upsert_usage_run(
        run_id="r-bench",
        session_id=cell.id,
        day=today,
        surface="ui",
        model_id="model-b",
        provider="openai",
        input_tokens=5000,
        output_tokens=0,
    )
    overview = build_usage_overview(store)
    assert overview.lifetime_tokens == 10
    assert overview.models_used == 1
    project = store.create_project(name="Bench · MMLU", folder_path=None)
    store.update_session(cell.id, project_id=project.id, update_project_id=True)
    scoped = build_usage_overview(store, project_id=project.id)
    assert scoped.lifetime_tokens == 5000


def test_usage_overview_includes_bench_rollup(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SANDWALK_SETTINGS_PATH", str(tmp_path / "auth.json"))
    monkeypatch.setattr(
        "agent_server.usage_service.backfill._trajectory_paths",
        lambda: [],
    )
    from agent_server.bench_service.usage_rollup import rollup_suite_usage

    chat = AgentStore(tmp_path / "chat.db", exclusive=True)
    bench = AgentStore(tmp_path / "bench.db", exclusive=True)
    try:
        for key in (
            "usage_backfill_v1",
            "usage_model_repair_v1",
            "usage_provider_repair_v1",
            "usage_alias_repair_v1",
        ):
            chat.set_usage_meta(key, "done")
        project = chat.create_project(name="Research", folder_path=None)
        today = __import__("datetime").date.today().isoformat()
        chat.upsert_usage_run(
            run_id="r-chat",
            session_id="s-chat",
            day=today,
            surface="ui",
            model_id="model-a",
            provider="openai",
            input_tokens=10,
            output_tokens=0,
        )
        cell_project = bench.create_project(name="Bench · MMLU", folder_path=None)
        cell = bench.create_session(
            title="cell",
            workspace_path=None,
            project_id=cell_project.id,
            source="bench",
        )
        bench.upsert_usage_run(
            run_id="cell-run",
            session_id=cell.id,
            day=today,
            input_tokens=500,
            output_tokens=20,
        )
        result = rollup_suite_usage(
            chat_store=chat,
            bench_store=bench,
            result={
                "run_id": "suite-1",
                "project_id": cell_project.id,
                "model_id": "model-b",
                "provider": "openrouter",
            },
            usage_project_id=project.id,
        )
        assert result["lifetime_tokens"] == 520
        overview = build_usage_overview(chat)
        assert overview.lifetime_tokens == 530
        scoped = build_usage_overview(chat, project_id=project.id)
        assert scoped.lifetime_tokens == 520
        again = rollup_suite_usage(
            chat_store=chat,
            bench_store=bench,
            result={
                "run_id": "suite-1",
                "project_id": cell_project.id,
                "model_id": "model-b",
                "provider": "openrouter",
            },
            usage_project_id=project.id,
        )
        overview2 = build_usage_overview(chat)
        assert again["lifetime_tokens"] == 520
        assert overview2.lifetime_tokens == 530
    finally:
        chat.close()
        bench.close()


def test_lifetime_tokens_by_project_batches_and_caches(tmp_path: Path):
    store = AgentStore(tmp_path / "usage.db", exclusive=True)
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
        input_tokens=80,
        output_tokens=20,
    )
    store.upsert_usage_run(
        run_id="r-b",
        session_id=session_b.id,
        day=today,
        input_tokens=5,
        output_tokens=7,
    )
    first = store.lifetime_tokens_by_project(
        [project_a.id, project_b.id, "missing-project"]
    )
    assert first[project_a.id] == 100
    assert first[project_b.id] == 12
    assert first["missing-project"] == 0
    store.upsert_usage_run(
        run_id="r-a",
        session_id=session_a.id,
        day=today,
        input_tokens=999,
        output_tokens=0,
    )
    cached = store.lifetime_tokens_by_project([project_a.id])
    assert cached[project_a.id] == 100
    from agent_server.store import usage as usage_mod

    usage_mod._project_token_cache.clear()
    fresh = store.lifetime_tokens_by_project([project_a.id])
    assert fresh[project_a.id] == 999


def test_open_existing_usage_runs_without_project_id(tmp_path: Path):
    """Packaged DBs already have usage_runs; schema indexes must not run first."""
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE usage_runs (
                run_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                day TEXT NOT NULL,
                surface TEXT NOT NULL DEFAULT 'unknown',
                model_id TEXT,
                provider TEXT,
                input_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                cache_read_tokens INTEGER NOT NULL DEFAULT 0,
                cache_creation_tokens INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );
            """
        )
    store = AgentStore(path, exclusive=True)
    try:
        with store._connect() as connection:
            names = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(usage_runs)")
            }
        assert "project_id" in names
        assert "kind" in names
        store.upsert_usage_run(
            run_id="suite-1",
            session_id=None,
            day="2026-08-18",
            kind="bench",
            input_tokens=1,
            output_tokens=0,
        )
        rows = store.list_usage_runs()
        assert rows[0]["kind"] == "bench"
        assert rows[0]["session_id"] is None
    finally:
        store.close()
