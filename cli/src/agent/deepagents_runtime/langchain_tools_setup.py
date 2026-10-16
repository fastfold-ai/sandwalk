"""Native and PTC (programmatic tool calling) domain-tool assembly."""

from __future__ import annotations

import threading
from typing import Any

from agent.deepagents_runtime.tool_adapter import (
    _args_schema_for,
    _make_lc_tool,
    _make_search_tools_tool,
    _sanitize_tool_name,
)

_NATIVE_TOOLS_LOCK = threading.Lock()
_NATIVE_TOOLS_CACHE: dict[tuple, tuple[list[Any], dict[str, str]]] = {}

# Registry tools that stay first-class in PTC mode instead of living only
# inside the `tools.*` namespace. They act on the host, not on science data.
PTC_DIRECT_TOOLS: tuple[str, ...] = (
    "shell.run",
    "environment.install_package",
    "environment.list_packages",
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
    from agent.mcp_server import _make_tool_handler
    from agent.ptc_tools import build_tools_namespace
    from tools import EXPERIMENTAL_CATEGORIES, registry

    tools: list[Any] = []
    ptc_excludes = set(exclude_categories) | set(EXPERIMENTAL_CATEGORIES)
    tools_namespace = build_tools_namespace(
        session, exclude_categories=ptc_excludes, exclude_tools=exclude_tools
    )

    used_names.add("search_tools")
    display_name_map["search_tools"] = "search_tools"
    tools.append(_make_search_tools_tool(ptc_excludes, set(exclude_tools)))

    # Expose shell.run as a first-class tool so skills can run scripts
    # directly (rather than wrapping every command in run_python). The
    # environment tools ride along: a missing import is fixed by a direct
    # call, not by hunting for pip inside the sandbox.
    for name in PTC_DIRECT_TOOLS:
        if name in exclude_tools:
            continue
        tool_obj = registry.get_tool(name)
        if tool_obj is None:
            continue
        safe_name = unique_name(tool_obj.name)
        display_name_map[safe_name] = tool_obj.name
        tools.append(
            _make_lc_tool(
                name=safe_name,
                description=tool_obj.description or tool_obj.name,
                args_schema=_args_schema_for(safe_name, tool_obj.parameters),
                handler=_make_tool_handler(tool_obj, session),
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
    used_names: set[str],
) -> list[Any]:
    """Native mode: expose every non-excluded registry tool as its own schema."""
    cache_key = (frozenset(exclude_categories), frozenset(exclude_tools))
    with _NATIVE_TOOLS_LOCK:
        cached = _NATIVE_TOOLS_CACHE.get(cache_key)
        if cached is not None:
            tools, names = cached
            display_name_map.update(names)
            used_names.update(names)
            return list(tools)

        from agent.mcp_server import _make_tool_handler
        from tools import EXPERIMENTAL_CATEGORIES, registry

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
        _NATIVE_TOOLS_CACHE[cache_key] = (list(tools), dict(display_name_map))
        return tools
