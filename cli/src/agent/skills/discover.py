"""Tier merging/scanning, name resolution, and ecosystem catalog discovery."""

from __future__ import annotations

import logging
import re
import subprocess
import tempfile
from pathlib import Path

from agent import skills as _skills

logger = logging.getLogger("skills")

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
# e.g. googleworkspace/cli@gws-calendar  48.9K installs
_ECO_SKILL_RE = re.compile(
    r"(?P<source>(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+)(?:@(?P<sub>[\w./-]+))?)"
    r"(?:\s+(?P<installs>[\d.]+[KkMm]?\s+installs))?"
)


# ─── Discovery / loading ───────────────────────────────────────────────────
def _scan_dir(base: Path, source: str) -> dict[str, _skills.SkillInfo]:
    out: dict[str, _skills.SkillInfo] = {}
    if not base.exists():
        return out
    manifest = _skills._read_manifest(base)
    skills_meta = manifest.get("skills", {}) if isinstance(manifest, dict) else {}
    npx_sources = _skills._npx_lock_sources() if source == "npx" else {}
    for child in sorted(base.iterdir()):
        skill_md = child / "SKILL.md"
        if child.is_dir() and skill_md.exists():
            info = _skills.parse_skill_md(skill_md)
            frontmatter_author = (info.author or "").strip()
            frontmatter_version = getattr(info, "version", None)
            frontmatter_updated = str(getattr(info, "updated_at", "") or "").strip()
            info.source = source
            meta = skills_meta.get(child.name) or {}
            if isinstance(meta, dict) and meta:
                install_source = str(meta.get("source") or "").strip()
                if install_source:
                    # Prefer the real source spec (owner/repo@path or URL) so
                    # UI links and install commands can trace origin correctly.
                    info.source = install_source
                derived = _skills._derive_author(install_source) if install_source else ""
                info.author = frontmatter_author or derived
                installed_at = str(meta.get("installed_at") or "").strip()
                if installed_at:
                    info.updated_at = installed_at
                release = meta.get("release")
                if release:
                    info.version = str(release)
                elif frontmatter_version:
                    info.version = frontmatter_version
                commit = str(meta.get("commit") or "").strip()
                info.commit = commit or None
            else:
                info.author = frontmatter_author or info.author
                info.version = frontmatter_version
                info.updated_at = frontmatter_updated
            if source == "npx" and info.source == "npx":
                lock_source = npx_sources.get(child.name) or npx_sources.get(info.name)
                if lock_source:
                    info.source = lock_source
                    info.author = frontmatter_author or _skills._derive_author(lock_source)
            if _skills.is_user_created_skill(info):
                if (info.category or "").strip().lower() in {"", "custom", "user"}:
                    info.category = _skills.USER_CREATED_CATEGORY
                if not info.author or info.author.strip().lower() in {"custom", "user"}:
                    info.author = _skills.local_skill_author_name()
            if source == "bundled":
                from agent.skills.releases import enrich_bundled_skill

                enrich_bundled_skill(info)
            # Key by directory name (canonical identifier everywhere else).
            out[child.name] = info
    return out


def _scan_project(project_root: Path) -> dict[str, _skills.SkillInfo]:
    """Scan project-local skills gated by skills-lock.json (back-compat)."""
    out: dict[str, _skills.SkillInfo] = {}
    lock_file = project_root / "skills-lock.json"
    claude_dir = project_root / ".claude" / "skills"
    if not (lock_file.exists() and claude_dir.exists()):
        return out
    lock_skills = _skills._read_skills_lock(lock_file)
    for name, meta in lock_skills.items():
        skill_md = claude_dir / name / "SKILL.md"
        if skill_md.exists():
            info = _skills.parse_skill_md(skill_md)
            info.source = "project"
            install_source = _skills._source_from_lock_meta(meta)
            if install_source:
                info.source = install_source
                info.author = _skills._derive_author(install_source)
            out[name] = info
    return out


