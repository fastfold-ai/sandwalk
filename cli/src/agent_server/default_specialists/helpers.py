"""Shared skill/tool/instruction builders for curated default specialists."""

from __future__ import annotations

from typing import Any

# Shared across curated defaults — discovery, diagrams, reporting.
CORE_SKILLS: list[str] = [
    "diagrams_mermaid",
    "skill-find",
    "scientific-writing",
    "slack_report",
    "automate",
    "ssh",
]


def _skills(*names: str) -> list[str]:
    """Domain skills + core, de-duplicated, stable order."""
    seen: set[str] = set()
    out: list[str] = []
    for name in [*names, *CORE_SKILLS]:
        key = name.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def _with_tools(body: str, tools: list[str]) -> str:
    """Append a built-in tools section that pairs well with skills."""
    listed = ", ".join(f"`{name}`" for name in tools)
    return (
        body.rstrip()
        + "\n\n"
        + "Built-in tools (use directly for fast lookups / analysis; prefer skills "
        + "for FastFold Cloud, Boltz API, and multi-step workflows):\n"
        + f"- Prefer: {listed}.\n"
        + "- Skills own long-running jobs and API workflows; tools own quick "
        + "compute, docking, descriptors, DepMap/Open Targets/PDB/UniProt queries, "
        + "and local analysis.\n"
        + "- If a needed skill is missing or disabled, tell the user to install or "
        + "enable it (or use `skill-find`) before continuing that path.\n"
    )


def _profile(
    *,
    name: str,
    slug: str,
    description: str,
    color: str,
    icon: str,
    instructions: str,
    skill_names: list[str],
    tools: list[str],
    mcp_catalog_ids: list[str] | None = None,
    role_label: str | None = None,
    cookbook_id: str | None = None,
    priors: str | None = None,
) -> dict[str, Any]:
    from agent.tool_tiers import CORE_TOOL_NAMES

    # Core tools (shell/skills/files/lookups) + specialist domain tools.
    tool_names = list(dict.fromkeys([*sorted(CORE_TOOL_NAMES), *tools]))
    return {
        "name": name,
        "slug": slug,
        "description": description,
        "color": color,
        "icon": icon,
        "role_label": role_label or name,
        "cookbook_id": cookbook_id or "biomed-research",
        "priors": priors
        or f"Domain specialist for {role_label or name}. Prioritize reproducible evidence and clear provenance.",
        "instructions": _with_tools(instructions, tools),
        "skill_names": skill_names,
        "preferred_tools": list(tools),
        "tool_names": tool_names,
        "mcp_catalog_ids": list(mcp_catalog_ids or []),
        "mcp_server_ids": [],
        "enabled": True,
    }
