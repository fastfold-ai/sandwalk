"""Native and PTC (programmatic tool calling) domain-tool assembly."""

from __future__ import annotations

from typing import Any

from agent.deepagents_runtime.tool_adapter import (
    _args_schema_for,
    _make_lc_tool,
    _make_search_tools_tool,
    _sanitize_tool_name,
)


def make_unique_namer(used_names: set[str]):
    """Build a namer that de-dupes sanitized tool names against ``used_names``."""

    def _unique(name: str) -> str:
        candidate = _sanitize_tool_name(name)
        base = candidate
        i = 2
        while candidate in used_names:
            candidate = f"{base}_{i}"
            i += 1
        used_names.add(candidate)
        return candidate

    return _unique


def build_ptc_domain_tools(
    session,
    *,
    exclude_categories: set[str],
    exclude_tools: set[str],
    display_name_map: dict[str, str],
    used_names: set[str],
    unique_name,
) -> tuple[list[Any], Any]:
    """PTC mode: expose only search_tools (+ shell.run) as schemas."""
    from tools import EXPERIMENTAL_CATEGORIES, registry

    from agent.mcp_server import _make_tool_handler
    from agent.ptc_tools import build_tools_namespace

    tools: list[Any] = []
    ptc_excludes = set(exclude_categories) | set(EXPERIMENTAL_CATEGORIES)
    tools_namespace = build_tools_namespace(
        session, exclude_categories=ptc_excludes, exclude_tools=exclude_tools
    )

    used_names.add("search_tools")
    display_name_map["search_tools"] = "search_tools"
    tools.append(_make_search_tools_tool(ptc_excludes, set(exclude_tools)))

    # Expose shell.run as a first-class tool so skills can run scripts
    # directly (rather than wrapping every command in run_python).
    shell_obj = registry.get_tool("shell.run")
    if shell_obj is not None:
        safe_name = unique_name(shell_obj.name)
        display_name_map[safe_name] = shell_obj.name
        tools.append(
            _make_lc_tool(
                name=safe_name,
                description=shell_obj.description or shell_obj.name,
                args_schema=_args_schema_for(safe_name, shell_obj.parameters),
                handler=_make_tool_handler(shell_obj, session),
            )
        )

    return tools, tools_namespace


def build_native_domain_tools(
    session,
    *,
    exclude_categories: set[str],
    exclude_tools: set[str],
    display_name_map: dict[str, str],
    unique_name,
) -> list[Any]:
    """Native mode: expose every non-excluded registry tool as its own schema."""
    from tools import EXPERIMENTAL_CATEGORIES, registry

    from agent.mcp_server import _make_tool_handler

    tools: list[Any] = []
    for tool_obj in registry.list_tools():
        if tool_obj.category in exclude_categories:
            continue
        if tool_obj.name in exclude_tools:
            continue
        if tool_obj.category in EXPERIMENTAL_CATEGORIES:
            continue

        safe_name = unique_name(tool_obj.name)
        display_name_map[safe_name] = tool_obj.name
        description = tool_obj.description or tool_obj.name
        if getattr(tool_obj, "usage_guide", ""):
            description = f"{description}\nUSE WHEN: {tool_obj.usage_guide}"[:1024]

        tools.append(
            _make_lc_tool(
                name=safe_name,
                description=description,
                args_schema=_args_schema_for(safe_name, tool_obj.parameters),
                handler=_make_tool_handler(tool_obj, session),
            )
        )
    return tools
