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
    missing = tmp_path / "missing-RayMol"
    monkeypatch.setattr(
        "agent.mcps.raymol_mcp.paths.DEFAULT_APP_BINARY", missing
    )
    monkeypatch.setattr(
        "agent.mcps.raymol_mcp.setup.DEFAULT_APP_BINARY", missing
    )
    monkeypatch.setattr(
        "agent.mcps.raymol_mcp.setup.launcher_path", lambda: missing
    )
    monkeypatch.setattr(
        "agent.mcps.raymol_mcp.paths.handoff_ready", lambda: False
    )
    monkeypatch.setattr(
        "agent.mcps.raymol_mcp.setup.handoff_ready", lambda: False
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


def test_find_raymol_binary_accepts_non_executable_name(tmp_path: Path, monkeypatch):
    """Some hosts report os.access(X_OK)=False even for a present app binary."""
    app = tmp_path / "RayMol.app" / "Contents" / "MacOS"
    app.mkdir(parents=True)
    binary = app / "RayMol"
    binary.write_text("#!/bin/sh\n", encoding="utf-8")
    # Intentionally leave without +x — discovery should still accept by name.
    monkeypatch.setattr(
        "agent.mcps.raymol_mcp.paths._candidate_apps",
        lambda: [tmp_path / "RayMol.app"],
    )
    monkeypatch.setattr("agent.mcps.raymol_mcp.paths.shutil.which", lambda _name: None)
    monkeypatch.setattr(
        "agent.mcps.raymol_mcp.paths._config_override", lambda: None
    )
    from agent.mcps.raymol_mcp.paths import find_raymol_binary

    found = find_raymol_binary()
    assert found is not None
    assert found.name == "RayMol"


def test_ensure_launcher_rejects_handoff_without_binary(tmp_path: Path, monkeypatch):
    """A handoff can outlive its app; the stdio bridge still needs the binary."""
    _cfg(tmp_path, monkeypatch)
    handoff = tmp_path / "mcp.json"
    handoff.write_text('{"port": 51737, "token": "t"}\n', encoding="utf-8")
    monkeypatch.setattr(
        "agent.mcps.raymol_mcp.setup.find_raymol_binary", lambda: None
    )
    monkeypatch.setattr(
        "agent.mcps.raymol_mcp.setup.launcher_path",
        lambda: tmp_path / "missing-RayMol",
    )
    monkeypatch.setattr("agent.mcps.raymol_mcp.setup.HANDOFF_PATH", handoff)
    monkeypatch.setattr(
        "agent.mcps.raymol_mcp.setup.handoff_ready", lambda: True
    )
    ok, message = ensure_launcher()
    assert ok is False
    assert "missing" in message.lower()
    assert "raymol" in message.lower()


def test_ensure_launcher_clears_stale_binary_config(tmp_path: Path, monkeypatch):
    """A deleted app must not leave mcp.raymol_binary pointing at a dead path."""
    _cfg(tmp_path, monkeypatch)
    config = Config.load()
    config.set("mcp.raymol_binary", str(tmp_path / "gone" / "RayMol"))
    config.save()

    monkeypatch.setattr(
        "agent.mcps.raymol_mcp.setup.find_raymol_binary", lambda: None
    )
    monkeypatch.setattr(
        "agent.mcps.raymol_mcp.setup.launcher_path",
        lambda: tmp_path / "missing-RayMol",
    )
    monkeypatch.setattr(
        "agent.mcps.raymol_mcp.setup.handoff_ready", lambda: False
    )
    ok, _message = ensure_launcher()
    assert ok is False
    assert not str(Config.load().get("mcp.raymol_binary") or "").strip()


def test_launcher_ready_requires_binary_not_just_handoff(tmp_path: Path, monkeypatch):
    """Install and Enable must agree: handoff alone is not spawnable."""
    from agent.mcps.raymol_mcp.paths import launcher_ready as ready

    monkeypatch.setattr(
        "agent.mcps.raymol_mcp.paths.find_raymol_binary", lambda: None
    )
    monkeypatch.setattr(
        "agent.mcps.raymol_mcp.paths.DEFAULT_APP_BINARY",
        tmp_path / "missing-RayMol",
    )
    handoff = tmp_path / "mcp.json"
    handoff.write_text('{"port": 1, "token": "t"}\n', encoding="utf-8")
    monkeypatch.setattr("agent.mcps.raymol_mcp.paths.HANDOFF_PATH", handoff)
    assert ready() is False


def test_find_raymol_binary_uses_running_process(tmp_path: Path, monkeypatch):
    """RayMol opened from its DMG is only visible via the process table."""
    volume = tmp_path / "Volumes" / "RayMol" / "RayMol.app" / "Contents" / "MacOS"
    volume.mkdir(parents=True)
    binary = volume / "RayMol"
    binary.write_text("#!/bin/sh\n", encoding="utf-8")
    binary.chmod(0o755)

    monkeypatch.setattr(
        "agent.mcps.raymol_mcp.paths._config_override", lambda: None
    )
    monkeypatch.setattr("agent.mcps.raymol_mcp.paths.shutil.which", lambda _n: None)
    monkeypatch.setattr("agent.mcps.raymol_mcp.paths._candidate_apps", lambda: [])
    monkeypatch.setattr(
        "agent.mcps.raymol_mcp.paths.running_binaries", lambda: [binary]
    )
    from agent.mcps.raymol_mcp.paths import find_raymol_binary

    assert find_raymol_binary() == binary


def test_find_raymol_binary_ignores_stale_default(tmp_path: Path, monkeypatch):
    """Never hand callers a path that does not exist — they exec it."""
    monkeypatch.setattr(
        "agent.mcps.raymol_mcp.paths._config_override", lambda: None
    )
    monkeypatch.setattr("agent.mcps.raymol_mcp.paths.shutil.which", lambda _n: None)
    monkeypatch.setattr("agent.mcps.raymol_mcp.paths._candidate_apps", lambda: [])
    monkeypatch.setattr("agent.mcps.raymol_mcp.paths.running_binaries", lambda: [])
    monkeypatch.setattr(
        "agent.mcps.raymol_mcp.paths.DEFAULT_APP_BINARY",
        tmp_path / "nope" / "RayMol",
    )
    from agent.mcps.raymol_mcp.paths import bridge_command, find_raymol_binary

    assert find_raymol_binary() is None
    assert bridge_command() is None


def test_permanent_install_beats_mounted_volume(tmp_path: Path, monkeypatch):
    """A DMG copy disappears on eject, so /Applications must win even while it runs."""

    def _make(root: Path) -> Path:
        macos = root / "RayMol.app" / "Contents" / "MacOS"
        macos.mkdir(parents=True)
        binary = macos / "RayMol"
        binary.write_text("#!/bin/sh\n", encoding="utf-8")
        binary.chmod(0o755)
        return binary

    removable = _make(tmp_path / "Volumes" / "RayMol")
    permanent = _make(tmp_path / "Applications")

    # Simulate /Volumes without touching the real filesystem.
    monkeypatch.setattr(
        "agent.mcps.raymol_mcp.paths.on_removable_volume",
        lambda p: "Volumes" in str(p),
    )
    monkeypatch.setattr(
        "agent.mcps.raymol_mcp.paths._config_override", lambda: removable
    )
    monkeypatch.setattr("agent.mcps.raymol_mcp.paths.shutil.which", lambda _n: None)
    monkeypatch.setattr(
        "agent.mcps.raymol_mcp.paths.running_binaries", lambda: [removable]
    )
    monkeypatch.setattr(
        "agent.mcps.raymol_mcp.paths._candidate_apps",
        lambda: [permanent.parent.parent.parent],
    )
    from agent.mcps.raymol_mcp.paths import find_raymol_binary

    assert find_raymol_binary() == permanent


def test_mounted_volume_used_when_only_option(tmp_path: Path, monkeypatch):
    """Running from the DMG still works — it is just the last resort."""
    macos = tmp_path / "Volumes" / "RayMol" / "RayMol.app" / "Contents" / "MacOS"
    macos.mkdir(parents=True)
    binary = macos / "RayMol"
    binary.write_text("#!/bin/sh\n", encoding="utf-8")
    binary.chmod(0o755)

    monkeypatch.setattr(
        "agent.mcps.raymol_mcp.paths.on_removable_volume",
        lambda p: "Volumes" in str(p),
    )
    monkeypatch.setattr(
        "agent.mcps.raymol_mcp.paths._config_override", lambda: None
    )
    monkeypatch.setattr("agent.mcps.raymol_mcp.paths.shutil.which", lambda _n: None)
    monkeypatch.setattr(
        "agent.mcps.raymol_mcp.paths.running_binaries", lambda: [binary]
    )
    monkeypatch.setattr("agent.mcps.raymol_mcp.paths._candidate_apps", lambda: [])
    monkeypatch.setattr(
        "agent.mcps.raymol_mcp.paths.DEFAULT_APP_BINARY", tmp_path / "nope" / "RayMol"
    )
    from agent.mcps.raymol_mcp.paths import find_raymol_binary

    assert find_raymol_binary() == binary


def test_running_binaries_parses_ps_output(monkeypatch):
    import subprocess as sp

    class _Proc:
        stdout = (
            "/usr/libexec/secinitd\n"
            "/Volumes/RayMol/RayMol.app/Contents/MacOS/RayMol\n"
            "/Applications/Safari.app/Contents/MacOS/Safari\n"
        )

    monkeypatch.setattr(
        "agent.mcps.raymol_mcp.paths.subprocess.run",
        lambda *a, **k: _Proc(),
    )
    _ = sp
    from agent.mcps.raymol_mcp.paths import running_binaries as running

    found = running()
    assert found == [Path("/Volumes/RayMol/RayMol.app/Contents/MacOS/RayMol")]
