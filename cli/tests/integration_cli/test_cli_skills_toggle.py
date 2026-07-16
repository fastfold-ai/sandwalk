"""Skill enable/disable + optional sibling-repo local fold install."""

from __future__ import annotations

import pytest

from integration_cli.harness import (
    assert_ok,
    combined_output,
    run_sandwalk,
    sibling_fold_skill_dir,
    skill_installed_on_disk,
    write_minimal_skill,
)

pytestmark = pytest.mark.cli_functional


def test_skills_disable_enable_roundtrip(cli_home, cli_cwd, tmp_path):
    skill_dir = write_minimal_skill(tmp_path / "skills", name="toggle-skill")
    add = run_sandwalk(
        "skills",
        "add",
        str(skill_dir),
        home=cli_home,
        cwd=cli_cwd,
        timeout=60,
    )
    assert_ok(add, label="skills add toggle-skill")
    assert skill_installed_on_disk(cli_home, "toggle-skill")

    disabled = run_sandwalk(
        "skills",
        "disable",
        "toggle-skill",
        home=cli_home,
        cwd=cli_cwd,
    )
    assert_ok(disabled, label="skills disable")
    listed = run_sandwalk("skills", "list", home=cli_home, cwd=cli_cwd)
    assert_ok(listed, label="skills list after disable")
    list_out = combined_output(listed)
    assert "toggle-skill" in list_out
    # Disabled skills still appear; look for an explicit no / disabled signal.
    assert "no" in list_out.lower() or "disabled" in list_out.lower()

    enabled = run_sandwalk(
        "skills",
        "enable",
        "toggle-skill",
        home=cli_home,
        cwd=cli_cwd,
    )
    assert_ok(enabled, label="skills enable")
    assert skill_installed_on_disk(cli_home, "toggle-skill")


def test_skills_add_sibling_fold_checkout(cli_home, cli_cwd):
    fold_dir = sibling_fold_skill_dir()
    if fold_dir is None:
        pytest.skip("Sibling skills checkout not found at ../skills/skills/fold")

    result = run_sandwalk(
        "skills",
        "add",
        str(fold_dir),
        home=cli_home,
        cwd=cli_cwd,
        timeout=60,
    )
    assert_ok(result, label="skills add sibling fold")
    assert skill_installed_on_disk(cli_home, "fold")
    listed = run_sandwalk("skills", "list", home=cli_home, cwd=cli_cwd)
    assert_ok(listed, label="skills list after sibling fold")
    assert "fold" in combined_output(listed).lower()
