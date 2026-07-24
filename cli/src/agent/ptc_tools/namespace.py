"""Sandbox `tools` namespace construction for Programmatic Tool Calling."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from .common import iter_domain_tools, short_name, signature
from .search import search_tools_text


def _make_callable(tool_obj, session):
    """Wrap a registry tool as a plain callable returning its raw result dict."""

    def _call(**kwargs):
        # PTC callables bypass LangGraph interrupt_on — gate sensitive skills
        # actions here so desktop/CLI HITL still fires for install/remove.
        if tool_obj.name == "skills.manage":
            from agent.hitl.ptc_gate import apply_skills_manage_hitl

            blocked = apply_skills_manage_hitl(kwargs)
            if blocked is not None:
                return blocked
        # Mirror the native handler's injected context. Domain tools always
        # accept **kwargs, so passing these through is safe even when unused.
        return tool_obj.run(_session=session, _prior_results={}, **kwargs)

    _call.__name__ = short_name(tool_obj.name)
    params = (tool_obj.parameters or {})
    param_doc = "\n".join(f"    {k}: {v}" for k, v in params.items())
    _call.__doc__ = (
        f"{tool_obj.description}\n\nCall: {signature(tool_obj)} -> dict"
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

    for tool_obj in iter_domain_tools(
        exclude_categories=exclude_categories, exclude_tools=exclude_tools
    ):
        short = short_name(tool_obj.name)
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
