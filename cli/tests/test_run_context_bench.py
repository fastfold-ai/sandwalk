from pathlib import Path

from agent_server.service.context import build_run_context
from agent_server.store import AgentStore


def test_bench_session_skips_dashboard_mcp(tmp_path: Path, monkeypatch):
    store = AgentStore(tmp_path / "agent.db")
    monkeypatch.setattr(
        "agent_server.mcp_service.McpService.resolve_runtime_servers",
        lambda self: [{"id": "hf", "name": "Hugging Face", "enabled": True}],
    )
    chat = store.create_session(title="Chat", workspace_path=None)
    cell = store.create_session(title="cell", workspace_path=None, source="bench")
    try:
        assert build_run_context(store, chat.id).mcp_servers
        assert build_run_context(store, cell.id).mcp_servers == []
    finally:
        store.close()
