"""
Skill management for fastfold-agent-cli.

Single source of truth for discovering, loading, installing, and removing
agent skills. A *skill* is a directory containing a ``SKILL.md`` file (plus
optional ``scripts/``, ``references/``, ``assets/``).

Skills are resolved from three tiers (highest priority first):

1. **global**  — ``~/.fastfold-cli/skills/`` (where ``skill add`` installs).
2. **project** — ``<cwd>/.claude/skills/`` gated by ``<cwd>/skills-lock.json``
   (legacy/back-compat; read-only here).
3. **bundled** — ``src/skills/`` shipped inside the package.

Higher tiers override lower tiers on a name collision.

Installation is native (``git clone``), with GitHub archive download when git
is unavailable or clone fails, and an optional fallback to the external
``npx skills`` CLI when Node.js is installed.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from agent.config import CONFIG_DIR

logger = logging.getLogger("skills")

# Serializes manifest read-modify-write so parallel installs don't corrupt it.
_MANIFEST_LOCK = threading.Lock()

# Bounded parallelism for network-bound skill syncs (clones/archives). Override
# with FASTFOLD_SKILLS_SYNC_WORKERS.
_DEFAULT_SYNC_WORKERS = 8

# ─── Locations ────────────────────────────────────────────────────────────
GLOBAL_SKILLS_DIR = CONFIG_DIR / "skills"
BUNDLED_SKILLS_DIR = Path(__file__).parent.parent / "skills"
MANIFEST_FILENAME = ".installed.json"
SKILL_STATE_FILENAME = "skills-state.json"

# Fastfold-controlled directory for `npx skills add` installs. We pin the Skills
# CLI's working directory to NPX_INSTALL_ROOT and target the `claude-code` agent in
# project scope, so files land in a single fastfold-owned location (not the user's
# global ~/.claude/skills). The loader reads NPX_SKILLS_DIR as its own tier.
NPX_INSTALL_ROOT = CONFIG_DIR
NPX_SKILLS_DIR = CONFIG_DIR / ".claude" / "skills"

# Default discovery catalog (GitHub ``owner/repo``); skills live under ``skills/``.
DEFAULT_CATALOG = "fastfold-ai/skills"

# Curated third-party skill collections, grouped by provider. Each ``source`` is a
# GitHub shorthand installable via ``install_skill`` (native git or npx). Installing
# a whole-repo source batch-installs all skills it contains.
SUGGESTED_SKILL_SOURCES = [
    {
        "provider": "K-Dense-AI",
        "source": "K-Dense-AI/scientific-agent-skills",
        "url": "https://github.com/K-Dense-AI/scientific-agent-skills",
        "description": "Scientific agent skills collection",
    },
    {
        "provider": "Anthropic",
        "source": "anthropics/life-sciences",
        "url": "https://github.com/anthropics/life-sciences#skills",
        "description": "Anthropic life-sciences skills",
    },
    {
        "provider": "DeepMind",
        "source": "google-deepmind/science-skills",
        "url": "https://github.com/google-deepmind/science-skills",
        "description": "Google DeepMind science skills",
    },
]

_GITHUB_SHORTHAND_RE = re.compile(r"^(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+?)(?:@(?P<sub>.+))?$")
_CLONE_TIMEOUT_S = 120
_SKILL_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_+.-]*")
_SKILL_FRONTMATTER_READ_MAX_CHARS = 64_000
SKILLS_PROMPT_INDEX_CACHE = CONFIG_DIR / "skills_prompt_index.json"
_SKILLS_PROMPT_INDEX_VERSION = 1
_SKILL_INDEX_SNIPPET_CHARS = 8_000
_SKILL_STOPWORDS = {
    # Pure grammar / filler words that appear in every sentence and carry
    # no signal when matching a user request to an installed skill.
    "a", "an", "and", "as", "at", "be", "by", "for", "from",
    "how", "i", "in", "is", "it", "me", "my", "of", "on", "or",
    "that", "the", "this", "to", "with",
}


# ─── Data model ─────────────────────────────────────────────────────────────
@dataclass
class SkillInfo:
    """A discovered skill."""

    name: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    path: Optional[Path] = None  # path to SKILL.md
    source: str = ""  # tier: global | project | bundled | npx
    author: str = ""  # org/owner derived from the install source
    updated_at: str = ""  # ISO timestamp the skill was installed/updated
    version: Optional[str] = None  # release tag (e.g. "v1.2.0") when known
    icon: str = ""  # optional icon path/URL from SKILL.md frontmatter
    enabled: bool = True

    @property
    def directory(self) -> Optional[Path]:
        return self.path.parent if self.path else None


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

    return SkillInfo(
        name=name,
        description=description,
        tags=tags,
        path=skill_md,
        icon=icon,
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
    lock_skills = _read_skills_lock(CONFIG_DIR / "skills-lock.json")
    out: dict[str, str] = {}
    for key, meta in lock_skills.items():
        source = _source_from_lock_meta(meta)
        if source:
            out[key] = source
    return out


def display_author(info: SkillInfo) -> str:
    """Author column value, with clean fallbacks for tiers without a source."""
    author = getattr(info, "author", "") or ""
    if author:
        return author
    if getattr(info, "source", "") == "bundled":
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


# ─── Discovery / loading ───────────────────────────────────────────────────
def _scan_dir(base: Path, source: str) -> dict[str, SkillInfo]:
    out: dict[str, SkillInfo] = {}
    if not base.exists():
        return out
    manifest = _read_manifest(base)
    skills_meta = manifest.get("skills", {}) if isinstance(manifest, dict) else {}
    npx_sources = _npx_lock_sources() if source == "npx" else {}
    for child in sorted(base.iterdir()):
        skill_md = child / "SKILL.md"
        if child.is_dir() and skill_md.exists():
            info = parse_skill_md(skill_md)
            info.source = source
            meta = skills_meta.get(child.name) or {}
            if isinstance(meta, dict):
                install_source = str(meta.get("source") or "").strip()
                if install_source:
                    # Prefer the real source spec (owner/repo@path or URL) so
                    # UI links and install commands can trace origin correctly.
                    info.source = install_source
                info.author = _derive_author(install_source)
                info.updated_at = str(meta.get("installed_at") or "")
                release = meta.get("release")
                info.version = str(release) if release else None
            if source == "npx" and info.source == "npx":
                lock_source = npx_sources.get(child.name) or npx_sources.get(info.name)
                if lock_source:
                    info.source = lock_source
                    info.author = _derive_author(lock_source)
            # Key by directory name (canonical identifier everywhere else).
            out[child.name] = info
    return out


def _scan_project(project_root: Path) -> dict[str, SkillInfo]:
    """Scan project-local skills gated by skills-lock.json (back-compat)."""
    out: dict[str, SkillInfo] = {}
    lock_file = project_root / "skills-lock.json"
    claude_dir = project_root / ".claude" / "skills"
    if not (lock_file.exists() and claude_dir.exists()):
        return out
    lock_skills = _read_skills_lock(lock_file)
    for name, meta in lock_skills.items():
        skill_md = claude_dir / name / "SKILL.md"
        if skill_md.exists():
            info = parse_skill_md(skill_md)
            info.source = "project"
            install_source = _source_from_lock_meta(meta)
            if install_source:
                info.source = install_source
                info.author = _derive_author(install_source)
            out[name] = info
    return out


def iter_skills(
    project_root: Optional[Path] = None,
    *,
    enabled_only: bool = False,
) -> dict[str, SkillInfo]:
    """Return merged skills keyed by directory name.

    Priority (high → low): global > npx > project (lock-gated) > bundled.
    Entries that only differ by ``_`` vs ``-`` naming (or share the same
    SKILL.md frontmatter name) are collapsed so the UI/API list is unique.
    """
    if project_root is None:
        project_root = Path.cwd()

    merged: dict[str, SkillInfo] = {}
    merged.update(_scan_dir(BUNDLED_SKILLS_DIR, "bundled"))
    merged.update(_scan_project(project_root))
    merged.update(_scan_dir(NPX_SKILLS_DIR, "npx"))
    merged.update(_scan_dir(GLOBAL_SKILLS_DIR, "global"))
    merged = _collapse_skills_by_name(merged)
    disabled = {
        _normalize_skill_lookup(name) for name in _disabled_skill_names() if name
    }
    for key, info in merged.items():
        identity = _normalize_skill_lookup(info.name) or _normalize_skill_lookup(key)
        info.enabled = identity not in disabled
    if enabled_only:
        return {name: info for name, info in merged.items() if info.enabled}
    return merged


def _skill_source_tier_rank(info: SkillInfo) -> int:
    """Higher wins when collapsing duplicate skill identities."""
    path = getattr(info, "path", None)
    source = str(getattr(info, "source", "") or "")
    try:
        if path is not None:
            resolved = Path(path).resolve()
            if GLOBAL_SKILLS_DIR.resolve() in resolved.parents:
                return 4
            if NPX_SKILLS_DIR.resolve() in resolved.parents:
                return 3
    except Exception:  # noqa: BLE001
        pass
    if source == "global":
        return 4
    if source == "npx":
        return 3
    if source == "project" or source.startswith("project"):
        return 1
    if source == "bundled":
        return 0
    return 2


def _prefer_duplicate_skill(current: SkillInfo, candidate: SkillInfo) -> SkillInfo:
    current_rank = _skill_source_tier_rank(current)
    candidate_rank = _skill_source_tier_rank(candidate)
    if candidate_rank != current_rank:
        return candidate if candidate_rank > current_rank else current
    if bool(candidate.version) != bool(current.version):
        return candidate if candidate.version else current
    if bool(candidate.updated_at) != bool(current.updated_at):
        return candidate if candidate.updated_at else current
    return current


def _collapse_skills_by_name(skills: dict[str, SkillInfo]) -> dict[str, SkillInfo]:
    """Collapse directory-key collisions that share one frontmatter skill name."""
    chosen: dict[str, tuple[str, SkillInfo]] = {}
    for key, info in skills.items():
        identity = _normalize_skill_lookup(info.name) or _normalize_skill_lookup(key)
        if not identity:
            continue
        existing = chosen.get(identity)
        if existing is None:
            chosen[identity] = (key, info)
            continue
        existing_key, existing_info = existing
        winner = _prefer_duplicate_skill(existing_info, info)
        if winner is info:
            # Keep a directory key that matches the public skill name when possible.
            preferred_key = key
            if _normalize_skill_lookup(existing_key) == identity and _normalize_skill_lookup(
                key
            ) != identity:
                preferred_key = existing_key
            chosen[identity] = (preferred_key, winner)
        else:
            chosen[identity] = (existing_key, existing_info)
    return {key: info for key, info in chosen.values()}


def list_skills(
    project_root: Optional[Path] = None,
    *,
    enabled_only: bool = False,
) -> list[SkillInfo]:
    return [
        s for _, s in sorted(iter_skills(project_root, enabled_only=enabled_only).items())
    ]


def _normalize_skill_lookup(value: str) -> str:
    return str(value or "").strip().lower().replace("_", "-")


def _resolve_skill_key(name: str, skills: dict[str, SkillInfo]) -> Optional[str]:
    # Exact directory key first.
    if name in skills:
        return name

    lowered = str(name or "").strip().lower()
    for key in skills:
        if key.lower() == lowered:
            return key

    # Match SKILL.md frontmatter name (e.g. "find-skills").
    for key, info in skills.items():
        if str(getattr(info, "name", "")).strip().lower() == lowered:
            return key

    # Last resort: normalize "_" and "-" differences.
    normalized = _normalize_skill_lookup(name)
    for key, info in skills.items():
        if _normalize_skill_lookup(key) == normalized:
            return key
        if _normalize_skill_lookup(getattr(info, "name", "")) == normalized:
            return key
    return None


def skill_info(name: str, project_root: Optional[Path] = None) -> Optional[SkillInfo]:
    skills = iter_skills(project_root)
    key = _resolve_skill_key(name, skills)
    return skills.get(key) if key is not None else None


def installed_skill_names(project_root: Optional[Path] = None) -> list[str]:
    return sorted(iter_skills(project_root).keys())


def _tokenize_skill_text(text: str) -> set[str]:
    tokens = set(_SKILL_TOKEN_RE.findall((text or "").lower()))
    return {t for t in tokens if len(t) >= 2 and t not in _SKILL_STOPWORDS}


def _path_signature(path: Path) -> str:
    try:
        st = path.stat()
        return f"{st.st_size}:{st.st_mtime_ns}"
    except Exception:  # noqa: BLE001
        return ""


def _read_text_prefix(path: Path, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            return f.read(max_chars)
    except Exception:  # noqa: BLE001
        return ""


def _read_prompt_index_cache() -> dict:
    if not SKILLS_PROMPT_INDEX_CACHE.exists():
        return {"version": _SKILLS_PROMPT_INDEX_VERSION, "entries": {}}
    try:
        raw = json.loads(SKILLS_PROMPT_INDEX_CACHE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {"version": _SKILLS_PROMPT_INDEX_VERSION, "entries": {}}
    if not isinstance(raw, dict):
        return {"version": _SKILLS_PROMPT_INDEX_VERSION, "entries": {}}
    entries = raw.get("entries")
    if not isinstance(entries, dict):
        entries = {}
    return {
        "version": int(raw.get("version") or _SKILLS_PROMPT_INDEX_VERSION),
        "updated_at": float(raw.get("updated_at") or 0.0),
        "entries": entries,
    }


def _write_prompt_index_cache(entries: dict[str, dict]) -> None:
    payload = {
        "version": _SKILLS_PROMPT_INDEX_VERSION,
        "updated_at": time.time(),
        "entries": entries,
    }
    try:
        SKILLS_PROMPT_INDEX_CACHE.parent.mkdir(parents=True, exist_ok=True)
        tmp = SKILLS_PROMPT_INDEX_CACHE.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(SKILLS_PROMPT_INDEX_CACHE)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Could not write skills prompt index cache: %s", exc)


def _build_skill_token_index(
    skills: dict[str, SkillInfo],
    *,
    snippet_chars: int = _SKILL_INDEX_SNIPPET_CHARS,
) -> dict[str, set[str]]:
    """Return per-skill token sets, reusing a disk cache when unchanged."""
    cache = _read_prompt_index_cache()
    cached_entries = cache.get("entries", {})
    if not isinstance(cached_entries, dict):
        cached_entries = {}

    index: dict[str, set[str]] = {}
    next_entries: dict[str, dict] = {}
    changed = cache.get("version") != _SKILLS_PROMPT_INDEX_VERSION

    for name, info in sorted(skills.items()):
        if not info.path:
            continue
        path = info.path
        path_sig = _path_signature(path)
        directory = info.directory
        scripts = _skill_script_names(directory) if directory else []
        scripts_sig = ",".join(
            f"{script}:{_path_signature(directory / 'scripts' / script)}"
            for script in scripts
        ) if directory else ""

        cached = cached_entries.get(name)
        cached_ok = (
            isinstance(cached, dict)
            and str(cached.get("path") or "") == str(path)
            and str(cached.get("path_sig") or "") == path_sig
            and str(cached.get("scripts_sig") or "") == scripts_sig
            and isinstance(cached.get("tokens"), list)
        )
        if cached_ok:
            tokens = {
                str(tok)
                for tok in (cached.get("tokens") or [])
                if isinstance(tok, str) and tok
            }
        else:
            snippet = _read_text_prefix(path, max(0, int(snippet_chars)))
            text_blob = " ".join(
                [
                    name,
                    info.description or "",
                    " ".join(info.tags or []),
                    " ".join(scripts),
                    snippet,
                ]
            )
            tokens = _tokenize_skill_text(text_blob)
            changed = True

        index[name] = tokens
        next_entries[name] = {
            "path": str(path),
            "path_sig": path_sig,
            "scripts_sig": scripts_sig,
            "tokens": sorted(tokens),
        }

    if set(next_entries) != set(cached_entries):
        changed = True
    if changed:
        _write_prompt_index_cache(next_entries)

    return index


def _score_skill_query_match(
    name: str,
    info: SkillInfo,
    query: str,
    *,
    query_tokens: Optional[set[str]] = None,
    skill_tokens: Optional[set[str]] = None,
) -> int:
    query_lc = (query or "").lower().strip()
    if not query_lc:
        return 0
    query_tokens = query_tokens or _tokenize_skill_text(query_lc)
    if not query_tokens:
        return 0

    name_lc = name.lower()
    name_tokens = _tokenize_skill_text(name_lc.replace("_", " "))
    if skill_tokens is None:
        desc_lc = (info.description or "").lower()
        tag_tokens = _tokenize_skill_text(" ".join(info.tags))
        skill_tokens = name_tokens | _tokenize_skill_text(desc_lc) | tag_tokens

    score = 0
    if name_lc and name_lc in query_lc:
        score += 80
    for tag in (t.lower() for t in info.tags if t):
        if len(tag) > 2 and tag in query_lc:
            score += 20

    overlap = query_tokens & skill_tokens
    score += len(overlap) * 8
    score += len(query_tokens & name_tokens) * 10
    return score


def _skill_script_names(directory: Path) -> list[str]:
    scripts_dir = directory / "scripts"
    if not scripts_dir.is_dir():
        return []
    return sorted(
        p.name for p in scripts_dir.glob("*.py")
        if not p.name.startswith("_")
    )


def _build_skill_catalog(
    skills: dict[str, SkillInfo],
    max_entries: int = 250,
    description_chars: int = 140,
) -> str:
    if not skills:
        return ""

    items = sorted(skills.items())
    shown = items[:max_entries]
    lines: list[str] = []
    for name, info in shown:
        desc = (info.description or "").strip().replace("\n", " ")
        if len(desc) > description_chars:
            desc = desc[:description_chars - 1].rstrip() + "…"
        tags = ", ".join(info.tags[:4]) if info.tags else "-"
        lines.append(
            f"- `{name}` — {desc or 'No description'} "
            f"(tags: {tags}; source: {info.source or '-'})."
        )

    tail = ""
    if len(items) > len(shown):
        tail = (
            f"\n\nCatalog truncated to {len(shown)} of {len(items)} installed skills. "
            "If a needed skill is missing from this list, discover by name and load it on demand."
        )

    return (
        "### Skill Catalog (compact)\n\n"
        "Installed skills are indexed below. Use this list to decide which skills are relevant "
        "to the current request. Full SKILL.md bodies are loaded only for selected skills.\n\n"
        + "\n".join(lines)
        + tail
    )


def _format_selected_skill_section(
    name: str,
    info: SkillInfo,
    raw_content: str,
) -> str:
    content = raw_content
    header = f"### Skill: `{name}`"
    directory = info.directory
    if directory is None:
        return f"{header}\n\n{content}"

    dir_str = str(directory)
    scripts = _skill_script_names(directory)
    if scripts:
        content = content.replace("python scripts/", f"python {dir_str}/scripts/")
        content = content.replace("`scripts/", f"`{dir_str}/scripts/")
        header += (
            f"\n\n**Skill directory:** `{dir_str}`. "
            f"Scripts: {', '.join(scripts)}. "
            f"Always invoke scripts by absolute path (for example, "
            f"`python {dir_str}/scripts/<name>.py ...`)."
        )
    else:
        header += (
            f"\n\n**Skill directory:** `{dir_str}`. "
            "This skill has no `scripts/` directory; follow SKILL.md instructions with available tools."
        )
    return f"{header}\n\n{content}"


def build_skills_prompt(
    project_root: Optional[Path] = None,
    user_request: str | None = None,
    max_catalog_entries: int = 250,
    max_active_skills: int = 6,
    max_active_chars: int = 120_000,
    catalog_description_chars: int = 140,
    index_snippet_chars: int = _SKILL_INDEX_SNIPPET_CHARS,
) -> str:
    """Build an adaptive 'Installed Agent Skills' prompt section.

    Strategy:
    1) Always include a compact catalog for all installed skills.
    2) Include full SKILL.md content only for request-relevant skills, capped by
       both skill count and character budget.
    """
    skills = iter_skills(project_root, enabled_only=True)
    if not skills:
        return ""

    catalog = _build_skill_catalog(
        skills,
        max_entries=max_catalog_entries,
        description_chars=catalog_description_chars,
    )

    request = (user_request or "").strip()
    ranked: list[tuple[int, str, SkillInfo]] = []
    if request:
        token_index = _build_skill_token_index(
            skills,
            snippet_chars=max(0, int(index_snippet_chars)),
        )
        query_tokens = _tokenize_skill_text(request.lower())
        for name, info in skills.items():
            score = _score_skill_query_match(
                name,
                info,
                request,
                query_tokens=query_tokens,
                skill_tokens=token_index.get(name),
            )
            if score > 0:
                ranked.append((score, name, info))
        ranked.sort(key=lambda item: (-item[0], item[1]))

    selected_sections: list[str] = []
    budget = max(0, int(max_active_chars))
    for score, name, info in ranked[:max(0, int(max_active_skills))]:
        if budget <= 0 or not info.path:
            break
        try:
            raw = info.path.read_text(encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            logger.debug("Could not read skill %s: %s", name, exc)
            continue
        section = _format_selected_skill_section(name, info, raw)
        if len(section) > budget:
            if budget < 800:
                break
            take = max(400, budget - 240)
            section = (
                _format_selected_skill_section(name, info, raw[:take].rstrip())
                + "\n\n[Skill content truncated to fit prompt budget.]"
            )
        selected_sections.append(section)
        budget -= len(section)
        logger.debug("Selected skill '%s' (score=%d, chars=%d)", name, score, len(section))

    intro = (
        "## Installed Agent Skills\n\n"
        "You have installed skills that can provide high-quality task-specific workflows. "
        "Follow a skill's instructions when the request matches its use-case.\n\n"
    )
    details = ""
    if selected_sections:
        details = (
            "\n\n### Selected Skill Details\n\n"
            "The following full skill instructions were selected for this request:\n\n"
            + "\n\n---\n\n".join(selected_sections)
        )
    else:
        details = (
            "\n\n### Selected Skill Details\n\n"
            "No specific skills matched strongly enough for this request. "
            "Use the catalog to pick one only if needed."
        )

    return intro + catalog + details


# ─── Source parsing ─────────────────────────────────────────────────────────
def detect_source_type(source: str) -> str:
    """Classify a skill source string: 'local', 'github', 'shorthand', or 'name'."""
    s = (source or "").strip()
    if not s:
        return "name"
    if s.startswith(("./", "../", "/", "~")) or Path(s).expanduser().exists():
        return "local"
    if s.startswith("http://") or s.startswith("https://") or s.startswith("git@"):
        return "github"
    if "/" in s and _GITHUB_SHORTHAND_RE.match(s):
        return "shorthand"
    return "name"


def _parse_github(source: str) -> tuple[str, Optional[str], Optional[str]]:
    """Return (clone_url, ref, subpath) for a GitHub URL or shorthand."""
    s = source.strip()

    # Shorthand: owner/repo[@subpath]
    m = _GITHUB_SHORTHAND_RE.match(s)
    if m and not s.startswith(("http", "git@")):
        owner, repo, sub = m.group("owner"), m.group("repo"), m.group("sub")
        repo = repo[:-4] if repo.endswith(".git") else repo
        return f"https://github.com/{owner}/{repo}.git", None, sub

    # Full URL, optionally with /tree/<ref>/<subpath>
    url = s
    ref: Optional[str] = None
    sub: Optional[str] = None
    tree = re.search(r"github\.com[:/](?P<owner>[\w.-]+)/(?P<repo>[\w.-]+?)(?:\.git)?(?:/tree/(?P<ref>[^/]+)(?:/(?P<sub>.+))?)?/?$", s)
    if tree:
        owner = tree.group("owner")
        repo = tree.group("repo")
        ref = tree.group("ref")
        sub = tree.group("sub")
        url = f"https://github.com/{owner}/{repo}.git"
    return url, ref, sub


# ─── Install ────────────────────────────────────────────────────────────────
def _git_available() -> bool:
    return shutil.which("git") is not None


def _npx_available() -> bool:
    return shutil.which("npx") is not None


def _noninteractive_git_env() -> dict:
    """Env that prevents git from blocking on interactive auth/SSH prompts.

    Without this, a transient 403 / auth challenge on an otherwise public clone
    makes ``git`` hang forever waiting for a username/password on stdin, which
    the subprocess timeout can't always interrupt cleanly. Failing fast lets us
    fall back to the GitHub archive download instead of stalling the upgrade.
    """
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_ASKPASS"] = "echo"
    env["GCM_INTERACTIVE"] = "never"
    env.setdefault("GIT_SSH_COMMAND", "ssh -oBatchMode=yes -oStrictHostKeyChecking=no")
    return env


def _git_clone(url: str, ref: Optional[str], dest: Path) -> Optional[str]:
    """Shallow clone ``url`` into ``dest``. Returns the commit SHA or None."""
    cmd = ["git", "clone", "--depth", "1"]
    if ref:
        cmd += ["--branch", ref]
    cmd += [url, str(dest)]
    env = _noninteractive_git_env()
    subprocess.run(
        cmd,
        check=True,
        capture_output=True,
        text=True,
        timeout=_CLONE_TIMEOUT_S,
        stdin=subprocess.DEVNULL,
        env=env,
    )
    try:
        out = subprocess.run(
            ["git", "-C", str(dest), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True, timeout=30,
            stdin=subprocess.DEVNULL, env=env,
        )
        return out.stdout.strip() or None
    except Exception:  # noqa: BLE001
        return None


def _resolve_skill_dirs(root: Path, subpath: Optional[str]) -> list[Path]:
    """Find skill directories (containing SKILL.md) within a cloned repo."""
    base = (root / subpath) if subpath else root
    if not base.exists():
        base = root

    # Single skill directly at base.
    if (base / "SKILL.md").exists():
        return [base]

    # Otherwise treat children (depth 1) with SKILL.md as a pack.
    if base.exists() and base.is_dir():
        found = [
            c
            for c in sorted(base.iterdir())
            if c.is_dir() and (c / "SKILL.md").exists()
        ]
        if found:
            return found

    # Monorepo convention: skills live under a 'skills/' folder
    # (e.g. fastfold-ai/skills with skills/<name>/SKILL.md). Mirrors discover_skills().
    skills_dir = base / "skills"
    if skills_dir.exists():
        found = [
            c
            for c in sorted(skills_dir.iterdir())
            if c.is_dir() and (c / "SKILL.md").exists()
        ]
        if found:
            return found

    # Skills.sh / curated layouts may nest skills (e.g. skills/.curated/<name>).
    # When a specific subpath was requested, search by the final folder name.
    if subpath:
        wanted = _normalize_skill_lookup(Path(subpath).name)
        if wanted:
            matches: list[Path] = []
            for skill_md in root.rglob("SKILL.md"):
                parent = skill_md.parent
                if _normalize_skill_lookup(parent.name) == wanted:
                    matches.append(parent)
            if matches:
                # Prefer shallower paths when multiple matches exist.
                matches.sort(key=lambda path: (len(path.parts), str(path)))
                return [matches[0]]
    return []


def _read_manifest(dest: Path) -> dict:
    path = dest / MANIFEST_FILENAME
    if not path.exists():
        return {"version": 1, "skills": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if "skills" not in data:
            data["skills"] = {}
        return data
    except Exception:  # noqa: BLE001
        return {"version": 1, "skills": {}}


def _write_manifest(dest: Path, manifest: dict) -> None:
    path = dest / MANIFEST_FILENAME
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    tmp.replace(path)


def _skill_state_path() -> Path:
    return CONFIG_DIR / SKILL_STATE_FILENAME


def _read_skill_state() -> dict:
    path = _skill_state_path()
    if not path.exists():
        return {"version": 1, "disabled": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {"version": 1, "disabled": []}
    if not isinstance(data, dict):
        return {"version": 1, "disabled": []}
    disabled = data.get("disabled")
    if not isinstance(disabled, list):
        disabled = []
    return {
        "version": int(data.get("version") or 1),
        "disabled": [str(name) for name in disabled if str(name).strip()],
    }


def _write_skill_state(state: dict) -> None:
    path = _skill_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(path)


def _disabled_skill_names() -> set[str]:
    state = _read_skill_state()
    return {name for name in state.get("disabled", []) if isinstance(name, str)}


def _set_disabled_skill_names(names: set[str]) -> None:
    _write_skill_state(
        {
            "version": 1,
            "disabled": sorted(name for name in names if name.strip()),
        }
    )


def set_skill_enabled(
    name: str,
    enabled: bool,
    *,
    project_root: Optional[Path] = None,
) -> dict:
    skills = iter_skills(project_root)
    key = _resolve_skill_key(name, skills)
    if key is None:
        return {"ok": False, "summary": f"Skill '{name}' is not installed."}
    disabled = _disabled_skill_names()
    aliases = {key}
    normalized = _normalize_skill_lookup(key)
    for candidate_key, info in skills.items():
        if _normalize_skill_lookup(candidate_key) == normalized:
            aliases.add(candidate_key)
        if _normalize_skill_lookup(getattr(info, "name", "")) == normalized:
            aliases.add(candidate_key)
    if enabled:
        disabled -= aliases
    else:
        disabled |= aliases
    _set_disabled_skill_names(disabled)
    display_name = str(getattr(skills.get(key), "name", "") or key)
    return {
        "ok": True,
        "summary": f"{'Enabled' if enabled else 'Disabled'} skill '{display_name}'.",
    }


def _clear_skill_enabled_state(names: set[str]) -> None:
    if not names:
        return
    disabled = _disabled_skill_names()
    if not (disabled & names):
        return
    disabled -= names
    _set_disabled_skill_names(disabled)


def _record_install(
    dest: Path,
    name: str,
    source: str,
    commit: Optional[str],
    release: Optional[str] = None,
) -> None:
    entry = {
        "source": source,
        "commit": commit,
        "installed_at": datetime.now(timezone.utc).isoformat(),
    }
    if release:
        entry["release"] = release
    # Hold the lock across the read-modify-write so concurrent installs can't
    # clobber each other's manifest entries.
    with _MANIFEST_LOCK:
        manifest = _read_manifest(dest)
        manifest["skills"][name] = entry
        _write_manifest(dest, manifest)


def _npx_target(source: str) -> tuple[str, Optional[str], bool]:
    """Map a skill source to (npx_target, skill_name, whole_repo) for `npx skills add`.

    - ``owner/repo@subpath`` -> (``owner/repo``, ``<last path segment>``, False)
    - GitHub ``/tree/<ref>/<path>`` URL -> (url, None, False)  # URL targets one skill
    - whole-repo shorthand/URL -> (source, None, True)
    """
    s = (source or "").strip()
    if s.startswith(("http://", "https://", "git@")):
        return s, None, ("/tree/" not in s)
    if "@" in s:
        repo, sub = s.split("@", 1)
        name = sub.rstrip("/").split("/")[-1] or None
        return repo, name, False
    return s, None, True


def _run_npx_add(target: str, skill_names: Optional[list[str]] = None, whole: bool = False) -> None:
    """Run `npx skills add` non-interactively, pinned to the fastfold-owned dir."""
    NPX_INSTALL_ROOT.mkdir(parents=True, exist_ok=True)
    cmd = ["npx", "-y", "skills", "add", target, "-a", "claude-code", "--copy", "-y"]
    if skill_names:
        for name in skill_names:
            cmd += ["--skill", name]
    elif whole:
        cmd += ["--skill", "*"]
    subprocess.run(
        cmd,
        check=True,
        capture_output=True,
        text=True,
        timeout=_CLONE_TIMEOUT_S,
        stdin=subprocess.DEVNULL,
        cwd=str(NPX_INSTALL_ROOT),
    )


def npx_add(target: str, skill_names: Optional[list[str]] = None, whole: bool = False) -> dict:
    """Install one or more skills from a single repo/URL via `npx skills add`."""
    if not _npx_available():
        return {"ok": False, "summary": "npx is not available.", "via": "npx"}
    try:
        _run_npx_add(target, skill_names, whole)
        what = f"{target}" + (f" (skills: {', '.join(skill_names)})" if skill_names else " (all)" if whole else "")
        return {
            "ok": True,
            "installed": list(skill_names or []),
            "summary": f"Installed {what} via npx into {NPX_SKILLS_DIR}.",
            "via": "npx",
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "summary": f"npx skills add timed out for {target}.", "via": "npx"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "summary": f"npx skills add failed: {exc}", "via": "npx"}


def _npx_install(source: str) -> dict:
    """Install a single source via npx (handles owner/repo@subpath via --skill)."""
    target, skill, whole = _npx_target(source)
    return npx_add(target, [skill] if skill else None, whole)


def _npx_update() -> dict:
    """Update all npx-installed skills in the fastfold-owned dir (`npx skills update`)."""
    if not _npx_available():
        return {"ok": False, "summary": "npx is not available."}
    try:
        subprocess.run(
            ["npx", "-y", "skills", "update", "-y"],
            check=True, capture_output=True, text=True,
            timeout=_CLONE_TIMEOUT_S, stdin=subprocess.DEVNULL, cwd=str(NPX_INSTALL_ROOT),
        )
        return {"ok": True, "summary": "Updated npx-installed skills."}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "summary": f"npx skills update failed: {exc}"}


# ─── GitHub releases + update cache ─────────────────────────────────────────
GITHUB_API = "https://api.github.com"
SKILLS_UPDATE_CACHE = CONFIG_DIR / "skills_update_check.json"
_UPDATE_CHECK_INTERVAL_S = 24 * 3600
_SEMVER_TAG_RE = re.compile(r"v?(\d+)\.(\d+)\.(\d+)")


def _owner_repo_from_source(source: str) -> Optional[str]:
    """Extract ``owner/repo`` from a GitHub URL or shorthand (drops any @subpath)."""
    s = (source or "").strip()
    if not s:
        return None
    if s.startswith(("http://", "https://", "git@")):
        m = re.search(r"github\.com[:/](?P<owner>[\w.-]+)/(?P<repo>[\w.-]+?)(?:\.git)?(?:/|$)", s)
        return f"{m.group('owner')}/{m.group('repo')}" if m else None
    m = _GITHUB_SHORTHAND_RE.match(s)
    if m:
        return f"{m.group('owner')}/{m.group('repo')}"
    return None


def _tag_tuple(tag: str) -> Optional[tuple[int, int, int]]:
    m = _SEMVER_TAG_RE.search(str(tag or ""))
    return tuple(int(x) for x in m.groups()) if m else None


def _is_newer_tag(latest: str, current: str) -> bool:
    lt, ct = _tag_tuple(latest), _tag_tuple(current)
    if not lt or not ct:
        return False
    return lt > ct


def _http_get_bytes(
    url: str,
    *,
    timeout: float = _CLONE_TIMEOUT_S,
    headers: Optional[dict[str, str]] = None,
) -> bytes:
    """Fetch HTTP(S) bytes with certifi-backed TLS (fixes Windows urllib SSL issues)."""
    import httpx

    hdrs = {"User-Agent": "fastfold-agent-cli", **(headers or {})}
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        resp = client.get(url, headers=hdrs)
        resp.raise_for_status()
        return resp.content


def fetch_latest_release(owner_repo: str, *, timeout_s: float = 2.5) -> Optional[dict]:
    """Return ``{"tag", "published_at"}`` for a repo's latest GitHub Release.

    Best-effort and network-bound: returns None on any error or when the repo
    has no releases (HTTP 404). Used to surface a version in the /skills table.
    """
    import httpx

    if not owner_repo:
        return None
    url = f"{GITHUB_API}/repos/{owner_repo}/releases/latest"
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "fastfold-agent-cli"}
    try:
        with httpx.Client(timeout=timeout_s, follow_redirects=True) as client:
            resp = client.get(url, headers=headers)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, TimeoutError, ValueError):
        return None
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(data, dict):
        return None
    tag = str(data.get("tag_name") or "").strip()
    if not tag:
        return None
    return {"tag": tag, "published_at": str(data.get("published_at") or "")}


def _read_update_cache() -> dict:
    if not SKILLS_UPDATE_CACHE.exists():
        return {}
    try:
        data = json.loads(SKILLS_UPDATE_CACHE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _write_update_cache(cache: dict) -> None:
    try:
        SKILLS_UPDATE_CACHE.parent.mkdir(parents=True, exist_ok=True)
        tmp = SKILLS_UPDATE_CACHE.with_suffix(".tmp")
        tmp.write_text(json.dumps(cache, indent=2), encoding="utf-8")
        tmp.replace(SKILLS_UPDATE_CACHE)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Could not write skills update cache: %s", exc)


def _installed_catalog_release(catalog: str = DEFAULT_CATALOG) -> Optional[str]:
    """Return the release tag recorded for the installed Fastfold catalog, if any."""
    owner_repo = catalog.split("@", 1)[0]
    manifest = _read_manifest(GLOBAL_SKILLS_DIR)
    for meta in (manifest.get("skills") or {}).values():
        if not isinstance(meta, dict):
            continue
        src = str(meta.get("source") or "")
        if _owner_repo_from_source(src) == owner_repo and meta.get("release"):
            return str(meta["release"])
    return None


def get_cached_skills_update(catalog: str = DEFAULT_CATALOG) -> Optional[dict]:
    """Local-only check (no network) for a newer catalog release.

    Returns ``{"installed", "latest", "published_at"}`` when the cached latest
    release is newer than the installed catalog release, else None. Safe to call
    on the boot path.
    """
    cache = _read_update_cache()
    latest = cache.get("latest_release")
    if not latest:
        return None
    installed = _installed_catalog_release(catalog)
    if not installed:
        return None
    if _is_newer_tag(str(latest), installed):
        return {
            "installed": installed,
            "latest": str(latest),
            "published_at": str(cache.get("latest_published_at") or ""),
        }
    return None


def refresh_skills_update_cache(
    *, catalog: str = DEFAULT_CATALOG, timeout_s: float = 2.5, force: bool = False
) -> None:
    """Refresh the cached latest catalog release (network). Throttled to 24h.

    Designed to run in a daemon thread so the next boot reads a fresh cache
    without any network on the boot path.
    """
    cache = _read_update_cache()
    if not force:
        checked = cache.get("checked_at")
        if checked:
            try:
                last = datetime.fromisoformat(str(checked))
                if (datetime.now(timezone.utc) - last).total_seconds() < _UPDATE_CHECK_INTERVAL_S:
                    return
            except Exception:  # noqa: BLE001
                pass
    owner_repo = catalog.split("@", 1)[0]
    rel = fetch_latest_release(owner_repo, timeout_s=timeout_s)
    _write_update_cache(
        {
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "latest_release": (rel or {}).get("tag"),
            "latest_published_at": (rel or {}).get("published_at", ""),
        }
    )

def _owner_repo_from_clone_url(url: str) -> Optional[str]:
    m = re.search(r"github\.com/(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+?)(?:\.git)?$", url)
    if not m:
        return None
    return f"{m.group('owner')}/{m.group('repo')}"


def _format_git_error(exc: subprocess.CalledProcessError) -> str:
    detail = (exc.stderr or exc.stdout or str(exc)).strip()
    if len(detail) > 200:
        detail = detail[:197] + "..."
    return detail or "git clone failed"


def _download_github_archive(owner: str, repo: str, ref: Optional[str], extract_parent: Path) -> Path:
    """Download and extract a GitHub repo archive without git."""
    import io
    import zipfile

    import httpx

    ref_key = ref or "HEAD"
    url = f"https://codeload.github.com/{owner}/{repo}/zip/{ref_key}"
    try:
        data = _http_get_bytes(url, timeout=_CLONE_TIMEOUT_S)
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"GitHub archive download failed (HTTP {exc.response.status_code})") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"GitHub archive download failed: {exc}") from exc

    extract_parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        zf.extractall(extract_parent)
    roots = [p for p in extract_parent.iterdir() if p.is_dir()]
    if len(roots) == 1:
        return roots[0]
    if not roots:
        raise RuntimeError("GitHub archive contained no directories")
    return extract_parent


def _install_from_repo_tree(
    repo_root: Path,
    subpath: Optional[str],
    dest: Path,
    source: str,
    commit: Optional[str],
    release_tag: Optional[str],
    via: str,
) -> dict:
    skill_dirs = _resolve_skill_dirs(repo_root, subpath)
    if not skill_dirs:
        return {
            "ok": False,
            "summary": (
                f"No SKILL.md found in {source}. "
                "This skill may have been removed or moved in the source repository "
                "or Skills.sh listing."
            ),
            "via": via,
        }
    installed = _copy_skill_dirs(skill_dirs, dest, source, commit, release_tag)
    return {
        "ok": True,
        "installed": installed,
        "summary": f"Installed {len(installed)} skill(s) to {dest}: {', '.join(installed)}.",
        "via": via,
    }


def _install_github_source(
    source: str,
    url: str,
    ref: Optional[str],
    subpath: Optional[str],
    dest: Path,
    release_tag: Optional[str],
) -> dict:
    """Install a GitHub source via git clone, archive download, then optional npx."""
    errors: list[str] = []

    if _git_available():
        try:
            with tempfile.TemporaryDirectory(prefix="fastfold-skill-") as tmp:
                clone_root = Path(tmp) / "repo"
                commit = _git_clone(url, ref, clone_root)
                return _install_from_repo_tree(
                    clone_root, subpath, dest, source, commit, release_tag, "git"
                )
        except subprocess.CalledProcessError as exc:
            logger.debug("git clone failed: %s", exc)
            errors.append(f"git clone failed: {_format_git_error(exc)}")
        except Exception as exc:  # noqa: BLE001
            logger.debug("git install failed: %s", exc)
            errors.append(f"git install failed: {exc}")

    owner_repo = _owner_repo_from_clone_url(url)
    if owner_repo:
        owner, repo = owner_repo.split("/", 1)
        try:
            with tempfile.TemporaryDirectory(prefix="fastfold-skill-") as tmp:
                extract_parent = Path(tmp)
                repo_root = _download_github_archive(owner, repo, ref, extract_parent)
                return _install_from_repo_tree(
                    repo_root, subpath, dest, source, None, release_tag, "archive"
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("GitHub archive install failed: %s", exc)
            errors.append(str(exc))

    if _npx_available():
        result = _npx_install(source)
        if result.get("ok"):
            return result
        errors.append(result.get("summary", "npx install failed"))

    summary = errors[0] if len(errors) == 1 else "; ".join(errors)
    if not summary:
        summary = "Could not install skill from GitHub."
    return {"ok": False, "summary": summary, "via": "git"}


def install_skill(source: str, *, dest: Optional[Path] = None, prefer_npx: bool = False) -> dict:
    """Install a skill from a GitHub URL/shorthand, local path, or catalog name.

    By default uses a native ``git clone``, then GitHub archive download, then
    ``npx skills add`` when available. When ``prefer_npx`` is True and ``npx`` is
    available, tries ``npx skills add`` first and falls back to git/archive.

    Returns a dict with keys: ok, installed (list of names), summary.
    """
    source = (source or "").strip()
    if not source:
        return {"ok": False, "summary": "No skill source provided."}

    dest = dest or GLOBAL_SKILLS_DIR
    dest.mkdir(parents=True, exist_ok=True)

    src_type = detect_source_type(source)

    # Resolve a bare name against the catalog before installing.
    if src_type == "name":
        match = _resolve_name_to_source(source)
        if not match:
            return {"ok": False, "summary": f"Could not find a skill named '{source}' in the catalog."}
        source = match
        src_type = detect_source_type(source)

    if src_type == "local":
        return _install_local(source, dest)

    url, ref, subpath = _parse_github(source)

    # Prefer npx when requested. npx handles both whole-repo and specific-skill
    # installs (the latter via --skill, derived from our owner/repo@subpath shorthand).
    if prefer_npx and _npx_available():
        result = _npx_install(source)
        if result.get("ok"):
            return result
        logger.debug("npx skills add failed, falling back to git/archive: %s", result.get("summary"))

    owner_repo = _owner_repo_from_source(source)
    release_info = fetch_latest_release(owner_repo) if owner_repo else None
    release_tag = release_info.get("tag") if release_info else None
    return _install_github_source(source, url, ref, subpath, dest, release_tag)


def _install_local(source: str, dest: Path) -> dict:
    base = Path(source).expanduser().resolve()
    if not base.exists():
        return {"ok": False, "summary": f"Local path does not exist: {source}"}
    skill_dirs = _resolve_skill_dirs(base, None)
    if not skill_dirs:
        return {"ok": False, "summary": f"No SKILL.md found at {source}."}
    installed = _copy_skill_dirs(skill_dirs, dest, str(base), None)
    return {
        "ok": True,
        "installed": installed,
        "summary": f"Installed {len(installed)} skill(s) to {dest}: {', '.join(installed)}.",
        "via": "local",
    }


def _copy_skill_dirs(
    skill_dirs: list[Path],
    dest: Path,
    source: str,
    commit: Optional[str],
    release: Optional[str] = None,
) -> list[str]:
    installed: list[str] = []
    for sd in skill_dirs:
        name = sd.name
        target = dest / name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(sd, target, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))
        _record_install(dest, name, source, commit, release)
        installed.append(name)
    return installed


def _project_lock_sources(project_root: Path) -> list[str]:
    """Return distinct skill sources recorded in a project's skills-lock.json (npx installs)."""
    lock_file = project_root / "skills-lock.json"
    if not lock_file.exists():
        return []
    try:
        lock = json.loads(lock_file.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []
    sources: list[str] = []
    for meta in (lock.get("skills") or {}).values():
        if isinstance(meta, dict) and meta.get("source"):
            src = str(meta["source"]).strip()
            if src and src not in sources:
                sources.append(src)
    return sources


def _clone_repo_once(url: str, ref: Optional[str], tmp_root: Path) -> tuple[Optional[Path], Optional[str], str]:
    """Clone ``url`` once (git, then archive fallback) into ``tmp_root``.

    Returns ``(repo_root, commit, via)``. ``repo_root`` is None when both
    strategies fail.
    """
    if _git_available():
        try:
            clone_root = tmp_root / "repo"
            commit = _git_clone(url, ref, clone_root)
            return clone_root, commit, "git"
        except subprocess.CalledProcessError as exc:
            logger.debug("group git clone failed for %s: %s", url, exc)
        except Exception as exc:  # noqa: BLE001
            logger.debug("group git install failed for %s: %s", url, exc)

    owner_repo = _owner_repo_from_clone_url(url)
    if owner_repo:
        owner, repo = owner_repo.split("/", 1)
        try:
            repo_root = _download_github_archive(owner, repo, ref, tmp_root)
            return repo_root, None, "archive"
        except Exception as exc:  # noqa: BLE001
            logger.debug("group archive install failed for %s: %s", url, exc)

    return None, None, "git"


def _run_grouped_clones(
    groups: dict,
    group_owner_repo: dict,
    install_item: callable,
    *,
    max_workers: Optional[int] = None,
    notify: Optional[callable] = None,
    label: str = "Updating skills",
    fetch_release: bool = True,
) -> tuple[list[str], list[tuple[str, str]]]:
    """Clone each ``(url, ref)`` group once and install its items in parallel.

    ``groups`` maps ``(url, ref)`` to a list of opaque ``item`` tuples whose
    first element is the source identifier (used for failure reporting).
    ``install_item(repo_root, commit, release_tag, via, item)`` does the per-item
    copy and returns ``(installed_names, failures)``.

    Emits ``"<label> <done>/<total>..."`` progress as each repo finishes so the
    user sees an n/m counter.
    """

    def _notify(msg: str) -> None:
        if notify is not None:
            try:
                notify(msg)
            except Exception:  # noqa: BLE001
                pass

    total = sum(len(items) for items in groups.values())
    done = 0
    installed: list[str] = []
    failures: list[tuple[str, str]] = []
    if not groups:
        return installed, failures

    def _process_group(key, items) -> tuple[list[str], list[tuple[str, str]]]:
        url, ref = key
        owner_repo = group_owner_repo.get(key)
        release_tag = None
        if fetch_release and owner_repo:
            release_info = fetch_latest_release(owner_repo)
            release_tag = release_info.get("tag") if release_info else None
        grp_installed: list[str] = []
        grp_failures: list[tuple[str, str]] = []
        with tempfile.TemporaryDirectory(prefix="fastfold-skill-grp-") as tmp:
            repo_root, commit, via = _clone_repo_once(url, ref, Path(tmp))
            if repo_root is None:
                for item in items:
                    grp_failures.append((item[0], "clone/archive failed"))
                return grp_installed, grp_failures
            for item in items:
                try:
                    ins, fails = install_item(repo_root, commit, release_tag, via, item)
                    grp_installed += ins
                    grp_failures += fails
                except Exception as exc:  # noqa: BLE001
                    grp_failures.append((item[0], str(exc)))
        return grp_installed, grp_failures

    workers = max_workers or int(
        os.environ.get("FASTFOLD_SKILLS_SYNC_WORKERS", _DEFAULT_SYNC_WORKERS) or _DEFAULT_SYNC_WORKERS
    )
    workers = max(1, min(workers, len(groups)))

    if workers == 1:
        for key, items in groups.items():
            gi, gf = _process_group(key, items)
            installed += gi
            failures += gf
            done += len(items)
            _notify(f"{label} {done}/{total}...")
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_process_group, key, items): items for key, items in groups.items()}
            for future in as_completed(futures):
                items = futures[future]
                gi, gf = future.result()
                installed += gi
                failures += gf
                done += len(items)
                _notify(f"{label} {done}/{total}...")

    return installed, failures


