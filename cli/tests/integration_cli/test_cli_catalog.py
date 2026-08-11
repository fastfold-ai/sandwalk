"""Catalog / listing commands — no network, no secrets."""

from __future__ import annotations

import pytest

from integration_cli.harness import assert_ok, combined_output, run_sandwalk

pytestmark = pytest.mark.cli_functional


def test_mcp_list_shows_catalog(cli_home, cli_cwd):
    result = run_sandwalk("mcp", "list", home=cli_home, cwd=cli_cwd, timeout=60)
    assert_ok(result, label="mcp list")
    out = combined_output(result).lower()
    assert "mcp" in out or "tamarind" in out or "suggested" in out


def test_mcp_catalog_lists_known_servers(cli_home, cli_cwd):
    result = run_sandwalk("mcp", "catalog", home=cli_home, cwd=cli_cwd, timeout=60)
    assert_ok(result, label="mcp catalog")
    out = combined_output(result).lower()
    assert "tamarind" in out
    assert "neurosnap" in out or "latch" in out or "linear" in out


def test_specialists_list_shows_defaults(cli_home, cli_cwd):
    result = run_sandwalk("specialists", "list", home=cli_home, cwd=cli_cwd, timeout=60)
    assert_ok(result, label="specialists list")
    out = combined_output(result).lower()
    assert "specialist" in out
    assert "structure-prediction" in out or "genomics-analyst" in out
