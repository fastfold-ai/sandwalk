"""node/npx/git CLI presence and installed-skills inventory checks."""

from __future__ import annotations

from pathlib import Path

from agent.doctor.checks_runtime import _tool_version
from agent.doctor.models import DoctorCheck


def _check_cli_tooling() -> list[DoctorCheck]:
    checks: list[DoctorCheck] = []

    node_version = _tool_version("node", "--version")
    if node_version:
        checks.append(
            DoctorCheck(
                name="node",
                status="ok",
                detail=node_version,
                category="tooling",
            )
        )
    else:
        checks.append(
            DoctorCheck(
                name="node",
                status="warn",
                detail="node not found on PATH",
                category="tooling",
                fix="Install Node.js to enable npx-based skill installs",
            )
        )

    npx_version = _tool_version("npx", "--version")
    if npx_version:
        checks.append(
            DoctorCheck(
                name="npx",
                status="ok",
                detail=f"npx {npx_version}",
                category="tooling",
            )
        )
    else:
        checks.append(
            DoctorCheck(
                name="npx",
                status="warn",
                detail="npx not found; skill installs fall back to git/archive",
                category="tooling",
                fix="Install Node.js (includes npx) for Skills.sh-compatible installs",
            )
        )

    git_version = _tool_version("git", "--version")
    if git_version:
        checks.append(
            DoctorCheck(
                name="git",
                status="ok",
                detail=git_version,
                category="tooling",
            )
        )
    else:
        checks.append(
            DoctorCheck(
                name="git",
                status="error",
                detail="git not found on PATH",
                category="tooling",
                fix="Install git to clone skill repositories",
            )
        )

    return checks


def _check_skills_loaded() -> DoctorCheck:
    try:
        from agent.skills import list_skills
    except Exception as exc:  # noqa: BLE001
        return DoctorCheck(
            name="skills_loaded",
            status="warn",
            detail=f"Could not inspect skills: {exc}",
            category="skills",
        )

    skills = list_skills()
    if not skills:
        return DoctorCheck(
            name="skills_loaded",
            status="warn",
            detail="0 discovered",
            category="skills",
            fix="sandwalk skills add fastfold-ai/skills",
        )

    enabled = sum(1 for skill in skills if skill.enabled)
    disabled = len(skills) - enabled
    missing_md = sum(
        1
        for skill in skills
        if skill.path is None or not Path(skill.path).exists()
    )
    detail = f"{len(skills)} total · {enabled} enabled · {disabled} disabled"
    if missing_md:
        return DoctorCheck(
            name="skills_loaded",
            status="warn",
            detail=f"{detail} · {missing_md} missing SKILL.md",
            category="skills",
            fix="Remove broken skills or reinstall from source",
        )
    return DoctorCheck(
        name="skills_loaded",
        status="ok",
        detail=detail,
        category="skills",
    )