def iter_skills(
    project_root: Path | None = None,
    *,
    enabled_only: bool = False,
) -> dict[str, _skills.SkillInfo]:
    """Return merged skills keyed by directory name.

    Priority (high → low): global > npx > project (lock-gated) > bundled.
    Entries that only differ by ``_`` vs ``-`` naming (or share the same
    SKILL.md frontmatter name) are collapsed so the UI/API list is unique.
    """
    if project_root is None:
        project_root = Path.cwd()

    merged: dict[str, _skills.SkillInfo] = {}
    merged.update(_scan_dir(_skills.BUNDLED_SKILLS_DIR, "bundled"))
    merged.update(_scan_project(project_root))
    merged.update(_scan_dir(_skills.NPX_SKILLS_DIR, "npx"))
    merged.update(_scan_dir(_skills.GLOBAL_SKILLS_DIR, "global"))
    merged = _collapse_skills_by_name(merged)
    disabled = {
        _normalize_skill_lookup(name) for name in _skills._disabled_skill_names() if name
    }
    for key, info in merged.items():
        # Directory key and frontmatter name can differ (e.g. firecrawl-cli / firecrawl).
        # Treat as disabled if either identity is listed.
        name_id = _normalize_skill_lookup(info.name)
        key_id = _normalize_skill_lookup(key)
        info.enabled = (name_id not in disabled) and (key_id not in disabled)
    if enabled_only:
        return {name: info for name, info in merged.items() if info.enabled}
    return merged


def _skill_source_tier_rank(info: _skills.SkillInfo) -> int:
    """Higher wins when collapsing duplicate skill identities."""
    path = getattr(info, "path", None)
    source = str(getattr(info, "source", "") or "")
    try:
        if path is not None:
            resolved = Path(path).resolve()
            if _skills.GLOBAL_SKILLS_DIR.resolve() in resolved.parents:
                return 4
            if _skills.NPX_SKILLS_DIR.resolve() in resolved.parents:
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


def _prefer_duplicate_skill(current: _skills.SkillInfo, candidate: _skills.SkillInfo) -> _skills.SkillInfo:
    current_rank = _skill_source_tier_rank(current)
    candidate_rank = _skill_source_tier_rank(candidate)
    if candidate_rank != current_rank:
        return candidate if candidate_rank > current_rank else current
    if bool(candidate.version) != bool(current.version):
        return candidate if candidate.version else current
    if bool(candidate.updated_at) != bool(current.updated_at):
        return candidate if candidate.updated_at else current
    return current


def _collapse_skills_by_name(
    skills: dict[str, _skills.SkillInfo],
) -> dict[str, _skills.SkillInfo]:
    """Collapse directory-key collisions that share one frontmatter skill name."""
    chosen: dict[str, tuple[str, _skills.SkillInfo]] = {}
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
    return dict(chosen.values())


def list_skills(
    project_root: Path | None = None,
    *,
    enabled_only: bool = False,
) -> list[_skills.SkillInfo]:
    return [
        s for _, s in sorted(_skills.iter_skills(project_root, enabled_only=enabled_only).items())
    ]


def _normalize_skill_lookup(value: str) -> str:
    return str(value or "").strip().lower().replace("_", "-")


def _resolve_skill_key(name: str, skills: dict[str, _skills.SkillInfo]) -> str | None:
    # Exact directory key first.
    if name in skills:
        return name

    lowered = str(name or "").strip().lower()
    for key in skills:
        if key.lower() == lowered:
            return key

    # Match SKILL.md frontmatter name (e.g. "skill-find").
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


def skill_info(name: str, project_root: Path | None = None) -> _skills.SkillInfo | None:
    skills = _skills.iter_skills(project_root)
    key = _resolve_skill_key(name, skills)
    return skills.get(key) if key is not None else None


def installed_skill_names(project_root: Path | None = None) -> list[str]:
    return sorted(_skills.iter_skills(project_root).keys())


