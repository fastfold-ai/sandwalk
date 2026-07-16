"""Always-on functional cases: local skill install + doctor (no network)."""

from __future__ import annotations

import json

import pytest

from integration_cli.harness import (
    assert_ok,
    combined_output,
    config_set,
    run_sandwalk,
    skill_installed_on_disk,
    write_minimal_skill,
)

pytestmark = pytest.mark.cli_functional


def test_skills_add_local_and_list(cli_home, cli_cwd, tmp_path):
    skill_dir = write_minimal_skill(tmp_path / "skills", name="demo-skill")
    add = run_sandwalk(
        "skills",
        "add",
        str(skill_dir),
        home=cli_home,
        cwd=cli_cwd,
        timeout=60,
    )
    assert_ok(add, label="skills add local")
    assert "Installed" in combined_output(add) or "demo-skill" in combined_output(add)
    assert skill_installed_on_disk(cli_home, "demo-skill")

    listed = run_sandwalk("skills", "list", home=cli_home, cwd=cli_cwd)
    assert_ok(listed, label="skills list")
    assert "demo-skill" in combined_output(listed)


def test_doctor_json_emits_report(cli_home, cli_cwd):
    # Seed a known-valid config key so doctor has something to read.
    config_set(cli_home, cli_cwd, "agent.cli_sandbox", "builtin")
    result = run_sandwalk("doctor", "--json", home=cli_home, cwd=cli_cwd, timeout=90)
    # Doctor exits non-zero when blocking issues exist (e.g. no LLM key) — still
    # must emit a machine-readable report on stdout.
    raw = (result.stdout or "").strip() or combined_output(result)
    payload = json.loads(raw)
    assert isinstance(payload, dict)
    assert "checks" in payload or "summary" in payload
