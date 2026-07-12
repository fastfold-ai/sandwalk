"""Custom MCP static headers + headers-helper resolution."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from agent_server.mcp_service import (
    get_custom_headers,
    resolve_custom_server_headers,
    run_headers_helper_command,
)
from agent_server.store import AgentStore


def test_run_headers_helper_command_parses_json_object():
    out = run_headers_helper_command(
        "python3 -c 'import json; print(json.dumps({\"Authorization\": \"Bearer x\"}))'"
    )
    assert out == {"Authorization": "Bearer x"}


def test_run_headers_helper_command_rejects_non_json():
    assert run_headers_helper_command("echo not-json") is None


def test_resolve_custom_prefers_helper_over_static():
    cfg = MagicMock()
    cfg.get.return_value = {"Authorization": "Bearer static"}
    server = MagicMock()
    server.id = "abc"
    server.headers_helper_command = (
        "python3 -c 'import json; print(json.dumps({\"X-Dyn\": \"1\"}))'"
    )
    assert resolve_custom_server_headers(server, config=cfg) == {"X-Dyn": "1"}


def test_resolve_custom_falls_back_to_static_headers():
    cfg = MagicMock()
    cfg.get.return_value = {"X-API-Key": "secret"}
    server = MagicMock()
    server.id = "abc"
    server.headers_helper_command = None
    assert resolve_custom_server_headers(server, config=cfg) == {"X-API-Key": "secret"}
    assert get_custom_headers(cfg, "abc") == {"X-API-Key": "secret"}


def test_store_persists_custom_mcp_metadata(tmp_path: Path):
    store = AgentStore(tmp_path / "agent.db")
    server = store.create_mcp_server(
        name="Custom",
        transport="streamable_http",
        command=None,
        args=[],
        url="https://mcp.example.com",
        enabled=True,
        description="demo",
        oauth_client_id="cid",
        oauth_server_url="https://auth.example.com",
        oauth_scopes="openid profile",
        headers_helper_command='echo \'{"Authorization":"Bearer x"}\'',
    )
    loaded = store.list_mcp_servers()[0]
    assert loaded.id == server.id
    assert loaded.description == "demo"
    assert loaded.oauth_client_id == "cid"
    assert loaded.oauth_scopes == "openid profile"
    assert loaded.headers_helper_command.startswith("echo")

    updated = store.update_mcp_server(server.id, description="updated", enabled=False)
    assert updated is not None
    assert updated.description == "updated"
    assert updated.enabled is False
