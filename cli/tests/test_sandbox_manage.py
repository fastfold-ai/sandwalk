"""Tests for CLI sandbox backend selection helpers."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from agent.config import Config, DEFAULTS, _validate_config
from agent import config as config_mod
from agent.sandbox_manage import (
    CLI_SANDBOX_CONFIG_KEY,
    get_sandbox_backend,
    handle_sandbox_argv,
    normalize_sandbox_backend,
    sandbox_toolbar_label,
    set_sandbox_backend,
    toggle_sandbox_backend,
)
from agent.specialists_manage.state import CLI_SPECIALIST_CONFIG_KEY


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


def test_cli_preference_keys_are_registered_in_defaults():
    """CLI writers must use keys that Config validation already knows.

    Catches the /sandbox modal false-positive "Unknown config key
    'agent.cli_sandbox'" without needing a live TTY or Modal account.
    """
    for key in (CLI_SANDBOX_CONFIG_KEY, CLI_SPECIALIST_CONFIG_KEY):
        assert key in DEFAULTS, f"{key} missing from DEFAULTS"
        assert not any(
            "Unknown config key" in issue and key in issue
            for issue in _validate_config({key: DEFAULTS[key]})
        )


def test_set_modal_roundtrip_has_no_unknown_key_warning(tmp_path, monkeypatch):
    """Persist agent.cli_sandbox via real Config.save/load; reload must be clean."""
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({}))
    monkeypatch.setattr(config_mod, "CONFIG_FILE", cfg_path)

    cfg = Config.load()
    with patch(
        "agent.sandbox_probe.modal_tokens_present",
        return_value=(True, ""),
    ):
        assert set_sandbox_backend("modal", cfg) == "modal"

    # Simulate next interactive boot (Config.load re-runs validation).
    with patch("agent.config.logger") as mock_logger:
        reloaded = Config.load()
        warning_msgs = [
            " ".join(str(a) for a in call.args)
            for call in mock_logger.warning.call_args_list
        ]
    assert reloaded.get(CLI_SANDBOX_CONFIG_KEY) == "modal"
    assert not any("cli_sandbox" in msg and "Unknown" in msg for msg in warning_msgs)
    assert not any(
        "Unknown config key" in issue and "cli_sandbox" in issue
        for issue in reloaded.validate()
    )


def test_handle_sandbox_argv_modal_uses_real_config(tmp_path, monkeypatch, capsys):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({}))
    monkeypatch.setattr(config_mod, "CONFIG_FILE", cfg_path)
    cfg = Config.load()
    console = Console(force_terminal=True, width=80)
    with patch(
        "agent.sandbox_probe.modal_tokens_present",
        return_value=(True, ""),
    ):
        handle_sandbox_argv(["modal"], console, config=cfg)
    out = capsys.readouterr().out
    assert "Modal Sandbox" in out
    assert Config.load().get(CLI_SANDBOX_CONFIG_KEY) == "modal"
    assert not any(
        "Unknown" in issue and "cli_sandbox" in issue for issue in Config.load().validate()
    )
