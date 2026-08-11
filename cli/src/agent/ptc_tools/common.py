"""Shared helpers for PTC: registry iteration and signature formatting."""

from __future__ import annotations


def short_name(dotted: str) -> str:
    """Return the part of a dotted tool name after the ``category.`` prefix."""
    return dotted.split(".", 1)[1] if "." in dotted else dotted


def iter_domain_tools(
    *,
    exclude_categories: set[str] | None = None,
    exclude_tools: set[str] | None = None,
):
    """Yield registry tools, applying the same exclusions as the native path."""
    from tools import EXPERIMENTAL_CATEGORIES, ensure_loaded, registry

    ensure_loaded()
    exclude_categories = exclude_categories or set()
    exclude_tools = exclude_tools or set()

    for tool_obj in registry.list_tools():
        if tool_obj.category in exclude_categories:
            continue
        if tool_obj.category in EXPERIMENTAL_CATEGORIES:
            continue
        if tool_obj.name in exclude_tools:
            continue
        yield tool_obj


def signature(tool_obj) -> str:
    """Compact call signature like ``tools.chemistry.descriptors(smiles, ph)``."""
    params = ", ".join((tool_obj.parameters or {}).keys())
    return f"tools.{tool_obj.category}.{short_name(tool_obj.name)}({params})"
