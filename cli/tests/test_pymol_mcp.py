"""PyMOL MCP catalog + managed launcher helpers."""

from __future__ import annotations

from pathlib import Path

from agent.config import Config
from agent.mcp_catalog import get_catalog_entry, resolve_catalog_command
from agent.mcps.pymol_mcp import (
    PLUGIN_VERSION,
    launcher_path,
    launcher_ready,
    token_ready,
    vendor_package_path,
)
from agent_server.mcp_json_config import seed_catalog_defaults
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


def test_pymol_catalog_entry_is_stdio():
    entry = get_catalog_entry("pymol")
    assert entry is not None
    assert entry.transport == "stdio"
    assert entry.auth_mode == "none"
    assert entry.setup_url == "https://sandwalk.sh/pymol/plugin.zip"
    assert entry.featured is True
    assert resolve_catalog_command(entry).endswith("agentic-pymol")
    assert PLUGIN_VERSION == "0.0.1"


def test_vendored_agentic_pymol_package_present():
    package = vendor_package_path()
    assert (package / "pyproject.toml").is_file()
    assert (package / "agentic_pymol" / "server.py").is_file()
    assert (package / "LICENSE").is_file()
    text = (package / "pyproject.toml").read_text(encoding="utf-8")
    assert "mcp[cli]>=1.0.0,<2" in text
    assert "git+https://" not in text
    app = (package / "agentic_pymol" / "app.py").read_text(encoding="utf-8")
    # FastMCP defaults to INFO+Rich→stderr; force WARNING so TUI stays clean.
    assert 'get("PYMOL_MCP_LOG", "WARNING")' in app
    assert 'log_level=_mcp_log_level()' in app or "log_level=_mcp_log_level()" in app
    types = (package / "agentic_pymol" / "types.py").read_text(encoding="utf-8")
    # slots=True breaks FastMCP output schemas (member descriptors as "defaults").
    assert "@dataclass(frozen=True, slots=True)" not in types
    assert "@dataclass(frozen=True)" in types
    client = (package / "agentic_pymol" / "client.py").read_text(encoding="utf-8")
    assert "logger.info" not in client


def test_seed_creates_pymol_stdio_row(tmp_path: Path, monkeypatch):
    _cfg(tmp_path, monkeypatch)
    store = AgentStore(tmp_path / "agent.db")
    seed_catalog_defaults(store)
    pymol = next(s for s in store.list_mcp_servers() if s.catalog_id == "pymol")
    assert pymol.transport == "stdio"
    assert pymol.url is None
    assert pymol.command
    assert "agentic-pymol" in pymol.command
    assert pymol.enabled is False


def test_pymol_credentials_require_launcher(tmp_path: Path, monkeypatch):
    cfg_dir = _cfg(tmp_path, monkeypatch)
    entry = get_catalog_entry("pymol")
    assert entry is not None
    assert not launcher_ready()
    assert not credentials_configured(entry)

    launcher = launcher_path()
    launcher.parent.mkdir(parents=True, exist_ok=True)
    launcher.write_text("#!/bin/sh\n", encoding="utf-8")
    launcher.chmod(0o755)
    assert launcher_ready()
    assert credentials_configured(entry)
    assert not token_ready()
    # silence unused
    assert cfg_dir.exists()
