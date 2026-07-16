"""Progressive-disclosure skills catalog text injected into the system prompt."""

from __future__ import annotations

from agent.deepagents_runtime.skills_sources import resolve_skill_source_dirs


def build_skills_index_text(
    allowed_skill_names: list[str] | None = None,
) -> tuple[str, int]:
    """Build the progressive-disclosure skills catalog text Deep Agents injects.

    Mirrors ``SkillsMiddleware`` formatting (name, description, path hint) so
    Prompts estimates match first-turn input context.
    """
    from deepagents.middleware.skills import SKILLS_SYSTEM_PROMPT

    from agent.skills import list_skills, skill_info

    if allowed_skill_names is not None:
        skills = []
        for name in allowed_skill_names or []:
            info = skill_info(str(name).strip())
            if info is not None:
                skills.append(info)
    else:
        skills = list(list_skills(enabled_only=True))

    if not skills:
        body = "(No skills available yet.)"
    else:
        lines: list[str] = []
        for skill in skills:
            desc = str(getattr(skill, "description", "") or "").strip()
            path = getattr(skill, "directory", None)
            path_s = f"{path}/SKILL.md" if path else "SKILL.md"
            lines.append(f"- **{skill.name}**: {desc}")
            lines.append(f"  -> Read `{path_s}` for full instructions")
        body = "\n".join(lines)

    sources = resolve_skill_source_dirs(allowed_skill_names)
    locations = "\n".join(f"**Skills**: `{src}`" for src in sources) or "**Skills**: (none)"
    text = SKILLS_SYSTEM_PROMPT.format(
        skills_locations=locations,
        skills_load_warnings="",
        skills_list=body,
    )
    return text, len(skills)
