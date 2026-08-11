"""Functional regression: sandbox modal must not warn on agent.cli_sandbox."""

from __future__ import annotations

import json

import pytest

from integration_cli.harness import (
    assert_no_unknown_config,
    assert_ok,
    combined_output,
    run_sandwalk,
)

pytestmark = pytest.mark.cli_functional


def _seed_modal_tokens(cli_home, cli_cwd) -> None:
    for key, value in (
        ("compute.modal_token_id", "test-modal-token-id"),
        ("compute.modal_token_secret", "test-modal-token-secret"),
    ):
        result = run_sandwalk("config", "set", key, value, home=cli_home, cwd=cli_cwd)
        assert_ok(result, label=f"config set {key}")


def test_sandbox_modal_persists_without_unknown_key_warning(cli_home, cli_cwd):
    _seed_modal_tokens(cli_home, cli_cwd)

    modal = run_sandwalk("sandbox", "modal", home=cli_home, cwd=cli_cwd)
    assert_ok(modal, label="sandbox modal")
    out = combined_output(modal)
    assert "Modal" in out
    assert_no_unknown_config(modal, "agent.cli_sandbox")

    validate = run_sandwalk("config", "validate", home=cli_home, cwd=cli_cwd)
    assert_ok(validate, label="config validate after sandbox modal")
    assert_no_unknown_config(validate, "agent.cli_sandbox")
    assert "Unknown config key" not in combined_output(validate)

    cfg_path = cli_home / ".sandwalk" / "config.json"
    data = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert data.get("agent.cli_sandbox") == "modal"


def test_sandbox_builtin_flips_back(cli_home, cli_cwd):
    _seed_modal_tokens(cli_home, cli_cwd)
    assert_ok(run_sandwalk("sandbox", "modal", home=cli_home, cwd=cli_cwd))

    builtin = run_sandwalk("sandbox", "builtin", home=cli_home, cwd=cli_cwd)
    assert_ok(builtin, label="sandbox builtin")
    out = combined_output(builtin)
    assert "Local Sandbox" in out or "builtin" in out.lower()
    assert_no_unknown_config(builtin, "agent.cli_sandbox")

    cfg_path = cli_home / ".sandwalk" / "config.json"
    data = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert data.get("agent.cli_sandbox") == "builtin"

    status = run_sandwalk("sandbox", "status", home=cli_home, cwd=cli_cwd)
    assert_ok(status, label="sandbox status")
    assert "Local Sandbox" in combined_output(status)
