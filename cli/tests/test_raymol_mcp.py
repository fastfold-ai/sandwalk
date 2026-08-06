"""RayMol MCP catalog + bridge helpers."""

from __future__ import annotations

from pathlib import Path

from agent.config import Config
from agent.mcp_catalog import get_catalog_entry, resolve_catalog_command
from agent.mcps.raymol_mcp import (
    SETUP_URL,
    ensure_launcher,
    handoff_ready,
    launcher_path,
    launcher_ready,
    raymol_doctor_checks,
)
from agent_server.mcp_json_config import (
    get_removed_catalog_ids,
    install_catalog_server,
    mark_catalog_removed,
    seed_catalog_defaults,
    suggested_catalog_ids,
)
from agent_server.mcp_service import credentials_configured
from agent_server.store import AgentStore


def _cfg(tmp_path: Path, monkeypatch) -> Path:
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("agent.config.CONFIG_DIR", cfg_dir)
    monkeypatch.setattr("agent.config.CONFIG_FILE", cfg_dir / "config.json")
    monkeypatch.setattr("agent_server.mcp_json_config.CONFIG_DIR", cfg_dir)
    Config({}).save()
    return cfg_dir


def test_raymol_catalog_entry_is_stdio():
    entry = get_catalog_entry("raymol")
    assert entry is not None
    assert entry.transport == "stdio"
    assert entry.auth_mode == "none"
    assert entry.featured is True
    assert entry.setup_url == SETUP_URL
    assert entry.args == ["--mcp-bridge"]
    command = resolve_catalog_command(entry)
    assert command
    assert "RayMol" in command


def test_seed_creates_raymol_stdio_row(tmp_path: Path, monkeypatch):
    _cfg(tmp_path, monkeypatch)
    store = AgentStore(tmp_path / "agent.db")
    seed_catalog_defaults(store)
    raymol = next(s for s in store.list_mcp_servers() if s.catalog_id == "raymol")
    assert raymol.transport == "stdio"
    assert raymol.url is None
    assert raymol.command
    assert list(raymol.args or []) == ["--mcp-bridge"]
    assert raymol.enabled is False


def test_install_clears_removed_raymol(tmp_path: Path, monkeypatch):
    _cfg(tmp_path, monkeypatch)
    store = AgentStore(tmp_path / "agent.db")
    seed_catalog_defaults(store)
    existing = next(s for s in store.list_mcp_servers() if s.catalog_id == "raymol")
    mark_catalog_removed("raymol")
    store.delete_mcp_server(existing.id)
    assert "raymol" in suggested_catalog_ids(store)

    server = install_catalog_server(store, "raymol")
    assert server.catalog_id == "raymol"
    assert "raymol" not in get_removed_catalog_ids()
    assert "raymol" not in suggested_catalog_ids(store)


def test_raymol_credentials_require_binary(tmp_path: Path, monkeypatch):
    _cfg(tmp_path, monkeypatch)
    entry = get_catalog_entry("raymol")
    assert entry is not None

    monkeypatch.setattr(
        "agent.mcps.raymol_mcp.paths.find_raymol_binary", lambda: None
    )
    monkeypatch.setattr(
        "agent.mcps.raymol_mcp.setup.find_raymol_binary", lambda: None
    )
    assert not launcher_ready()
    assert not credentials_configured(entry)
    ok, message = ensure_launcher()
    assert ok is False
    assert "raymol.io" in message.lower() or "not found" in message.lower()

    fake = tmp_path / "RayMol"
    fake.write_text("#!/bin/sh\n", encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.setattr(
        "agent.mcps.raymol_mcp.paths.find_raymol_binary", lambda: fake
    )
    monkeypatch.setattr(
        "agent.mcps.raymol_mcp.setup.find_raymol_binary", lambda: fake
    )
    assert launcher_ready()
    assert credentials_configured(entry)
    ok, message = ensure_launcher()
    assert ok is True
    assert str(fake) in message
    assert "--mcp-bridge" in message


def test_raymol_doctor_warns_without_handoff(tmp_path: Path, monkeypatch):
    _cfg(tmp_path, monkeypatch)
    fake = tmp_path / "RayMol"
    fake.write_text("#!/bin/sh\n", encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.setattr(
        "agent.mcps.raymol_mcp.paths.find_raymol_binary", lambda: fake
    )
    monkeypatch.setattr(
        "agent.mcps.raymol_mcp.setup.find_raymol_binary", lambda: fake
    )
    handoff = tmp_path / "mcp.json"
    monkeypatch.setattr("agent.mcps.raymol_mcp.paths.HANDOFF_PATH", handoff)
    monkeypatch.setattr("agent.mcps.raymol_mcp.setup.HANDOFF_PATH", handoff)

    assert not handoff_ready()
    rows = {row["name"]: row for row in raymol_doctor_checks()}
    assert rows["raymol_app"]["status"] == "ok"
    assert rows["raymol_mcp_enabled"]["status"] == "warn"

    handoff.write_text('{"port": 51737, "token": "t"}\n', encoding="utf-8")
    assert handoff_ready()
    rows = {row["name"]: row for row in raymol_doctor_checks()}
    assert rows["raymol_mcp_enabled"]["status"] == "ok"


def test_launcher_path_fallback_default():
    path = launcher_path()
    assert path.name == "RayMol" or "RayMol" in str(path)
