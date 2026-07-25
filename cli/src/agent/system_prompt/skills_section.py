"""Installed-skills prompt section (SDK catalog vs deepagents progressive disclosure)."""

from __future__ import annotations


def _load_installed_skills(session=None, user_request: str | None = None) -> str:
    """Build installed-skills context with an adaptive size budget.

    Delegates to :mod:`agent.skills`, which merges three tiers
    (global install dir, project-local lock-gated skills, bundled catalog) and
    includes full SKILL.md content only for request-relevant skills.
    """
    from agent.skills import build_skills_prompt

    config = getattr(session, "config", None)

    def _cfg_int(key: str, default: int) -> int:
        if config is None:
            return default
        try:
            return int(config.get(key, default))
        except Exception:  # noqa: BLE001
            return default

    return build_skills_prompt(
        user_request=user_request,
        max_catalog_entries=_cfg_int("agent.skills.max_catalog_entries", 250),
        max_active_skills=_cfg_int("agent.skills.max_active", 6),
        max_active_chars=_cfg_int("agent.skills.max_prompt_chars", 120_000),
        catalog_description_chars=_cfg_int("agent.skills.catalog_description_chars", 140),
        index_snippet_chars=_cfg_int("agent.skills.index_snippet_chars", 8_000),
    )


def build_skills_section(
    session,
    user_request: str | None,
    *,
    include_skills: bool,
    runtime: str,
    sandbox_backend: str | None,
    compact: bool = False,
) -> str:
    """Embed an installed-skills catalog, or deepagents filesystem-skills guidance."""
    if include_skills:
        # Resolved lazily via the package attribute so tests can monkeypatch
        # `agent.system_prompt._load_installed_skills`.
        from agent import system_prompt as _pkg

        skills_context = _pkg._load_installed_skills(session=session, user_request=user_request)
        return ("\n" + skills_context) if skills_context else ""

    if runtime != "deepagents":
        return ""

    if compact:
        return (
            "\n## Skills\n"
            "Skills are listed in the Skills System section below. Read a skill's "
            "``SKILL.md`` with ``read_file`` before following it. Run skill scripts "
            "with ``shell_run`` on the **host** skill path "
            "(``$SANDWALK_SKILLS_DIR/<skill>/scripts/...``).\n"
        )

    modal_on = str(sandbox_backend or "").strip().lower() == "modal"
    skills_exec = (
        "To run a skill's bundled scripts, use the `shell_run` tool "
        "(``python3`` + absolute **host** script path, or "
        "``$SANDWALK_SKILLS_DIR/<skill>/scripts/...``). "
        "Skill scripts run on the host (API keys / env), not inside Modal.\n"
        "Modal `execute` is only for `/workspace` compute (CPU/GPU code). "
        "Do **not** `execute` skill paths like `/skills/.../scripts/*.py` — "
        "those files are not in the Modal sandbox.\n"
        if modal_on
        else "To run a skill's bundled scripts, prefer the `shell_run` tool "
        "(``python3`` + absolute script path, or "
        "``$SANDWALK_SKILLS_DIR/<skill>/scripts/...``).\n"
    )
    return (
        "\n## Skills & Filesystem\n"
        "Installed skills are listed in the Skills System section below. Read a "
        "skill's full SKILL.md with `read_file(path, limit=1000)` before following "
        "it. "
        "When the user message includes `/skill-name` (or a skill chip), that is a "
        "skill activation — not a directory under `/`. Prefer the preloaded "
        "SKILL.md / listed `read_file` path; never `ls /skill-name` or hunt "
        "`/skills` with shell.\n"
        + skills_exec
        + "Filesystem tools (`read_file`, `ls`, `glob`, `grep`) may read skill "
        "directories and the **session workspace**. Do not use them to roam "
        "the whole machine (`/`, `$HOME`, `/tmp`, unrelated repos) looking for "
        "artifacts or API keys — downloads belong in the session workspace; "
        "credentials come from Integrations / host env (see Credentials section).\n"
    )
