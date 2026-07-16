"""The adaptive "Installed Agent Skills" system-prompt section (catalog + index)."""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path

from agent import skills as _skills

logger = logging.getLogger("skills")

_SKILL_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_+.-]*")
_SKILLS_PROMPT_INDEX_VERSION = 1
_SKILL_INDEX_SNIPPET_CHARS = 8_000
_SKILL_STOPWORDS = {
    # Pure grammar / filler words that appear in every sentence and carry
    # no signal when matching a user request to an installed skill.
    "a", "an", "and", "as", "at", "be", "by", "for", "from",
    "how", "i", "in", "is", "it", "me", "my", "of", "on", "or",
    "that", "the", "this", "to", "with",
}


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
    if not _skills.SKILLS_PROMPT_INDEX_CACHE.exists():
        return {"version": _SKILLS_PROMPT_INDEX_VERSION, "entries": {}}
    try:
        raw = json.loads(_skills.SKILLS_PROMPT_INDEX_CACHE.read_text(encoding="utf-8"))
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
        _skills.SKILLS_PROMPT_INDEX_CACHE.parent.mkdir(parents=True, exist_ok=True)
        tmp = _skills.SKILLS_PROMPT_INDEX_CACHE.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(_skills.SKILLS_PROMPT_INDEX_CACHE)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Could not write skills prompt index cache: %s", exc)


def _build_skill_token_index(
    skills: dict[str, _skills.SkillInfo],
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
    info: _skills.SkillInfo,
    query: str,
    *,
    query_tokens: set[str] | None = None,
    skill_tokens: set[str] | None = None,
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
    skills: dict[str, _skills.SkillInfo],
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
    info: _skills.SkillInfo,
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
    project_root: Path | None = None,
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
    skills = _skills.iter_skills(project_root, enabled_only=True)
    if not skills:
        return ""

    catalog = _build_skill_catalog(
        skills,
        max_entries=max_catalog_entries,
        description_chars=catalog_description_chars,
    )

    request = (user_request or "").strip()
    ranked: list[tuple[int, str, _skills.SkillInfo]] = []
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
