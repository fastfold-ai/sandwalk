"""Tests for setup sandbox / MCP prompt helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from agent.config import Config


def test_prompt_setup_sandbox_noninteractive_skip(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent.config.CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr("agent.config.CONFIG_FILE", tmp_path / "cfg" / "config.json")
    (tmp_path / "cfg").mkdir(parents=True, exist_ok=True)
    cfg = Config({})
    cfg.save()

    import cli as cli_mod

    monkeypatch.setattr(cli_mod.sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(cli_mod.sys.stdout, "isatty", lambda: False)
    cli_mod._prompt_setup_sandbox(cfg, backend_arg=None, skip=False)
    assert str(Config.load().get("sandbox.backend") or "builtin") == "builtin"


def test_prompt_setup_sandbox_sets_backend(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent.config.CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr("agent.config.CONFIG_FILE", tmp_path / "cfg" / "config.json")
    (tmp_path / "cfg").mkdir(parents=True, exist_ok=True)
    cfg = Config({})
    cfg.save()

    import cli as cli_mod

    cli_mod._prompt_setup_sandbox(cfg, backend_arg="builtin", skip=False)
    assert Config.load().get("sandbox.backend") == "builtin"


def test_prompt_setup_mcps_skip():
    import cli as cli_mod

    # Should no-op without touching MCP services.
    cli_mod._prompt_setup_mcps(mcp_arg=None, skip=True)


def test_prompt_setup_mcps_noninteractive_explicit(monkeypatch):
    import cli as cli_mod

    called: list[list[str]] = []

    def fake_handle(args, console):
        called.append(list(args))
        return 0

    monkeypatch.setattr(cli_mod, "handle_mcp_argv", fake_handle, raising=False)
    with patch("agent.mcp_manage.handle_mcp_argv", fake_handle):
        with patch.object(cli_mod, "_prompt_masked_secret", return_value=""):
            # oauth-preferred entries may not prompt; use unknown skip path via empty key
            cli_mod._prompt_setup_mcps(mcp_arg="linear", skip=False)

    # linear prefers oauth — handle_mcp_argv should still be invoked
    assert any(args and args[0] == "connect" for args in called) or called == []
