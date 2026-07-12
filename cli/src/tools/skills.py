"""
Agent-facing skill management tool.

Lets the agent discover, list, inspect, install, and remove agent skills
mid-conversation. Backs the bundled ``find-skills`` and ``skill-creator``
skills. Installing/removing third-party skills clones remote code, so those
actions are gated behind the ``skills.allow_agent_install`` config flag.
"""

from __future__ import annotations

from typing import Any

from tools import registry


def _install_allowed(_session) -> bool:
    if _session is not None and getattr(_session, "config", None) is not None:
        return bool(_session.config.get("skills.allow_agent_install", False))
    return False


@registry.register(
    name="skills.manage",
    description=(
        "Discover, list, inspect, install, or remove agent skills. "
        "Actions: find (search the catalog), list (installed skills), info, "
        "install (from GitHub url/owner-repo@path/local path/name), remove."
    ),
    category="skills",
    parameters={
        "action": "One of: find, list, info, install, remove",
        "source": "For install: GitHub URL, owner/repo@subpath, local path, or catalog name",
        "name": "For info/remove: the skill name",
        "query": "For find: optional search query",
    },
    usage_guide=(
        "Use when the user wants to find, add, inspect, or remove agent skills. "
        "install/remove require the user to have enabled skills.allow_agent_install; "
        "if disabled, instruct the user to run `fastfold skill add <source>` or `/skills-add`."
    ),
)
def manage(
    action: str = "list",
    source: str = "",
    name: str = "",
    query: str = "",
    _session: Any = None,
    _prior_results: Any = None,
    **kwargs,
) -> dict:
    """Manage agent skills (find/list/info/install/remove)."""
    from agent import skills as skills_mod

    act = (action or "list").strip().lower()

    if act in ("find", "search", "discover"):
        results = skills_mod.discover_skills((query or source or "").strip() or None)
        if not results:
            return {
                "summary": "No matching skills found in the catalog (requires git + network).",
                "results": [],
            }
        lines = [f"- {r['name']} ({r['install_source']}): {r['description']}" for r in results]
        return {
            "summary": f"Found {len(results)} skill(s):\n" + "\n".join(lines),
            "results": results,
        }

    if act == "list":
        installed = skills_mod.list_skills()
        lines = [f"- {s.name} [{s.source}]: {s.description}" for s in installed]
        return {
            "summary": (f"{len(installed)} skill(s) installed:\n" + "\n".join(lines)) if installed else "No skills installed.",
            "skills": [s.name for s in installed],
        }

    if act == "info":
        info = skills_mod.skill_info(name or source)
        if not info:
            return {"summary": f"Skill '{name or source}' is not installed."}
        return {
            "summary": f"{info.name} [{info.source}]: {info.description}",
            "name": info.name,
            "description": info.description,
            "tags": info.tags,
            "source": info.source,
            "path": str(info.path) if info.path else None,
        }

    if act in ("install", "add"):
        if not _install_allowed(_session):
            return {
                "summary": (
                    "Skill install is disabled for the agent (installs third-party code). "
                    "Ask the user to run `fastfold skills add <source>` or `/skills-add <source>`, "
                    "or enable it with `fastfold config set skills.allow_agent_install true`."
                ),
                "ok": False,
                "blocked": True,
            }
        result = skills_mod.install_skill((source or name).strip())
        return result

    if act in ("remove", "uninstall"):
        if not _install_allowed(_session):
            return {
                "summary": (
                    "Skill removal is disabled for the agent. Ask the user to run "
                    "`fastfold skills remove <name>` or `/skills-remove <name>`."
                ),
                "ok": False,
                "blocked": True,
            }
        return skills_mod.remove_skill((name or source).strip())

    return {"summary": f"Unknown action '{action}'. Use find, list, info, install, or remove."}
