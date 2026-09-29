"""Bench projects are created on the bench database but listed from the chat one."""

from __future__ import annotations

from pathlib import Path

from agent_server.app import create_app
from agent_server.store import AgentStore


def test_existing_bench_project_shows_up_on_the_chat_store(tmp_path: Path) -> None:
    bench = AgentStore(tmp_path / "bench-agent.db")
    project = bench.create_project(
        name="bench · BixBench · sample · 2026-09-29 0556",
        description="sandwalk-bench batch",
        icon="sparkles",
        color="purple",
        pinned=True,
    )
    bench.close()

    app = create_app(store_path=tmp_path / "agent.db", allowed_hosts=["testserver"])
    try:
        copied = app.state.store.get_project(project.id)
        assert copied is not None
        assert copied.name == project.name
        assert copied.pinned is True
        names = [item.name for item in app.state.store.list_projects()]
        assert project.name in names
    finally:
        app.state.store.close()
        app.state.deps.bench_store.close()