def _sync_tracked_sources(
    tracked: list[tuple[str, str]],
    dest: Path,
    *,
    max_workers: Optional[int] = None,
    notify: Optional[callable] = None,
    label: str = "Updating skills",
) -> tuple[list[str], list[tuple[str, str]]]:
    """Install many tracked skill sources efficiently.

    Sources that resolve to the same GitHub repo + ref are cloned **once** and
    every requested subpath is installed from that single clone (instead of one
    clone per skill). Distinct repos are processed in parallel since the work is
    network-bound.

    Returns ``(installed_names, failures)`` where ``failures`` is a list of
    ``(source, reason)``.
    """

    def _notify(msg: str) -> None:
        if notify is not None:
            try:
                notify(msg)
            except Exception:  # noqa: BLE001
                pass

    # Group GitHub sources by (clone_url, ref); keep non-GitHub sources separate.
    groups: dict[tuple[str, Optional[str]], list[tuple[str, Optional[str]]]] = {}
    group_owner_repo: dict[tuple[str, Optional[str]], Optional[str]] = {}
    other_sources: list[str] = []
    for name, source in tracked:
        src_type = detect_source_type(source)
        if src_type in {"github", "shorthand"}:
            try:
                url, ref, subpath = _parse_github(source)
            except Exception:  # noqa: BLE001
                other_sources.append(source)
                continue
            key = (url, ref)
            groups.setdefault(key, []).append((source, subpath))
            group_owner_repo.setdefault(key, _owner_repo_from_source(source))
        else:
            other_sources.append(source)

    def _install_item(repo_root, commit, release_tag, via, item):
        source, subpath = item
        result = _install_from_repo_tree(
            repo_root, subpath, dest, source, commit, release_tag, via
        )
        if result.get("ok"):
            return result.get("installed", []), []
        return [], [(source, result.get("summary", "failed"))]

    installed, failures = _run_grouped_clones(
        groups,
        group_owner_repo,
        _install_item,
        max_workers=max_workers,
        notify=notify,
        label=label,
    )

    # Non-GitHub sources: install individually (rare; local paths / bare names).
    for source in other_sources:
        _notify(f"Updating {source}...")
        result = install_skill(source, dest=dest)
        if result.get("ok"):
            installed += result.get("installed", [])
        else:
            failures.append((source, result.get("summary", "failed")))

    return installed, failures


