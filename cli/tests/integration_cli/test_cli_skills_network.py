"""Network CLI cases: install featured Fastfold skills from GitHub.

Gated by ``RUN_CLI_NETWORK=1`` so default CI stays offline-friendly.
"""

from __future__ import annotations

import os

import pytest

from integration_cli.harness import (
    BOLTZGEN_SKILL_SOURCE,
    BOLTZ_SKILL_SOURCE,
    FOLD_SKILL_SOURCE,
    MD_SKILL_SOURCE,
    assert_ok,
    combined_output,
    run_sandwalk,
    skill_installed_on_disk,
)

_RUN = os.environ.get("RUN_CLI_NETWORK", "").strip() in {"1", "true", "yes"}

pytestmark = [
    pytest.mark.cli_network,
    pytest.mark.skipif(
        not _RUN,
        reason="Set RUN_CLI_NETWORK=1 to install skills from GitHub",
    ),
]


@pytest.mark.parametrize(
    ("source", "expected_name"),
    [
        (FOLD_SKILL_SOURCE, "fold"),
        (BOLTZ_SKILL_SOURCE, "boltz"),
        (MD_SKILL_SOURCE, "md_openmm_calvados"),
        (BOLTZGEN_SKILL_SOURCE, "protein_design_boltzgen"),
    ],
    ids=["fold", "boltz", "md_openmm_calvados", "protein_design_boltzgen"],
)
def test_skills_add_featured_from_github(cli_home, cli_cwd, source, expected_name):
    result = run_sandwalk(
        "skills",
        "add",
        source,
        home=cli_home,
        cwd=cli_cwd,
        timeout=180,
    )
    assert_ok(result, label=f"skills add {source}")
    out = combined_output(result)
    assert expected_name in out.lower() or "Installed" in out
    assert skill_installed_on_disk(cli_home, expected_name), (
        f"expected {cli_home}/.sandwalk/skills/{expected_name}/SKILL.md after install"
    )

    listed = run_sandwalk("skills", "list", home=cli_home, cwd=cli_cwd, timeout=60)
    assert_ok(listed, label="skills list after network install")
    assert expected_name in combined_output(listed)
