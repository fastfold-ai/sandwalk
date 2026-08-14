from pathlib import Path

from agent_server.store import AgentStore


def test_list_sessions_includes_bench_in_project(tmp_path: Path):
    store = AgentStore(tmp_path / "agent.db")
    try:
        project = store.create_project(name="Suite", folder_path=None)
        chat = store.create_session(
            title="Chat",
            workspace_path=None,
            project_id=project.id,
        )
        cell = store.create_session(
            title="cell",
            workspace_path=None,
            project_id=project.id,
            source="bench",
        )
        listed = store.list_sessions(project_id=project.id)
        assert {item.id for item in listed} == {chat.id, cell.id}
        global_list = store.list_sessions()
        assert [item.id for item in global_list] == [chat.id]
        hidden = store.list_sessions(project_id=project.id, include_bench=False)
        assert [item.id for item in hidden] == [chat.id]
        assert store.sessions_revision().startswith("1:")
        found = store.search_sessions("cell")
        assert [item.id for item in found] == [cell.id]
    finally:
        store.close()
