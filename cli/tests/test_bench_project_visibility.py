"""Opening a bench project lists its cells and their token usage."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from agent_server.app import create_app


def test_project_scope_sees_bench_sessions_and_tokens(tmp_path: Path) -> None:
    app = create_app(store_path=tmp_path / "agent.db", allowed_hosts=["testserver"])
    with TestClient(app) as client:
        deps = app.state.deps
        bench = deps.bench_store
        project = bench.create_project(name="bench · suite · 2026-09-29 0956")
        deps.store.insert_project_copy(project)
        session = deps.bench_service.create_session(
            title="question 1",
            workspace_path=None,
            project_id=project.id,
            source="bench",
        )
        bench.upsert_usage_run(
            run_id="run-1",
            session_id=session.id,
            day="2026-09-29",
            surface="ui",
            project_id=project.id,
            kind="bench",
            input_tokens=100,
            output_tokens=25,
        )

        listed = client.get("/v1/sessions", params={"projectId": project.id})
        assert listed.status_code == 200
        ids = [row["id"] for row in listed.json()["data"]]
        assert session.id in ids

        # Global list stays free of bench cells.
        global_list = client.get("/v1/sessions")
        assert session.id not in [row["id"] for row in global_list.json()["data"]]

        one = client.get(f"/v1/sessions/{session.id}")
        assert one.status_code == 200
        assert one.json()["title"] == "question 1"

        overview = client.get("/v1/usage/overview", params={"projectId": project.id})
        assert overview.status_code == 200
        assert overview.json()["lifetimeTokens"] == 125
        assert overview.json()["sessions"] == 1