def user_installed_skill_names(project_root: Path | None = None) -> list[str]:
    """Return names of user-installed skills (global + project tiers; excludes bundled)."""
    if project_root is None:
        project_root = Path.cwd()
    names = set(_scan_dir(_skills.GLOBAL_SKILLS_DIR, "global").keys())
    names |= set(_scan_dir(_skills.NPX_SKILLS_DIR, "npx").keys())
    names |= set(_scan_project(project_root).keys())
    return sorted(names)


# ─── Discovery (catalog + ecosystem) ────────────────────────────────────────
def discover_skills(query: str | None = None, *, catalog: str = _skills.DEFAULT_CATALOG) -> list[dict]:
    """Discover skills from the catalog repo (shallow clone) filtered by query.

    Returns dicts with: name, description, tags, install_source.
    """
    results: list[dict] = []
    if not _skills._git_available():
        return results

    owner_repo = catalog.split("@", 1)[0]
    url = f"https://github.com/{owner_repo}.git"
    try:
        with tempfile.TemporaryDirectory(prefix="fastfold-catalog-") as tmp:
            clone_root = Path(tmp) / "catalog"
            _skills._git_clone(url, None, clone_root)
            skills_dir = clone_root / "skills"
            base = skills_dir if skills_dir.exists() else clone_root
            for child in sorted(base.iterdir()):
                skill_md = child / "SKILL.md"
                if child.is_dir() and skill_md.exists():
                    info = _skills.parse_skill_md(skill_md)
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


def _resolve_name_to_source(name: str, *, catalog: str = _skills.DEFAULT_CATALOG) -> str | None:
    for entry in _skills.discover_skills(name, catalog=catalog):
        if entry["name"] == name:
            return entry["install_source"]
    # Loose fallback: first match.
    matches = _skills.discover_skills(name, catalog=catalog)
    return matches[0]["install_source"] if matches else None


def discover_ecosystem_skills(query: str) -> dict:
    """Search the public skills.sh ecosystem via ``npx -y skills find``.

    Does not use the UI's Vercel-authenticated skills.sh API. Returns
    ``{ok, summary, results}`` where each result has name/install_source.
    """
    q = (query or "").strip()
    if not q:
        return {
            "ok": False,
            "summary": "Ecosystem find requires a non-empty query.",
            "results": [],
        }
    if not _skills._npx_available():
        return {
            "ok": False,
            "summary": (
                "Node/npx is not available, so public ecosystem search is skipped. "
                "Install Node.js, browse https://skills.sh, or use the Skills UI."
            ),
            "results": [],
        }
    try:
        proc = subprocess.run(
            ["npx", "-y", "skills", "find", q],
            check=False,
            capture_output=True,
            text=True,
            timeout=90,
            stdin=subprocess.DEVNULL,
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("npx skills find failed: %s", exc)
        return {
            "ok": False,
            "summary": f"Ecosystem search failed: {exc}",
            "results": [],
        }

    text = _ANSI_RE.sub("", (proc.stdout or "") + "\n" + (proc.stderr or ""))
    results: list[dict] = []
    seen: set[str] = set()
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("└") or "skills.sh" in stripped and "http" in stripped:
            # Still try to parse install_source lines; skip pure URL-only rows.
            if "http" in stripped and "@" not in stripped:
                continue
        match = _ECO_SKILL_RE.search(stripped)
        if not match:
            continue
        install_source = match.group("source")
        if install_source in seen:
            continue
        seen.add(install_source)
        sub = match.group("sub") or ""
        name = sub.rsplit("/", 1)[-1] if sub else match.group("repo")
        results.append({
            "name": name,
            "description": "",
            "tags": [],
            "install_source": install_source,
            "installs": (match.group("installs") or "").strip(),
            "tier": "ecosystem",
        })

    if not results:
        detail = "No public ecosystem matches."
        if proc.returncode != 0:
            detail += f" (npx exit {proc.returncode})"
        return {"ok": True, "summary": detail, "results": []}
    return {
        "ok": True,
        "summary": f"Found {len(results)} public ecosystem skill(s).",
        "results": results,
    }