def _copy_skill_to(skill_dir: Path, dest: Path, target_name: str) -> None:
    """Copy a single resolved skill directory into ``dest/target_name``."""
    target = dest / target_name
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(
        skill_dir, target, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc")
    )


def update_npx_skills_via_git(
    *,
    max_workers: Optional[int] = None,
    notify: Optional[callable] = None,
) -> dict:
    """Refresh npx-installed skills with grouped git clones (one clone per repo).

    ``npx skills update`` reprocesses every skill individually and is the dominant
    cost of an upgrade when many skills share a few repos. This reads the npx
    ``skills-lock.json``, groups skills by their source repo, clones each repo
    once (in parallel), and copies each skill into ``NPX_SKILLS_DIR`` under its
    **existing** (lock) directory name — repo paths often differ from the
    installed name (e.g. ``skills/foo_bar`` vs ``foo-bar``).

    Returns ``{ok, synced, failed, summary}``. ``ok`` is False (with no writes)
    when git is unavailable or the lock has no usable GitHub sources, so the
    caller can fall back to ``npx skills update``.
    """
    lock_path = NPX_INSTALL_ROOT / "skills-lock.json"
    if not lock_path.exists() or not _git_available():
        return {"ok": False, "synced": 0, "failed": [], "summary": "no lock or git"}
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "synced": 0, "failed": [], "summary": f"unreadable lock: {exc}"}

    entries = lock.get("skills") or {}
    groups: dict[tuple[str, Optional[str]], list[tuple[str, Optional[str], str]]] = {}
    group_owner_repo: dict[tuple[str, Optional[str]], Optional[str]] = {}
    skipped: list[str] = []
    for name, meta in sorted(entries.items()):
        if not isinstance(meta, dict):
            continue
        source = str(meta.get("source") or "").strip()
        source_type = str(meta.get("sourceType") or "github").strip()
        skill_path = str(meta.get("skillPath") or "").strip()
        if not source or source_type != "github":
            skipped.append(name)
            continue
        # Directory holding SKILL.md within the repo.
        if skill_path.endswith("/SKILL.md"):
            subpath = skill_path[: -len("/SKILL.md")]
        elif skill_path:
            subpath = str(Path(skill_path).parent)
        else:
            subpath = None
        shorthand = f"{source}@{subpath}" if subpath else source
        try:
            url, ref, _sub = _parse_github(shorthand)
        except Exception:  # noqa: BLE001
            skipped.append(name)
            continue
        key = (url, ref)
        groups.setdefault(key, []).append((shorthand, subpath, name))
        group_owner_repo.setdefault(key, _owner_repo_from_source(shorthand))

    if not groups:
        return {"ok": False, "synced": 0, "failed": [], "summary": "no github sources in lock"}

    NPX_SKILLS_DIR.mkdir(parents=True, exist_ok=True)

    def _install_item(repo_root, commit, release_tag, via, item):
        source, subpath, target_name = item
        skill_dirs = _resolve_skill_dirs(repo_root, subpath)
        if not skill_dirs:
            return [], [(source, f"no SKILL.md at {subpath}")]
        _copy_skill_to(skill_dirs[0], NPX_SKILLS_DIR, target_name)
        return [target_name], []

    installed, failures = _run_grouped_clones(
        groups,
        group_owner_repo,
        _install_item,
        max_workers=max_workers,
        notify=notify,
        label="Updating community skills",
        # npx skills are pinned in the lock; skip the per-repo release lookup.
        fetch_release=False,
    )
    return {
        "ok": True,
        "synced": len(installed),
        "failed": failures,
        "summary": f"Updated {len(installed)} npx skill(s) via git ({len(groups)} repo clone(s)).",
    }


