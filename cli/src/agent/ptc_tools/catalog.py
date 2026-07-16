"""Compact PTC tool catalog injected into the system prompt."""

from __future__ import annotations

from .common import iter_domain_tools, short_name


def build_tool_catalog(
    *,
    exclude_categories: set[str] | None = None,
    exclude_tools: set[str] | None = None,
) -> str:
    """Build the compact PTC tool catalog injected into the system prompt.

    Lists category counts and a names-only listing of every available domain
    tool (no per-param schemas), keeping the prompt compact instead of carrying
    the full per-tool schema cost.
    """
    names_by_cat: dict[str, list[str]] = {}
    total = 0
    for tool_obj in iter_domain_tools(
        exclude_categories=exclude_categories, exclude_tools=exclude_tools
    ):
        names_by_cat.setdefault(tool_obj.category, []).append(tool_obj.name)
        total += 1

    lines: list[str] = []
    lines.append(f"## Domain Tools - Programmatic Tool Calling (PTC) ({total} tools)\n")
    lines.append(
        "The domain tools are NOT exposed as individual tool calls. Instead, call "
        "them as Python functions inside `run_python`, via the pre-injected `tools` "
        "namespace, and process results locally - only what you `print()` returns to "
        "you. This keeps large/structured tool outputs out of your context."
    )
    lines.append(
        "\n    tools.<category>.<name>(**kwargs) -> dict   # returns the tool's raw result dict\n"
    )
    lines.append(
        "Each tool returns a dict (usually with a 'summary' key). Pass arguments as "
        "normal Python values (int/float/bool/str/list). Discover exact signatures "
        "with the `search_tools` tool, e.g. search_tools(\"kinase inhibitor admet\"). "
        "Inside code you can also call tools.search(\"...\"), tools.list(\"<category>\"), "
        "and inspect tools.categories."
    )
    lines.append(
        "\nExample:\n"
        "    res = tools.chemistry.descriptors(smiles=\"CCO\")\n"
        "    print(res.get(\"summary\"))\n"
    )
    lines.append(
        "Note: domain-tool calls run inside the sandbox timeout. For long-running "
        "or polling workflows (fold jobs, MD runs), use the relevant skill's scripts "
        "via `shell_run` instead.\n"
    )

    counts = ", ".join(f"{c} ({len(names_by_cat[c])})" for c in sorted(names_by_cat))
    lines.append(f"Categories ({len(names_by_cat)}): {counts}\n")

    lines.append("All tool names (call as tools.<category>.<name>):")
    for category in sorted(names_by_cat):
        shorts = ", ".join(short_name(n) for n in sorted(names_by_cat[category]))
        lines.append(f"- {category}: {shorts}")

    return "\n".join(lines)
