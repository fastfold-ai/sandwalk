"""Enable/disable state tracking and uninstalling skills."""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

from agent import skills as _skills

logger = logging.getLogger("skills")


def _skill_state_path() -> Path:
    return _skills.CONFIG_DIR / _skills.SKILL_STATE_FILENAME


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
    state = _skills._read_skill_state()
    return {name for name in state.get("disabled", []) if isinstance(name, str)}


def _set_disabled_skill_names(names: set[str]) -> None:
    _skills._write_skill_state(
        {
            "version": 1,
            "disabled": sorted(name for name in names if name.strip()),
        }
    )


def set_skill_enabled(
    name: str,
    enabled: bool,
    *,
    project_root: Path | None = None,
) -> dict:
    skills = _skills.iter_skills(project_root)
    key = _skills._resolve_skill_key(name, skills)
    if key is None:
        return {"ok": False, "summary": f"Skill '{name}' is not installed."}
    info = skills[key]
    display_name = str(getattr(info, "name", "") or key)
    disabled = _disabled_skill_names()
    # Persist both directory key and frontmatter name — they often differ
    # (e.g. dir ``firecrawl-cli``, name ``firecrawl``).
    aliases = {key, display_name}
    targets = {
        _skills._normalize_skill_lookup(key),
        _skills._normalize_skill_lookup(display_name),
    }
    targets.discard("")
    for candidate_key, candidate in skills.items():
        candidate_ids = {
            _skills._normalize_skill_lookup(candidate_key),
            _skills._normalize_skill_lookup(getattr(candidate, "name", "")),
        }
        candidate_ids.discard("")
        if candidate_ids & targets:
            aliases.add(candidate_key)
            cand_name = str(getattr(candidate, "name", "") or "").strip()
            if cand_name:
                aliases.add(cand_name)
    if enabled:
        disabled -= aliases
    else:
        disabled |= aliases
    _set_disabled_skill_names(disabled)
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


def remove_all_skills(*, project_root: Path | None = None) -> dict:
    """Remove ALL user-installed skills (global install dir + project lock-gated).

    Bundled skills (shipped in the package) are never touched.
    """
    if project_root is None:
        project_root = Path.cwd()
    removed: list[str] = []

    global_dir = _skills.GLOBAL_SKILLS_DIR
    npx_dir = _skills.NPX_SKILLS_DIR
    npx_root = _skills.NPX_INSTALL_ROOT

    # 1) Global install dir (~/.sandwalk/skills).
    if global_dir.exists():
        for child in sorted(global_dir.iterdir()):
            if child.is_dir() and (child / "SKILL.md").exists():
                try:
                    shutil.rmtree(child)
                    removed.append(child.name)
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Could not remove %s: %s", child, exc)
        _skills._write_manifest(global_dir, {"version": 1, "skills": {}})

    # 1b) npx-installed skills (fastfold-owned ~/.sandwalk/.claude/skills).
    if npx_dir.exists():
        for child in sorted(npx_dir.iterdir()):
            if child.is_dir() and (child / "SKILL.md").exists():
                try:
                    shutil.rmtree(child)
                    removed.append(child.name)
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Could not remove %s: %s", child, exc)
        npx_lock = npx_root / "skills-lock.json"
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


def remove_skill(name: str, *, dest: Path | None = None) -> dict:
    """Remove a globally-installed skill by name."""
    dest = dest or _skills.GLOBAL_SKILLS_DIR
    resolved_name = name
    installed = _skills._scan_dir(dest, "global")
    key = _skills._resolve_skill_key(name, installed)
    if key is not None:
        resolved_name = key
    target = dest / resolved_name
    if not target.exists():
        return {"ok": False, "summary": f"Skill '{name}' is not installed in {dest}."}
    try:
        shutil.rmtree(target)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "summary": f"Could not remove '{name}': {exc}"}

    manifest = _skills._read_manifest(dest)
    if resolved_name in manifest.get("skills", {}):
        del manifest["skills"][resolved_name]
        _skills._write_manifest(dest, manifest)
    _clear_skill_enabled_state({resolved_name, name})
    return {"ok": True, "summary": f"Removed skill '{name}'."}
