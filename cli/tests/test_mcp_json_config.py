"""Tests for mcp.json seed/export and catalog remove/re-add."""

from __future__ import annotations

from pathlib import Path

from agent.config import Config
from agent.mcp_catalog import MCP_CATALOG
from agent_server.mcp_json_config import (
    apply_mcp_json,
    export_mcp_json,
    get_or_export_mcp_json,
    get_removed_catalog_ids,
    install_catalog_server,
    mark_catalog_removed,
    seed_catalog_defaults,
    suggested_catalog_ids,
)
from agent_server.mcp_service import McpService
from agent_server.store import AgentStore


def _cfg(tmp_path: Path, monkeypatch) -> Path:
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("agent.config.CONFIG_DIR", cfg_dir)
    monkeypatch.setattr("agent.config.CONFIG_FILE", cfg_dir / "config.json")
    monkeypatch.setattr("agent_server.mcp_json_config.CONFIG_DIR", cfg_dir)
    Config({}).save()
    return cfg_dir


def test_seed_catalog_defaults_creates_disabled_rows(tmp_path: Path, monkeypatch):
    _cfg(tmp_path, monkeypatch)
    store = AgentStore(tmp_path / "agent.db")

    created = seed_catalog_defaults(store)
    assert created == len(MCP_CATALOG)

    servers = store.list_mcp_servers()
    assert len(servers) == len(MCP_CATALOG)
    assert all(s.catalog_id for s in servers)
    assert all(not s.enabled for s in servers)

    # Idempotent
    assert seed_catalog_defaults(store) == 0


def test_export_includes_catalog_meta_without_secrets(tmp_path: Path, monkeypatch):
    _cfg(tmp_path, monkeypatch)
    store = AgentStore(tmp_path / "agent.db")
    seed_catalog_defaults(store)
    store.create_mcp_server(
        name="local-tool",
        transport="stdio",
        command="echo",
        args=["hi"],
        url=None,
        enabled=True,
    )

    doc = export_mcp_json(store)
    servers = doc["mcpServers"]
    assert "local-tool" in servers
    assert servers["local-tool"]["command"] == "echo"

    catalog_keys = [
        key for key, entry in servers.items() if entry.get("_sandwalkCatalogId")
    ]
    assert len(catalog_keys) == len(MCP_CATALOG)
    for key in catalog_keys:
        assert "headers" not in servers[key]


def test_remove_catalog_sticky_and_suggested(tmp_path: Path, monkeypatch):
    _cfg(tmp_path, monkeypatch)
    store = AgentStore(tmp_path / "agent.db")
    get_or_export_mcp_json(store)

    first = next(s for s in store.list_mcp_servers() if s.catalog_id)
    catalog_id = first.catalog_id
    assert catalog_id

    mark_catalog_removed(catalog_id)
    store.delete_mcp_server(first.id)

    # Seed must not recreate removed templates.
    assert seed_catalog_defaults(store) == 0
    assert catalog_id in get_removed_catalog_ids()
    assert catalog_id in suggested_catalog_ids(store)
    assert not any(s.catalog_id == catalog_id for s in store.list_mcp_servers())


def test_install_catalog_clears_removed(tmp_path: Path, monkeypatch):
    _cfg(tmp_path, monkeypatch)
    store = AgentStore(tmp_path / "agent.db")
    get_or_export_mcp_json(store)

    catalog_id = MCP_CATALOG[0].id
    existing = next(s for s in store.list_mcp_servers() if s.catalog_id == catalog_id)
    mark_catalog_removed(catalog_id)
    store.delete_mcp_server(existing.id)

    server = install_catalog_server(store, catalog_id)
    assert server.catalog_id == catalog_id
    assert catalog_id not in get_removed_catalog_ids()
    assert catalog_id not in suggested_catalog_ids(store)


def test_apply_mcp_json_deletes_missing_catalog(tmp_path: Path, monkeypatch):
    _cfg(tmp_path, monkeypatch)
    store = AgentStore(tmp_path / "agent.db")
    get_or_export_mcp_json(store)

    doc = export_mcp_json(store)
    # Drop one catalog entry from the file.
    drop_id = MCP_CATALOG[0].id
    servers = {
        key: value
        for key, value in doc["mcpServers"].items()
        if value.get("_sandwalkCatalogId") != drop_id
    }
    apply_mcp_json(store, {"mcpServers": servers})

    assert drop_id in get_removed_catalog_ids()
    assert not any(s.catalog_id == drop_id for s in store.list_mcp_servers())


def test_catalog_statuses_after_seed(tmp_path: Path, monkeypatch):
    _cfg(tmp_path, monkeypatch)
    store = AgentStore(tmp_path / "agent.db")
    seed_catalog_defaults(store)

    svc = McpService(store)
    statuses = svc.catalog_statuses()
    by_id = {item["id"]: item for item in statuses}
    for entry in MCP_CATALOG:
        assert by_id[entry.id]["server_id"] is not None
