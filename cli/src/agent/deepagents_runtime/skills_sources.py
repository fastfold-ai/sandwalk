"""Skill source directory resolution for deepagents ``skills=`` (progressive disclosure)."""

from __future__ import annotations

from pathlib import Path


def skill_source_dirs() -> list[str]:
    """Return existing skill source directories for deepagents ``skills=``.

    Ordered low -> high priority (later sources win on name collision), mirroring
    :func:`agent.skills.iter_skills`: bundled -> npx -> global.

    Prefer :func:`resolve_skill_source_dirs` at runtime so Dashboard enable/disable
    and specialist allowlists are respected — this helper returns raw roots and
    will expose every on-disk skill to SkillsMiddleware.
    """
    from agent.skills import BUNDLED_SKILLS_DIR, GLOBAL_SKILLS_DIR, NPX_SKILLS_DIR

    sources: list[str] = []
    for path in (BUNDLED_SKILLS_DIR, NPX_SKILLS_DIR, GLOBAL_SKILLS_DIR):
        try:
            if path and Path(path).exists():
                sources.append(str(path))
        except Exception:  # noqa: BLE001
            continue
    return sources


def skill_source_dirs_for_names(skill_names: list[str]) -> list[str]:
    """Stage only the named skills into a temp directory for deepagents ``skills=``.

    When a specialist scopes a run, deepagents still expects parent directories that
    contain skill folders — so we symlink the selected skill directories into a
    staging root and return that root alone.
    """
    import hashlib
    import shutil
    import tempfile

    from agent.skills import skill_info

    names = [str(name).strip() for name in skill_names if str(name).strip()]
    if not names:
        return []

    resolved: list[tuple[str, Path]] = []
    for name in names:
        info = skill_info(name)
        if info is None:
            continue
        directory = info.directory
        if directory is None or not directory.is_dir():
            continue
        resolved.append((directory.name, directory.resolve()))

    if not resolved:
        return []

    stamp = hashlib.sha1(
        "|".join(sorted(f"{key}:{path}" for key, path in resolved)).encode()
    ).hexdigest()[:16]
    staging = Path(tempfile.gettempdir()) / "sandwalk-specialist-skills" / stamp
    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)
    for key, directory in resolved:
        link = staging / key
        if link.exists() or link.is_symlink():
            link.unlink()
        try:
            link.symlink_to(directory, target_is_directory=True)
        except OSError:
            shutil.copytree(directory, link)
    return [str(staging)]


def resolve_skill_source_dirs(
    allowed_skill_names: list[str] | None = None,
) -> list[str]:
    """Skill roots for ``create_deep_agent(skills=...)``.

    Deep Agents loads skills with progressive disclosure: name + description at
    startup, full SKILL.md on demand
    (https://docs.langchain.com/oss/python/deepagents/overview#skills).

    - Specialist allowlist (``allowed_skill_names is not None``): stage those
      names only (empty list → no skills).
    - Default (None): stage **enabled** skills from the Skills UI — never the
      raw on-disk roots, which would ignore disable toggles.
    """
    from agent.skills import list_skills

    if allowed_skill_names is not None:
        return skill_source_dirs_for_names(list(allowed_skill_names or []))
    enabled = [s.name for s in list_skills(enabled_only=True)]
    return skill_source_dirs_for_names(enabled)
