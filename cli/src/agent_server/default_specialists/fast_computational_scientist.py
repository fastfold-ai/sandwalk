"""Lightweight FastFold-first default specialist, upserted once per store."""

from __future__ import annotations

from typing import Any

FAST_COMPUTATIONAL_SCIENTIST_SLUG = "fast-computational-scientist"
FAST_COMPUTATIONAL_SCIENTIST_META_KEY = "fast_computational_scientist_seeded"


def _fast_computational_scientist_spec() -> dict[str, Any]:
    from agent.tool_tiers import CORE_TOOL_NAMES

    core_tools = sorted(CORE_TOOL_NAMES)
    instructions = (
        "You are a Fast computational scientist — a lightweight FastFold-first agent.\n"
        "- Prefer FastFold featured skills for cloud jobs: `fold`, "
        "`protein_design_boltzgen`, `md_openmm_calvados`, `md_openmmdl`.\n"
        "- Use `shell.run` to execute skill scripts; use `run_python` only for "
        "small local analysis or plotting.\n"
        "- Keep tool use minimal. Do not invent skills that are not installed — "
        "tell the user to install/enable them (or use `find-skills`).\n"
        "- Do not pull in broad MCP tool surfaces; stay on FastFold workflows.\n"
    )
    return {
        "name": "Fast computational scientist",
        "slug": FAST_COMPUTATIONAL_SCIENTIST_SLUG,
        "description": (
            "Lightweight FastFold-first profile: featured fold/design/MD skills "
            "and core tools only."
        ),
        "color": "teal",
        "icon": "lightning",
        "instructions": instructions,
        "skill_names": [
            "fold",
            "protein_design_boltzgen",
            "md_openmm_calvados",
            "md_openmmdl",
            "find-skills",
        ],
        "tool_names": core_tools,
        "mcp_catalog_ids": [],
        "mcp_server_ids": [],
        "enabled": True,
    }


def ensure_fast_computational_scientist(store: Any) -> Any | None:
    """Upsert the lightweight FastFold specialist once for existing stores."""
    if store.get_meta(FAST_COMPUTATIONAL_SCIENTIST_META_KEY) == "1":
        existing = store.get_specialist_by_slug(FAST_COMPUTATIONAL_SCIENTIST_SLUG)
        return existing

    spec = _fast_computational_scientist_spec()
    existing = store.get_specialist_by_slug(FAST_COMPUTATIONAL_SCIENTIST_SLUG)
    if existing is not None:
        store.set_meta(FAST_COMPUTATIONAL_SCIENTIST_META_KEY, "1")
        return existing

    created = store.create_specialist(
        slug=str(spec["slug"]),
        name=str(spec["name"]),
        description=str(spec.get("description") or "") or None,
        instructions=str(spec.get("instructions") or "") or None,
        color=str(spec.get("color") or "teal"),
        icon=str(spec.get("icon") or "lightning"),
        skill_names=list(spec.get("skill_names") or []),
        tool_names=list(spec.get("tool_names") or []),
        mcp_server_ids=list(spec.get("mcp_server_ids") or []),
        mcp_catalog_ids=list(spec.get("mcp_catalog_ids") or []),
        enabled=bool(spec.get("enabled", True)),
    )
    store.set_meta(FAST_COMPUTATIONAL_SCIENTIST_META_KEY, "1")
    return created