def upgrade_skills(
    *,
    include_catalog: bool = True,
    include_npx: bool = True,
    catalog: str = DEFAULT_CATALOG,
    project_root: Optional[Path] = None,
    progress: Optional[callable] = None,
) -> dict:
    """Re-sync installed skills to their latest versions.

    1. When ``include_catalog`` is True, installs/refreshes the entire Fastfold
       catalog (adds new skills + overrides existing ones).
    2. Re-installs every other skill recorded in the global manifest from its
       recorded source (overwrites in place).
    3. When ``include_npx`` is True and ``npx`` is available, re-runs
       ``npx skills add`` for each source recorded in the project-local
       ``skills-lock.json`` (skills the Skills CLI installed into .claude/skills).

    ``progress`` is an optional ``callable(str)`` invoked with a human-readable
    phase message (e.g. for driving an animated spinner). It is best-effort and
    never affects the result.

    Returns a dict: added (new names), updated (refreshed names), failed (list of
    (source, reason)), and a human-readable summary.
    """

    def _notify(msg: str) -> None:
        if progress is not None:
            try:
                progress(msg)
            except Exception:  # noqa: BLE001
                pass

    dest = GLOBAL_SKILLS_DIR
    if project_root is None:
        project_root = Path.cwd()
    before = set(iter_skills(project_root).keys())
    installed_total: list[str] = []
    failed: list[tuple[str, str]] = []

    # 1) Sync the whole Fastfold catalog (one clone: adds new + overrides existing).
    catalog_owner_repo = catalog.split("@", 1)[0]
    if include_catalog:
        _notify(f"Syncing catalog ({catalog_owner_repo})...")
        result = install_skill(catalog_owner_repo, dest=dest)
        if result.get("ok"):
            installed_total += result.get("installed", [])
        else:
            failed.append((catalog_owner_repo, result.get("summary", "failed")))

    # 2) Update other manifest-tracked skills from their recorded sources.
    #    Sources that share a repo+ref are cloned once and synced in parallel,
    #    so N skills from one repo cost one clone instead of N.
    manifest = _read_manifest(dest)
    tracked: list[tuple[str, str]] = []
    for name, meta in sorted(manifest.get("skills", {}).items()):
        source = (meta or {}).get("source")
        if not source:
            continue
        # Skip skills already refreshed by the catalog sync above.
        if include_catalog and source.split("@", 1)[0] == catalog_owner_repo:
            continue
        tracked.append((name, source))

    if tracked:
        grouped_installed, grouped_failed = _sync_tracked_sources(
            tracked, dest, notify=_notify, label="Updating skills"
        )
        installed_total += grouped_installed
        failed += grouped_failed

    # 3) Update npx-installed skills. Prefer grouped git clones (one clone per
    #    repo, in parallel) over `npx skills update`, which reprocesses every
    #    skill individually and dominates the runtime for large libraries.
    npx_synced = 0
    if include_npx and NPX_SKILLS_DIR.exists():
        git_result = update_npx_skills_via_git(notify=_notify)
        if git_result.get("ok"):
            npx_synced = git_result.get("synced", 0)
            failed += git_result.get("failed", [])
        elif _npx_available():
            # Fallback: git unavailable or lock unusable — use the npx CLI.
            _notify("Updating npx-installed skills...")
            result = _npx_update()
            if result.get("ok"):
                npx_synced = len(_scan_dir(NPX_SKILLS_DIR, "npx"))
            else:
                failed.append(("npx skills update", result.get("summary", "failed")))

    _notify("Finalizing...")

    after = set(iter_skills(project_root).keys())
    added = sorted(after - before)
    updated = sorted(set(installed_total) - set(added))
    summary = (
        f"Synced skills: {len(updated)} updated, {len(added)} added, "
        f"{npx_synced} npx-synced, {len(failed)} failed."
    )
    return {
        "added": added,
        "updated": updated,
        "npx_synced": npx_synced,
        "failed": failed,
        "summary": summary,
    }


