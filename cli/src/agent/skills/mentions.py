"""Resolve UI/slash skill mentions into prompt context (generic for any skill).

When the user includes ``/skill-name`` or a composer chip token, Deep Agents
progressive disclosure alone is not enough for weaker models — they often treat
``/name`` as a filesystem path. This module:

1. Extracts skill mentions from the user message (skill-agnostic).
2. Builds a short activation hint with ``read_file`` paths.
3. Preloads each matched skill's ``SKILL.md`` body so the agent does not wait
   to discover it.
"""

from __future__ import annotations

import re
from pathlib import Path

# Composer chip tokens survive in some paths; UI normally serializes to `/name`.
_SKILL_TOKEN_RE = re.compile(r"⟦/:([^⟧]+)⟧")
# `/lab-notes` at a boundary — not `/Users/...` or mid-path segments.
_SKILL_SLASH_RE = re.compile(
    r"(?:^|[\s(\[\"'])(/[A-Za-z][\w-]*)(?=[\s.,;:!?)\]\"'`]|$)"
)

# Keep mention preloads bounded so multi-skill messages stay usable.
_MAX_MENTIONED_SKILLS = 4
_MAX_SKILL_MD_CHARS = 12_000


def extract_skill_mentions(text: str) -> list[str]:
    """Return unique skill names mentioned via chip tokens or slash mentions."""
    raw = str(text or "")
    hits: list[tuple[int, str]] = []

    for match in _SKILL_TOKEN_RE.finditer(raw):
        name = str(match.group(1) or "").strip().lstrip("/")
        if name:
            hits.append((match.start(), name))

    for match in _SKILL_SLASH_RE.finditer(raw):
        raw_token = match.group(1) or ""
        name = str(raw_token).strip().lstrip("/")
        if not name:
            continue
        # Align start with the `/name` span (regex may include a leading delimiter).
        start = match.start() + match.group(0).index(raw_token)
        hits.append((start, name))

    hits.sort(key=lambda item: item[0])
    names: list[str] = []
    seen: set[str] = set()
    for _, name in hits:
        key = name.lower().replace("_", "-")
        if key in seen:
            continue
        seen.add(key)
        names.append(name)
    return names


def _read_skill_md(path: Path | None, *, max_chars: int) -> str:
    if path is None or not path.is_file():
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    body = text.strip()
    if len(body) <= max_chars:
        return body
    return body[: max_chars].rstrip() + "\n\n…(truncated)"


def _read_file_path_for_skill(
    info,
    *,
    sandbox_backend: str | None,
) -> str:
    """Path the agent should pass to ``read_file`` for this skill."""
    modal = str(sandbox_backend or "").strip().lower() == "modal"
    if modal:
        return f"/skills/{info.name}/SKILL.md"
    if getattr(info, "path", None) is not None:
        return str(Path(info.path).expanduser().resolve())
    directory = getattr(info, "directory", None)
    if directory is not None:
        return str(Path(directory).expanduser().resolve() / "SKILL.md")
    return f"{info.name}/SKILL.md"


def _host_skill_dir(info) -> str | None:
    directory = getattr(info, "directory", None)
    if directory is None:
        return None
    try:
        return str(Path(directory).expanduser().resolve())
    except OSError:
        return str(directory)


def build_skill_mention_context(
    text: str,
    *,
    sandbox_backend: str | None = None,
    allowed_skill_names: list[str] | None = None,
    max_skills: int = _MAX_MENTIONED_SKILLS,
    max_skill_md_chars: int = _MAX_SKILL_MD_CHARS,
) -> str:
    """Build activation hint + preloaded SKILL.md for mentioned skills.

    Only resolves against installed skills (enabled; optional specialist
    allowlist). Unknown slash tokens are listed briefly so the agent can
    ``skills.manage(find/install)`` instead of hunting the filesystem.
    """
    mentions = extract_skill_mentions(text)
    if not mentions:
        return ""

    from agent.skills import skill_info

    allow: set[str] | None = None
    if allowed_skill_names is not None:
        allow = {
            str(name).strip().lower().replace("_", "-")
            for name in allowed_skill_names
            if str(name).strip()
        }

    resolved: list[tuple[str, object]] = []
    unknown: list[str] = []
    for name in mentions:
        if len(resolved) >= max(1, int(max_skills)):
            break
        info = skill_info(name)
        if info is None or not getattr(info, "enabled", True):
            unknown.append(name)
            continue
        identity = str(info.name).strip().lower().replace("_", "-")
        if allow is not None and identity not in allow:
            unknown.append(name)
            continue
        resolved.append((name, info))

    if not resolved and not unknown:
        return ""

    lines: list[str] = [
        "User mentioned skill(s) in this message. Treat `/<name>` as a skill "
        "activation, not a filesystem directory under `/`.",
    ]

    if resolved:
        lines.append("Activated skills (follow these instructions now):")
        for mentioned_as, info in resolved:
            read_path = _read_file_path_for_skill(
                info, sandbox_backend=sandbox_backend
            )
            host_dir = _host_skill_dir(info)
            lines.append(f"- /{info.name} (mentioned as /{mentioned_as})")
            lines.append(f"  read_file path: `{read_path}` (limit=1000)")
            if host_dir:
                lines.append(
                    f"  host skill directory (for `shell_run` scripts): `{host_dir}`"
                )
                lines.append(
                    "  Run bundled scripts with `shell_run` using absolute host "
                    "paths under that directory — do not `ls /skills` or "
                    f"`ls /{info.name}`."
                )

    if unknown:
        missing = ", ".join(f"/{name}" for name in unknown)
        lines.append(
            f"Mentioned but not available as an installed/enabled skill: {missing}. "
            "Use `skills.manage` (find/list/install) — do not search the filesystem "
            "for those names as directories."
        )

    for _, info in resolved:
        body = _read_skill_md(
            getattr(info, "path", None), max_chars=max_skill_md_chars
        )
        if not body:
            continue
        lines.append("")
        lines.append(f"### Preloaded SKILL.md: {info.name}")
        lines.append(body)

    return "\n".join(lines).strip()
