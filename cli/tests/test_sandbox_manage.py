"""Tests for CLI sandbox backend selection helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from agent.sandbox_manage import (
    get_sandbox_backend,
    handle_sandbox_argv,
    normalize_sandbox_backend,
    sandbox_toolbar_label,
    set_sandbox_backend,
    toggle_sandbox_backend,
)


def test_normalize_aliases():
    assert normalize_sandbox_backend("off") == "builtin"
    assert normalize_sandbox_backend("on") == "modal"
    assert normalize_sandbox_backend("Built-in") == "builtin"
    with pytest.raises(ValueError):
        normalize_sandbox_backend("cloud")


def test_get_defaults_to_builtin_when_unset():
    cfg = MagicMock()
    cfg.get.return_value = ""
    assert get_sandbox_backend(cfg) == "builtin"
    cfg.get.return_value = None
    assert get_sandbox_backend(cfg) == "builtin"


def test_get_and_set_builtin(tmp_path, monkeypatch):
    cfg = MagicMock()
    cfg.get.return_value = "builtin"
    assert get_sandbox_backend(cfg) == "builtin"
    assert sandbox_toolbar_label("builtin") == "Local Sandbox"
    assert sandbox_toolbar_label("modal") == "Modal Sandbox"

    saved = {}

    def _set(key, value):
        saved[key] = value

    cfg.set.side_effect = _set
    cfg.save = MagicMock()
    assert set_sandbox_backend("builtin", cfg) == "builtin"
    assert saved["agent.cli_sandbox"] == "builtin"
    cfg.save.assert_called_once()


def test_set_modal_requires_tokens():
    cfg = MagicMock()
    with patch(
        "agent.sandbox_probe.modal_tokens_present",
        return_value=(False, "missing tokens"),
    ):
        with pytest.raises(RuntimeError, match="missing tokens"):
            set_sandbox_backend("modal", cfg)


def test_toggle_builtin_to_modal():
    cfg = MagicMock()
    cfg.get.return_value = "builtin"
    cfg.set = MagicMock()
    cfg.save = MagicMock()
    with patch(
        "agent.sandbox_probe.modal_tokens_present",
        return_value=(True, ""),
    ):
        assert toggle_sandbox_backend(cfg) == "modal"
    cfg.set.assert_called_with("agent.cli_sandbox", "modal")


def test_cli_ignores_global_sandbox_backend():
    """Web dashboard modal default must not force CLI onto Modal."""
    cfg = MagicMock()

    def _get(key, default=None):
        if key == "sandbox.backend":
            return "modal"
        if key == "agent.cli_sandbox":
            return ""
        return default

    cfg.get.side_effect = _get
    assert get_sandbox_backend(cfg) == "builtin"


def test_handle_sandbox_argv_status(capsys):
    console = Console(force_terminal=True, width=80)
    cfg = MagicMock()
    cfg.get.return_value = "builtin"
    handle_sandbox_argv(["status"], console, config=cfg)
    out = capsys.readouterr().out
    assert "Local Sandbox" in out
    assert "builtin" in out