def user_installed_skill_names(project_root: Optional[Path] = None) -> list[str]:
    """Return names of user-installed skills (global + project tiers; excludes bundled)."""
    if project_root is None:
        project_root = Path.cwd()
    names = set(_scan_dir(GLOBAL_SKILLS_DIR, "global").keys())
    names |= set(_scan_dir(NPX_SKILLS_DIR, "npx").keys())
    names |= set(_scan_project(project_root).keys())
    return sorted(names)


def remove_all_skills(*, project_root: Optional[Path] = None) -> dict:
    """Remove ALL user-installed skills (global install dir + project lock-gated).

    Bundled skills (shipped in the package) are never touched.
    """
    if project_root is None:
        project_root = Path.cwd()
    removed: list[str] = []

    # 1) Global install dir (~/.fastfold-cli/skills).
    if GLOBAL_SKILLS_DIR.exists():
        for child in sorted(GLOBAL_SKILLS_DIR.iterdir()):
            if child.is_dir() and (child / "SKILL.md").exists():
                try:
                    shutil.rmtree(child)
                    removed.append(child.name)
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Could not remove %s: %s", child, exc)
        _write_manifest(GLOBAL_SKILLS_DIR, {"version": 1, "skills": {}})

    # 1b) npx-installed skills (fastfold-owned ~/.fastfold-cli/.claude/skills).
    if NPX_SKILLS_DIR.exists():
        for child in sorted(NPX_SKILLS_DIR.iterdir()):
            if child.is_dir() and (child / "SKILL.md").exists():
                try:
                    shutil.rmtree(child)
                    removed.append(child.name)
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Could not remove %s: %s", child, exc)
        npx_lock = NPX_INSTALL_ROOT / "skills-lock.json"
        if npx_lock.exists():
            try:
                npx_lock.unlink()
            except Exception:  # noqa: BLE001
                pass

    # 2) Project-local lock-gated skills (npx installs under .claude/skills).
    lock_file = project_root / "skills-lock.json"
    claude_dir = project_root / ".claude" / "skills"
    if lock_file.exists() and claude_dir.exists():
        try:
            lock = json.loads(lock_file.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            lock = {"version": 1, "skills": {}}
        for name in list((lock.get("skills") or {}).keys()):
            skill_dir = claude_dir / name
            if (skill_dir / "SKILL.md").exists():
                try:
                    shutil.rmtree(skill_dir)
                    removed.append(name)
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Could not remove %s: %s", skill_dir, exc)
            lock.get("skills", {}).pop(name, None)
        try:
            lock_file.write_text(json.dumps(lock, indent=2), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            logger.debug("Could not rewrite %s: %s", lock_file, exc)

    removed = sorted(set(removed))
    _clear_skill_enabled_state(set(removed))
    return {"ok": True, "removed": removed, "summary": f"Removed {len(removed)} skill(s)."}


def remove_skill(name: str, *, dest: Optional[Path] = None) -> dict:
    """Remove a globally-installed skill by name."""
    dest = dest or GLOBAL_SKILLS_DIR
    resolved_name = name
    installed = _scan_dir(dest, "global")
    key = _resolve_skill_key(name, installed)
    if key is not None:
        resolved_name = key
    target = dest / resolved_name
    if not target.exists():
        return {"ok": False, "summary": f"Skill '{name}' is not installed in {dest}."}
    try:
        shutil.rmtree(target)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "summary": f"Could not remove '{name}': {exc}"}

    manifest = _read_manifest(dest)
    if resolved_name in manifest.get("skills", {}):
        del manifest["skills"][resolved_name]
        _write_manifest(dest, manifest)
    _clear_skill_enabled_state({resolved_name, name})
    return {"ok": True, "summary": f"Removed skill '{name}'."}


# ─── Discovery (catalog + ecosystem) ────────────────────────────────────────
def discover_skills(query: Optional[str] = None, *, catalog: str = DEFAULT_CATALOG) -> list[dict]:
    """Discover skills from the catalog repo (shallow clone) filtered by query.

    Returns dicts with: name, description, tags, install_source.
    """
    results: list[dict] = []
    if not _git_available():
        return results

    owner_repo = catalog.split("@", 1)[0]
    url = f"https://github.com/{owner_repo}.git"
    try:
        with tempfile.TemporaryDirectory(prefix="fastfold-catalog-") as tmp:
            clone_root = Path(tmp) / "catalog"
            _git_clone(url, None, clone_root)
            skills_dir = clone_root / "skills"
            base = skills_dir if skills_dir.exists() else clone_root
            for child in sorted(base.iterdir()):
                skill_md = child / "SKILL.md"
                if child.is_dir() and skill_md.exists():
                    info = parse_skill_md(skill_md)
                    results.append({
                        "name": info.name,
                        "description": info.description,
                        "tags": info.tags,
                        "install_source": f"{owner_repo}@skills/{child.name}",
                    })
    except Exception as exc:  # noqa: BLE001
        logger.debug("Catalog discovery failed: %s", exc)
        return results

    if query:
        q = query.lower()
        results = [
            r for r in results
            if q in r["name"].lower()
            or q in r["description"].lower()
            or any(q in t.lower() for t in r["tags"])
        ]
    return results


def _resolve_name_to_source(name: str, *, catalog: str = DEFAULT_CATALOG) -> Optional[str]:
    for entry in discover_skills(name, catalog=catalog):
        if entry["name"] == name:
            return entry["install_source"]
    # Loose fallback: first match.
    matches = discover_skills(name, catalog=catalog)
    return matches[0]["install_source"] if matches else None
