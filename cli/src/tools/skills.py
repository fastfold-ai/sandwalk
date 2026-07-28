"""
Agent-facing skill management tool.

Lets the agent discover, list, inspect, install, enable, disable, create, and
remove agent skills mid-conversation. Backs the bundled ``skill-find`` and
``skill-creator`` skills. Installing/removing third-party skills clones remote
code, so those actions are gated behind ``skills.allow_agent_install``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tools import registry


def _install_allowed(_session) -> bool:
    if _session is not None and getattr(_session, "config", None) is not None:
        return bool(_session.config.get("skills.allow_agent_install", True))
    return True


def _truthy(value: Any, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _author_for_create(_session) -> str:
    if _session is not None and getattr(_session, "config", None) is not None:
        for key in ("user.display_name", "user.name", "profile.label"):
            value = _session.config.get(key)
            if value and str(value).strip():
                return str(value).strip()
    from agent.skills.models import local_skill_author_name

    return local_skill_author_name()


def _skill_mention(name: str) -> str:
    """Slash mention that the local-web UI renders as a clickable skill chip."""
    return f"/{(name or '').strip().lstrip('/')}"


def _with_mention(result: dict, name: str) -> dict:
    mention = _skill_mention(name)
    if not mention or mention == "/":
        return result
    out = {**result, "mention": mention, "name": result.get("name") or name}
    summary = str(out.get("summary") or "")
    if mention not in summary:
        out["summary"] = f"{summary} Skill: {mention}".strip()
    return out


def _create_skill(
    *,
    name: str,
    path: str,
    author: str,
    install: bool,
    with_scripts: bool,
    _session: Any = None,
) -> dict:
    from agent import skills as skills_mod
    from skills.skill_creator.scripts import init_skill

    skill_name = (name or "").strip()
    if not skill_name:
        return {"ok": False, "summary": "create requires a skill name (kebab-case)."}

    # Session-independent drafts (not under a chat workspace).
    default_root = skills_mod.CONFIG_DIR / "skill-drafts"
    out_root = Path(path).expanduser().resolve() if path.strip() else default_root
    out_root.mkdir(parents=True, exist_ok=True)

    argv = [skill_name, "--path", str(out_root)]
    if with_scripts:
        argv.append("--with-scripts")
    if author:
        argv.extend(["--author", author])

    code = init_skill.main(argv)
    skill_dir = out_root / skill_name
    if code != 0 or not (skill_dir / "SKILL.md").exists():
        return {
            "ok": False,
            "summary": f"Failed to scaffold skill '{skill_name}' under {out_root}.",
            "path": str(skill_dir),
        }

    mention = _skill_mention(skill_name)
    result: dict[str, Any] = {
        "ok": True,
        "name": skill_name,
        "path": str(skill_dir),
        "author": author,
        "category": "Created by Me",
        "summary": (
            f"Created skill draft at {skill_dir}. "
            "This draft is not installed or available yet."
        ),
        "skills_updated": False,
        "installed": False,
        "installation_verified": False,
        "available": False,
    }
    if not install:
        result["summary"] += (
            " Finish authoring it, then call skills.manage(action='install', "
            "source=<this path>) and verify with action='info'."
        )
        return result

    if not _install_allowed(_session):
        result["summary"] += (
            " Scaffold ready, but agent install is disabled — "
            "run `sandwalk skills add` or enable skills.allow_agent_install."
        )
        result["blocked"] = True
        return result

    installed = skills_mod.install_skill(
        str(skill_dir),
        manifest_source="custom",
    )
    result["install"] = installed
    result["ok"] = bool(installed.get("ok"))
    if result["ok"]:
        verified = skills_mod.skill_info(skill_name)
        if verified is None:
            result["ok"] = False
            result["summary"] = (
                f"Created scaffold at {skill_dir}, and the installer reported "
                "success, but the installed registry could not verify it. "
                "Do not claim this skill is available."
            )
            return result
        result["skills_updated"] = True
        result["mention"] = mention
        result["installed_path"] = str(skills_mod.GLOBAL_SKILLS_DIR / skill_name)
        result["installed"] = True
        result["installation_verified"] = True
        result["available"] = bool(verified.enabled)
        result["summary"] = (
            f"Created and installed {mention} (author: {author}, category: Created by Me) "
            f"to {skills_mod.GLOBAL_SKILLS_DIR}. "
            "Available on the next user message and in the CLI. "
            f"Always include {mention} in your reply so the user can open skill details."
        )
        result["enabled"] = True
    else:
        result["summary"] = (
            f"Created scaffold at {skill_dir}, but install failed: "
            f"{installed.get('summary', 'unknown error')}"
        )
    return result


@registry.register(
    name="skills.manage",
    description=(
        "Discover, list, inspect, create, install, enable, disable, or remove agent skills. "
        "Actions: find, list, info, create, install, remove, enable, disable. "
        "Find searches the Fastfold catalog then the public skills.sh ecosystem via npx. "
        "Install accepts GitHub URL/shorthand, local skill dir, or local .zip/.skill."
    ),
    category="skills",
    parameters={
        "action": (
            "One of: find, list, info, create, install, remove, enable, disable"
        ),
        "source": "For install: GitHub URL, owner/repo@subpath, local path/zip, or catalog name",
        "name": "For info/remove/enable/disable/create: the skill name (kebab-case)",
        "query": "For find: search query",
        "path": "For create: output directory (default: ~/.sandwalk/skill-drafts)",
        "author": "For create: author label (default: local user name)",
        "install": "For create: also install immediately (default false; author the draft first)",
        "with_scripts": "For create: also create a scripts/ folder (default false)",
    },
    usage_guide=(
        "Use when the user wants to find, craft, add, enable, disable, or remove agent skills. "
        "install/remove (and create with install=true) pause for human approval in the "
        "desktop UI or interactive CLI before running — do not ask the user to confirm in chat "
        "as a substitute for that gate. "
        "For authored skills: create with install=false, finish the draft, then install its "
        "returned path and verify with info. Never call a draft available unless the install "
        "result has installation_verified=true and info succeeds. "
        "Newly installed/enabled skills are usable on the next user message and in the CLI. "
        "After create/install/enable/disable/remove, always include the skill slash mention "
        "(e.g. /lab-notes) in your user-facing reply so the UI can link to skill details. "
        "install/remove also require skills.allow_agent_install (on by default) as a hard kill-switch."
    ),
)
def manage(
    action: str = "list",
    source: str = "",
    name: str = "",
    query: str = "",
    path: str = "",
    author: str = "",
    install: Any = False,
    with_scripts: Any = False,
    _session: Any = None,
    _prior_results: Any = None,
    **kwargs,
) -> dict:
    """Manage agent skills (full lifecycle)."""
    from agent import skills as skills_mod

    act = (action or "list").strip().lower()

    if act in ("find", "search", "discover"):
        q = (query or source or name or "").strip()
        catalog = skills_mod.discover_skills(q or None)
        ecosystem: list[dict] = []
        notes: list[str] = []
        if q:
            eco = skills_mod.discover_ecosystem_skills(q)
            if eco.get("ok"):
                ecosystem = list(eco.get("results") or [])
            else:
                notes.append(str(eco.get("summary") or "Ecosystem search unavailable."))
        elif not catalog:
            notes.append(
                "Pass query= to also search the public skills.sh ecosystem via npx."
            )

        lines: list[str] = []
        if catalog:
            lines.append("Fastfold catalog:")
            lines.extend(
                f"- {r['name']} ({r['install_source']}): {r['description']}" for r in catalog
            )
        if ecosystem:
            lines.append("Public ecosystem (skills.sh / npx):")
            lines.extend(
                f"- {r['name']} ({r['install_source']}): {r.get('description') or r.get('installs') or ''}"
                for r in ecosystem
            )
        if not lines:
            summary = "No matching skills found."
            if notes:
                summary += " " + " ".join(notes)
            return {
                "ok": True,
                "summary": summary,
                "results": [],
                "catalog": [],
                "ecosystem": [],
            }
        summary = f"Found {len(catalog) + len(ecosystem)} skill(s):\n" + "\n".join(lines)
        if notes:
            summary += "\n" + "\n".join(notes)
        return {
            "ok": True,
            "summary": summary,
            "results": catalog + ecosystem,
            "catalog": catalog,
            "ecosystem": ecosystem,
        }

    if act == "list":
        installed = skills_mod.list_skills()
        lines = [
            f"- {s.name} [{s.source}] "
            f"{'enabled' if s.enabled else 'disabled'} "
            f"(author: {skills_mod.display_author(s)}): {s.description}"
            for s in installed
        ]
        return {
            "ok": True,
            "summary": (
                f"{len(installed)} skill(s) installed:\n" + "\n".join(lines)
            )
            if installed
            else "No skills installed.",
            "skills": [
                {
                    "name": s.name,
                    "source": s.source,
                    "enabled": s.enabled,
                    "author": skills_mod.display_author(s),
                    "description": s.description,
                }
                for s in installed
            ],
        }

    if act == "info":
        target = (name or source).strip()
        info = skills_mod.skill_info(target)
        if not info:
            return {"ok": False, "summary": f"Skill '{target}' is not installed.", "name": target}
        mention = _skill_mention(info.name)
        return {
            "ok": True,
            "summary": (
                f"{mention} [{info.source}] "
                f"{'enabled' if info.enabled else 'disabled'} "
                f"(author: {skills_mod.display_author(info)}): {info.description}"
            ),
            "name": info.name,
            "mention": mention,
            "description": info.description,
            "tags": info.tags,
            "source": info.source,
            "author": skills_mod.display_author(info),
            "enabled": info.enabled,
            "path": str(info.path) if info.path else None,
            "installed": True,
            "installation_verified": True,
            "available": bool(info.enabled),
        }

    if act == "create":
        return _create_skill(
            name=(name or source).strip(),
            path=path.strip(),
            author=(author or _author_for_create(_session)).strip(),
            install=_truthy(install, default=False),
            with_scripts=_truthy(with_scripts, default=False),
            _session=_session,
        )

    if act in ("install", "add"):
        if not _install_allowed(_session):
            return {
                "summary": (
                    "Skill install is disabled for the agent (installs third-party code). "
                    "Ask the user to run `sandwalk skills add <source>` or `/skills-add <source>`, "
                    "or enable it with `sandwalk config set skills.allow_agent_install true`."
                ),
                "ok": False,
                "blocked": True,
            }
        src = (source or name).strip()
        # Local custom/draft installs record as "custom" so the UI does not
        # pin a disposable session workspace path as the source.
        manifest_source = None
        try:
            local = Path(src).expanduser().resolve()
            drafts = (skills_mod.CONFIG_DIR / "skill-drafts").resolve()
            if local.exists() and (
                drafts == local or drafts in local.parents
            ):
                manifest_source = "custom"
        except Exception:  # noqa: BLE001
            manifest_source = None
        result = skills_mod.install_skill(src, manifest_source=manifest_source)
        if isinstance(result, dict) and result.get("ok"):
            installed_names = result.get("installed") or []
            label = installed_names[0] if installed_names else Path(src).name
            verified = [
                skills_mod.skill_info(str(installed_name))
                for installed_name in installed_names
            ]
            if not installed_names or any(info is None for info in verified):
                return {
                    **result,
                    "ok": False,
                    "skills_updated": False,
                    "installed": False,
                    "installation_verified": False,
                    "available": False,
                    "summary": (
                        f"{result.get('summary', 'Installer completed.')} "
                        "Sandwalk could not verify the skill in the installed "
                        "registry. Do not claim it is available."
                    ),
                }
            result = _with_mention(
                {
                    **result,
                    "skills_updated": True,
                    "installed": True,
                    "installation_verified": True,
                    "available": all(bool(info and info.enabled) for info in verified),
                },
                str(label),
            )
            result["summary"] = (
                f"{result['summary']} "
                f"Always include {result['mention']} in your reply so the user "
                "can open skill details. Usable on the next user message and in the CLI."
            )
        return result

    if act in ("remove", "uninstall"):
        if not _install_allowed(_session):
            return {
                "summary": (
                    "Skill removal is disabled for the agent. Ask the user to run "
                    "`sandwalk skills remove <name>` or `/skills-remove <name>`."
                ),
                "ok": False,
                "blocked": True,
            }
        target = (name or source).strip()
        result = skills_mod.remove_skill(target)
        if isinstance(result, dict) and result.get("ok"):
            result = _with_mention({**result, "skills_updated": True}, target)
        return result

    if act == "enable":
        target = (name or source).strip()
        result = skills_mod.set_skill_enabled(target, True)
        if isinstance(result, dict) and result.get("ok"):
            result = _with_mention(
                {**result, "enabled": True, "skills_updated": True},
                target,
            )
        return result

    if act == "disable":
        target = (name or source).strip()
        result = skills_mod.set_skill_enabled(target, False)
        if isinstance(result, dict) and result.get("ok"):
            result = _with_mention(
                {**result, "enabled": False, "skills_updated": True},
                target,
            )
        return result

    return {
        "ok": False,
        "summary": (
            f"Unknown action '{action}'. Use find, list, info, create, "
            "install, remove, enable, or disable."
        ),
    }
