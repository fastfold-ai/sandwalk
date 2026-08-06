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

    featured = [e for e in MCP_CATALOG if e.featured]
    created = seed_catalog_defaults(store)
    assert created == len(featured)

    servers = store.list_mcp_servers()
    assert len(servers) == len(featured)
    assert all(s.catalog_id for s in servers)
    assert all(not s.enabled for s in servers)
    assert "linear" not in {s.catalog_id for s in servers}

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

    featured = [e for e in MCP_CATALOG if e.featured]
    catalog_keys = [
        key for key, entry in servers.items() if entry.get("_sandwalkCatalogId")
    ]
    assert len(catalog_keys) == len(featured)
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

    catalog_id = next(e.id for e in MCP_CATALOG if e.featured)
    existing = next(s for s in store.list_mcp_servers() if s.catalog_id == catalog_id)
    mark_catalog_removed(catalog_id)
    store.delete_mcp_server(existing.id)

    server = install_catalog_server(store, catalog_id)
    assert server.catalog_id == catalog_id
    assert catalog_id not in get_removed_catalog_ids()
    assert catalog_id not in suggested_catalog_ids(store)


def test_reset_featured_defaults_reinstalls_missing(tmp_path: Path, monkeypatch):
    _cfg(tmp_path, monkeypatch)
    store = AgentStore(tmp_path / "agent.db")
    get_or_export_mcp_json(store)

    # Avoid PyMOL launcher side effects — pick a remote featured template.
    entry = next(
        e for e in MCP_CATALOG if e.featured and e.transport != "stdio"
    )
    existing = next(s for s in store.list_mcp_servers() if s.catalog_id == entry.id)
    mark_catalog_removed(entry.id)
    store.delete_mcp_server(existing.id)
    assert entry.id in suggested_catalog_ids(store)

    # Custom (user-added) server must survive reset.
    custom = store.create_mcp_server(
        name="My Custom MCP",
        transport="streamable_http",
        command=None,
        args=[],
        url="https://example.invalid/custom-mcp",
        enabled=True,
        description="user custom",
    )

    svc = McpService(store)
    result = svc.reset_featured_defaults()
    assert entry.id in result["installed"]
    assert result["errors"] == []
    assert entry.id not in suggested_catalog_ids(store)
    assert entry.id not in get_removed_catalog_ids()

    by_id = {s.id: s for s in store.list_mcp_servers()}
    assert custom.id in by_id
    assert by_id[custom.id].name == "My Custom MCP"
    assert getattr(by_id[custom.id], "catalog_id", None) in (None, "")

    # Already at defaults — nothing left to install; custom still untouched.
    again = svc.reset_featured_defaults()
    assert again["installed"] == []
    assert again["errors"] == []
    assert custom.id in {s.id for s in store.list_mcp_servers()}


def test_apply_mcp_json_deletes_missing_catalog(tmp_path: Path, monkeypatch):
    _cfg(tmp_path, monkeypatch)
    store = AgentStore(tmp_path / "agent.db")
    get_or_export_mcp_json(store)

    doc = export_mcp_json(store)
    # Drop one catalog entry from the file.
    drop_id = next(e.id for e in MCP_CATALOG if e.featured)
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
        if entry.featured:
            assert by_id[entry.id]["server_id"] is not None
        else:
            assert by_id[entry.id]["server_id"] is None

def test_prune_obsolete_catalog_servers(tmp_path: Path, monkeypatch):
    from agent_server.mcp_json_config import prune_obsolete_catalog_servers

    _cfg(tmp_path, monkeypatch)
    store = AgentStore(tmp_path / "agent.db")
    seed_catalog_defaults(store)
    orphan = store.create_mcp_server(
        name="Gone Template",
        transport="streamable_http",
        command=None,
        args=[],
        url="https://example.invalid/mcp",
        enabled=False,
        catalog_id="betterstack",
        description="removed from catalog",
    )
    custom = store.create_mcp_server(
        name="Custom Keep",
        transport="stdio",
        command="echo",
        args=["hi"],
        url=None,
        enabled=True,
    )

    deleted = prune_obsolete_catalog_servers(store)
    assert deleted == 1
    ids = {s.id for s in store.list_mcp_servers()}
    assert orphan.id not in ids
    assert custom.id in ids
    assert prune_obsolete_catalog_servers(store) == 0
