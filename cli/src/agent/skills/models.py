"""SkillInfo data model, SKILL.md frontmatter parsing, and display helpers."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from agent import skills as _skills

logger = logging.getLogger("skills")

_SKILL_FRONTMATTER_READ_MAX_CHARS = 64_000


# ─── Data model ─────────────────────────────────────────────────────────────
USER_CREATED_CATEGORY = "Created by Me"


@dataclass
class SkillInfo:
    """A discovered skill."""

    name: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    path: Path | None = None  # path to SKILL.md
    source: str = ""  # tier: global | project | bundled | npx
    author: str = ""  # org/owner derived from the install source
    category: str = ""  # optional frontmatter category / origin
    updated_at: str = ""  # ISO timestamp the skill was installed/updated
    version: str | None = None  # release tag (e.g. "v1.2.0") when known
    commit: str | None = None  # installed git SHA when known
    update_available: bool = False
    latest_version: str | None = None  # newer release tag or short SHA
    update_channel: str | None = None  # "release" | "commit"
    icon: str = ""  # optional icon path/URL from SKILL.md frontmatter
    enabled: bool = True

    @property
    def directory(self) -> Path | None:
        return self.path.parent if self.path else None


def is_user_created_skill(info: SkillInfo) -> bool:
    """True for agent/user-authored skills (not catalog/GitHub installs)."""
    category = (getattr(info, "category", "") or "").strip().lower()
    if category in {"custom", "created by me", "user"}:
        return True
    source = str(getattr(info, "source", "") or "").strip()
    source_l = source.lower()
    if source_l == "custom" or source_l.startswith("custom:"):
        return True
    if source.startswith(("/", "~")):
        return True
    if "skill-drafts" in source_l or "/workspaces/" in source_l:
        return True
    return False


def local_skill_author_name() -> str:
    """Display name for the local Sandwalk user (same as /v1/health userName)."""
    try:
        from agent_server.routes.health import local_user_name

        name = (local_user_name() or "").strip()
        if name:
            return name
    except Exception:  # noqa: BLE001
        pass
    try:
        import getpass
        import os

        return getpass.getuser().replace(".", " ").replace("_", " ").title() or os.environ.get(
            "USER", "Me"
        )
    except Exception:  # noqa: BLE001
        return "Me"


# ─── SKILL.md parsing ─────────────────────────────────────────────────────
def parse_skill_md(skill_md: Path) -> SkillInfo:
    """Parse name/description/tags from a SKILL.md frontmatter block.

    Uses a lightweight line parser (no YAML dependency) consistent with the
    rest of the codebase. Falls back to the directory name for ``name``.
    """
    name = skill_md.parent.name
    description = ""
    tags: list[str] = []
    icon = ""
    author = ""
    category = ""

    try:
        # Frontmatter lives at the top; avoid loading large SKILL.md bodies just
        # to extract name/description/tags.
        with skill_md.open("r", encoding="utf-8", errors="ignore") as f:
            content = f.read(_SKILL_FRONTMATTER_READ_MAX_CHARS)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Could not read %s: %s", skill_md, exc)
        return SkillInfo(name=name, path=skill_md)

    # Restrict parsing to the frontmatter block when present.
    block = content
    if content.lstrip().startswith("---"):
        stripped = content.lstrip()
        end = stripped.find("\n---", 3)
        if end != -1:
            block = stripped[3:end]

    for line in block.splitlines():
        line = line.strip()
        if line.startswith("name:"):
            value = line.split(":", 1)[1].strip().strip('"').strip("'")
            if value:
                name = value
        elif line.startswith("description:"):
            description = line.split(":", 1)[1].strip().strip('"').strip("'")
        elif line.startswith("tags:"):
            raw = line.split(":", 1)[1].strip().strip("[]")
            tags = [t.strip().strip('"').strip("'") for t in raw.split(",") if t.strip()]
        elif line.startswith("icon:"):
            icon = line.split(":", 1)[1].strip().strip('"').strip("'")
        elif line.startswith("author:"):
            author = line.split(":", 1)[1].strip().strip('"').strip("'")
        elif line.startswith("category:") or line.startswith("origin:"):
            category = line.split(":", 1)[1].strip().strip('"').strip("'")

    if category.lower() in {"custom", "user"}:
        category = USER_CREATED_CATEGORY
    if not author and category == USER_CREATED_CATEGORY:
        author = local_skill_author_name()

    return SkillInfo(
        name=name,
        description=description,
        tags=tags,
        path=skill_md,
        icon=icon,
        author=author,
        category=category,
    )


# ─── Display helpers ───────────────────────────────────────────────────────
def _derive_author(source: str) -> str:
    """Derive an author/org label from an install source string.

    ``fastfold-ai/skills@skills/fold`` -> ``fastfold-ai``;
    ``https://github.com/owner/repo/...`` -> ``owner``; local paths -> ``local``.
    """
    s = (source or "").strip()
    if not s:
        return ""
    if s.startswith(("http://", "https://", "git@")):
        m = re.search(r"github\.com[:/](?P<owner>[\w.-]+)/", s)
        return m.group("owner") if m else ""
    if s.startswith((".", "/", "~")):
        return "local"
    # owner/repo or owner/repo@subpath shorthand
    if "/" in s:
        return s.split("/", 1)[0]
    return ""


def _source_from_lock_meta(meta: dict) -> str:
    source = str(meta.get("source") or "").strip()
    if not source:
        return ""
    if "@" in source:
        return source
    source_type = str(meta.get("sourceType") or "").strip().lower()
    skill_path = str(meta.get("skillPath") or "").strip().replace("\\", "/")
    if source_type != "github" or not skill_path:
        return source
    if skill_path.lower().endswith("/skill.md"):
        parent = skill_path[: -len("/SKILL.md")]
    elif skill_path.lower() == "skill.md":
        parent = ""
    else:
        parent = str(Path(skill_path).parent).replace("\\", "/")
    parent = parent.strip("/")
    return f"{source}@{parent}" if parent else source


def _read_skills_lock(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.debug("Could not read %s: %s", path, exc)
        return {}
    skills = data.get("skills")
    if not isinstance(skills, dict):
        return {}
    result: dict[str, dict] = {}
    for key, value in skills.items():
        if isinstance(key, str) and isinstance(value, dict):
            result[key] = value
    return result


def _npx_lock_sources() -> dict[str, str]:
    """Map skill keys/names to install source from global skills-lock.json."""
    lock_skills = _read_skills_lock(_skills.CONFIG_DIR / "skills-lock.json")
    out: dict[str, str] = {}
    for key, meta in lock_skills.items():
        source = _source_from_lock_meta(meta)
        if source:
            out[key] = source
    return out


def display_author(info: SkillInfo) -> str:
    """Author column value, with clean fallbacks for tiers without a source."""
    if is_user_created_skill(info):
        author = (getattr(info, "author", "") or "").strip()
        if author and author.lower() not in {"custom", "user"}:
            return author
        return local_skill_author_name()
    author = getattr(info, "author", "") or ""
    if author and author.lower() not in {"custom", "user"}:
        return author
    source = str(getattr(info, "source", "") or "")
    if source == "bundled":
        return "fastfold-ai"
    return "-"


def display_updated(info: SkillInfo) -> str:
    """Updated column value (date only), or ``-`` when unknown."""
    updated = getattr(info, "updated_at", "") or ""
    if not updated:
        return "-"
    return updated[:10]  # YYYY-MM-DD from an ISO timestamp


def display_version(info: SkillInfo) -> str:
    """Version column value, or ``Version not available`` when unreleased.

    npx-installed, bundled, and GitHub sources without a release have no tag.
    """
    return getattr(info, "version", None) or "Version not available"
