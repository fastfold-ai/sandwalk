from __future__ import annotations

from pathlib import Path

from agent.hitl.context import reset_hitl_context, set_hitl_context
from agent_server.sites_service.core import SitesService
from agent_server.store import AgentStore
from tools import sites as sites_tool


def test_create_infers_session_and_project_from_run_context(
    tmp_path: Path, monkeypatch
) -> None:
    database = tmp_path / "agent.db"
    setup = AgentStore(database)
    project = setup.create_project(name="Research", folder_path=str(tmp_path))
    session = setup.create_session(
        title="Site session",
        workspace_path=str(tmp_path),
        project_id=project.id,
    )
    setup.close()

    source = tmp_path / "dist"
    source.mkdir()
    (source / "index.html").write_text("<h1>Site</h1>", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sites_tool, "AgentStore", lambda: AgentStore(database))
    monkeypatch.setattr(
        sites_tool,
        "SitesService",
        lambda store: SitesService(store, root=tmp_path / "managed"),
    )

    token = set_hitl_context(session_id=session.id, headless=True)
    try:
        result = sites_tool.manage(action="create", name="Report", path="dist")
    finally:
        reset_hitl_context(token)

    assert result["ok"] is True, result
    store = AgentStore(database)
    try:
        site = store.get_site(result["site"]["id"])
        assert site is not None
        assert site.origin_session_id == session.id
        assert site.origin_project_id == project.id
    finally:
        store.close()
