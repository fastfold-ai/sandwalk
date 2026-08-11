"""Cheap, deterministic sandwalk smoke checks (real process, isolated HOME)."""

from __future__ import annotations

import json

import pytest

from integration_cli.harness import assert_ok, combined_output, run_sandwalk

pytestmark = pytest.mark.cli_functional


def test_version_prints_sandwalk(cli_home, cli_cwd):
    result = run_sandwalk("--version", home=cli_home, cwd=cli_cwd)
    assert_ok(result, label="sandwalk --version")
    out = combined_output(result).lower()
    assert "sandwalk" in out
    assert "v" in out


def test_tool_list_exits_zero(cli_home, cli_cwd):
    result = run_sandwalk("tool", "list", home=cli_home, cwd=cli_cwd, timeout=90)
    assert_ok(result, label="sandwalk tool list")
    out = combined_output(result)
    # Registry table always includes a known core category/tool prefix.
    assert "target." in out or "Tool" in out or "tool" in out.lower()


def test_config_roundtrip_and_validate(cli_home, cli_cwd):
    set_result = run_sandwalk(
        "config",
        "set",
        "agent.cli_specialist",
        "",
        home=cli_home,
        cwd=cli_cwd,
    )
    assert_ok(set_result, label="config set")

    get_result = run_sandwalk(
        "config",
        "get",
        "agent.cli_specialist",
        home=cli_home,
        cwd=cli_cwd,
    )
    assert_ok(get_result, label="config get")
    assert "agent.cli_specialist" in combined_output(get_result)

    validate = run_sandwalk("config", "validate", home=cli_home, cwd=cli_cwd)
    assert_ok(validate, label="config validate")
    assert "Unknown config key" not in combined_output(validate)

    cfg_path = cli_home / ".sandwalk" / "config.json"
    assert cfg_path.is_file()
    data = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert "agent.cli_specialist" in data
