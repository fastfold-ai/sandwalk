"""
Programmatic Tool Calling (PTC) support for the deepagents runtime.

Instead of exposing every domain tool as its own LangChain tool schema (which
adds a large, fixed input-token cost for ~190 tools on every model call), PTC
injects the domain tools as plain Python callables inside the persistent
``run_python`` sandbox. The model invokes them in code:

    res = tools.chemistry.descriptors(smiles="CCO")
    df = pd.DataFrame(res["table"])
    print(df.describe())          # only this returns to the model

This is the "code execution with MCP" / Programmatic Tool Calling pattern
(Anthropic; open-ptc-agent; CodeAct). The model only ever sees:

- a compact catalog (category counts + names-only listing) in the system prompt
  (built by :func:`build_tool_catalog`), and
- an on-demand ``search_tools`` tool (text from :func:`search_tools_text`) that
  returns exact signatures when asked.

The tools namespace itself is built by :func:`build_tools_namespace` and bound
into the sandbox via :meth:`agent.sandbox.Sandbox.inject_tools`.
"""

from __future__ import annotations

import re
from types import SimpleNamespace
from typing import Any


def _short_name(dotted: str) -> str:
    """Return the part of a dotted tool name after the ``category.`` prefix."""
    return dotted.split(".", 1)[1] if "." in dotted else dotted


def _iter_domain_tools(
    *,
    exclude_categories: set[str] | None = None,
    exclude_tools: set[str] | None = None,
):
    """Yield registry tools, applying the same exclusions as the native path."""
    from tools import registry, ensure_loaded, EXPERIMENTAL_CATEGORIES

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


def _signature(tool_obj) -> str:
    """Compact call signature like ``tools.chemistry.descriptors(smiles, ph)``."""
    params = ", ".join((tool_obj.parameters or {}).keys())
    return f"tools.{tool_obj.category}.{_short_name(tool_obj.name)}({params})"


# ---------------------------------------------------------------------------
# Sandbox namespace
# ---------------------------------------------------------------------------

def _make_callable(tool_obj, session):
    """Wrap a registry tool as a plain callable returning its raw result dict."""

    def _call(**kwargs):
        # Mirror the native handler's injected context. Domain tools always
        # accept **kwargs, so passing these through is safe even when unused.
        return tool_obj.run(_session=session, _prior_results={}, **kwargs)

    _call.__name__ = _short_name(tool_obj.name)
    params = (tool_obj.parameters or {})
    param_doc = "\n".join(f"    {k}: {v}" for k, v in params.items())
    _call.__doc__ = (
        f"{tool_obj.description}\n\nCall: {_signature(tool_obj)} -> dict"
        + (f"\nParameters:\n{param_doc}" if param_doc else "")
    )
    return _call


def build_tools_namespace(
    session,
    *,
    exclude_categories: set[str] | None = None,
    exclude_tools: set[str] | None = None,
) -> SimpleNamespace:
    """Build the ``tools`` namespace injected into the run_python sandbox.

    Returns a :class:`types.SimpleNamespace` where ``tools.<category>`` is a
    sub-namespace of callables keyed by the tool's short name, plus a few
    discovery helpers: ``tools.search(query)``, ``tools.list(category=None)``,
    and ``tools.categories`` (``{category: count}``).
    """
    cats: dict[str, dict[str, Any]] = {}
    names_by_cat: dict[str, list[str]] = {}

    for tool_obj in _iter_domain_tools(
        exclude_categories=exclude_categories, exclude_tools=exclude_tools
    ):
        short = _short_name(tool_obj.name)
        cats.setdefault(tool_obj.category, {})[short] = _make_callable(tool_obj, session)
        names_by_cat.setdefault(tool_obj.category, []).append(tool_obj.name)

    root = SimpleNamespace()
    for category, members in cats.items():
        setattr(root, category, SimpleNamespace(**members))

    root.categories = {c: len(v) for c, v in sorted(names_by_cat.items())}

    def _list(category: str | None = None) -> list[str]:
        if category:
            return sorted(names_by_cat.get(category, []))
        return sorted(n for names in names_by_cat.values() for n in names)

    def _search(query: str, category: str | None = None, limit: int = 12) -> str:
        return search_tools_text(
            query,
            category=category,
            limit=limit,
            exclude_categories=exclude_categories,
            exclude_tools=exclude_tools,
        )

    root.list = _list
    root.search = _search
    return root


# ---------------------------------------------------------------------------
# Compact prompt catalog
# ---------------------------------------------------------------------------

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
    for tool_obj in _iter_domain_tools(
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
        shorts = ", ".join(_short_name(n) for n in sorted(names_by_cat[category]))
        lines.append(f"- {category}: {shorts}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# On-demand signature search
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", str(text).lower()) if t]


def search_tools_text(
    query: str,
    *,
    category: str | None = None,
    limit: int = 12,
    exclude_categories: set[str] | None = None,
    exclude_tools: set[str] | None = None,
) -> str:
    """Return compact signatures for domain tools matching ``query``.

    Scores tools by token overlap against name + description + parameter
    names/descriptions. Used by the ``search_tools`` tool and ``tools.search``.
    """
    query = (query or "").strip()
    tokens = _tokenize(query)

    scored: list[tuple[int, Any]] = []
    for tool_obj in _iter_domain_tools(
        exclude_categories=exclude_categories, exclude_tools=exclude_tools
    ):
        if category and tool_obj.category != category:
            continue
        haystack = " ".join(
            [
                tool_obj.name,
                tool_obj.description or "",
                getattr(tool_obj, "usage_guide", "") or "",
                " ".join((tool_obj.parameters or {}).keys()),
                " ".join(str(v) for v in (tool_obj.parameters or {}).values()),
            ]
        ).lower()

        if not tokens:
            score = 1
        else:
            score = 0
            for tok in tokens:
                if tok in haystack:
                    score += 1
                if tok in tool_obj.name.lower():
                    score += 2  # weight name matches
            if score == 0:
                continue
        scored.append((score, tool_obj))

    scored.sort(key=lambda pair: (-pair[0], pair[1].name))
    top = scored[:limit]

    if not top:
        return f"No domain tools matched '{query}'. Try tools.list() or a broader query."

    lines = [f"Matches for '{query}' (showing {len(top)} of {len(scored)}):"]
    for _score, tool_obj in top:
        desc = (tool_obj.description or "").strip().replace("\n", " ")
        if len(desc) > 160:
            desc = desc[:157] + "..."
        lines.append(f"- {_signature(tool_obj)} -> dict")
        if desc:
            lines.append(f"    {desc}")
    return "\n".join(lines)
