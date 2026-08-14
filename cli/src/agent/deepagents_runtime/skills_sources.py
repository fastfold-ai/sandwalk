"""Skill source directory resolution for deepagents ``skills=`` (progressive disclosure)."""

from __future__ import annotations

import hashlib
import logging
import shutil
import tempfile
import threading
from pathlib import Path

logger = logging.getLogger("runner")

_STAGING_LOCK = threading.Lock()


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


def _staging_complete(staging: Path, expected: set[str]) -> bool:
    if not staging.is_dir():
        return False
    present = {p.name for p in staging.iterdir() if p.is_dir() or p.is_symlink()}
    return expected <= present


def _link_or_copy(directory: Path, link: Path) -> None:
    """Install ``directory`` at ``link``; tolerate concurrent creators."""
    if link.exists() or link.is_symlink():
        return
    try:
        link.symlink_to(directory, target_is_directory=True)
        return
    except FileExistsError:
        return
    except OSError:
        pass
    if link.exists() or link.is_symlink():
        return
    try:
        shutil.copytree(directory, link)
    except FileExistsError:
        return


def skill_source_dirs_for_names(skill_names: list[str]) -> list[str]:
    """Stage only the named skills into a temp directory for deepagents ``skills=``.

    When a specialist scopes a run, deepagents still expects parent directories that
    contain skill folders — so we symlink the selected skill directories into a
    staging root and return that root alone.

    Staging is keyed by content hash and reused across concurrent callers so
    Context estimates / bench cells / agent runs do not race on rmtree+mkdir.
    """
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

    expected = {key for key, _ in resolved}
    stamp = hashlib.sha1(
        "|".join(sorted(f"{key}:{path}" for key, path in resolved)).encode()
    ).hexdigest()[:16]
    root = Path(tempfile.gettempdir()) / "sandwalk-specialist-skills"
    staging = root / stamp

    with _STAGING_LOCK:
        if _staging_complete(staging, expected):
            return [str(staging)]

        root.mkdir(parents=True, exist_ok=True)
        # Build atomically in a unique dir, then rename into place so concurrent
        # callers never observe a half-deleted shared stamp directory.
        work = Path(tempfile.mkdtemp(prefix=f"{stamp}-", dir=str(root)))
        try:
            for key, directory in resolved:
                _link_or_copy(directory, work / key)
            if staging.exists() and not _staging_complete(staging, expected):
                shutil.rmtree(staging, ignore_errors=True)
            if not staging.exists():
                work.rename(staging)
            else:
                shutil.rmtree(work, ignore_errors=True)
        except Exception:  # noqa: BLE001
            shutil.rmtree(work, ignore_errors=True)
            logger.warning(
                "skill staging failed for stamp=%s; falling back to empty list",
                stamp,
                exc_info=True,
            )
            return []

        if not _staging_complete(staging, expected):
            for key, directory in resolved:
                _link_or_copy(directory, staging / key)

        if not _staging_complete(staging, expected):
            logger.warning("skill staging incomplete for stamp=%s", stamp)
            return []
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
