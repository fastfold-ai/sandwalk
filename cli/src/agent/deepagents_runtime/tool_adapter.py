"""Adapters wrapping registry tool handlers as LangChain StructuredTools."""

from __future__ import annotations

import re
from typing import Any


def _sanitize_tool_name(name: str) -> str:
    """Produce a provider-safe tool name (``^[A-Za-z0-9_-]+``)."""
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "_", str(name or "").strip())
    return cleaned or "tool"


def _args_schema_for(model_name: str, parameters: dict | None, *, required_code: bool = False):
    """Build a pydantic args schema mirroring the MCP string-typed schema.

    Parameter names that are not valid Python identifiers are skipped (the
    model could not address them anyway); ``protected_namespaces`` is disabled
    so params like ``model`` / ``schema`` do not raise pydantic warnings.
    """
    from pydantic import ConfigDict, Field, create_model

    fields: dict[str, Any] = {}
    if required_code:
        fields["code"] = (str, Field(description="Code to execute"))
    for pname, desc in (parameters or {}).items():
        key = str(pname)
        if not key.isidentifier() or key.startswith("_") or key == "code":
            continue
        fields[key] = (str | None, Field(default=None, description=str(desc)))

    config = ConfigDict(protected_namespaces=())
    try:
        return create_model(f"{model_name}_Args", __config__=config, **fields)
    except Exception:  # noqa: BLE001 - fall back to an arg-less schema
        return create_model(f"{model_name}_Args", __config__=config)


def _make_lc_tool(*, name: str, description: str, args_schema, handler, strip_none: bool = True):
    """Wrap an async ``mcp_server`` handler as a LangChain ``StructuredTool``."""
    from langchain_core.tools import StructuredTool

    async def _coroutine(**kwargs):
        args = {
            key: value
            for key, value in kwargs.items()
            if value is not None or not strip_none
        }
        result = await handler(args)
        parts = result.get("content", []) if isinstance(result, dict) else []
        text = "\n".join(
            str(part.get("text", ""))
            for part in parts
            if isinstance(part, dict) and part.get("type") == "text"
        )
        return text or "(no output)"

    def _sync_unsupported(**_kwargs):  # pragma: no cover - deepagents runs async
        raise NotImplementedError("This tool is async-only; call via ainvoke.")

    return StructuredTool(
        name=name,
        description=description or name,
        args_schema=args_schema,
        func=_sync_unsupported,
        coroutine=_coroutine,
    )


def _make_search_tools_tool(exclude_categories: set[str], exclude_tools: set[str]):
    """Build the on-demand ``search_tools`` StructuredTool used in PTC mode."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, ConfigDict, Field

    from agent.ptc_tools import search_tools_text

    class SearchToolsArgs(BaseModel):
        model_config = ConfigDict(protected_namespaces=())
        query: str = Field(description="Keywords describing the tool you need")
        category: str | None = Field(
            default=None, description="Optional category to restrict the search"
        )
        limit: int | None = Field(default=12, description="Max results (default 12)")

    async def _coroutine(query: str, category: str | None = None, limit: int | None = 12):
        return search_tools_text(
            query,
            category=category,
            limit=int(limit or 12),
            exclude_categories=exclude_categories,
            exclude_tools=exclude_tools,
        )

    def _sync_unsupported(**_kwargs):  # pragma: no cover - deepagents runs async
        raise NotImplementedError("This tool is async-only; call via ainvoke.")

    return StructuredTool(
        name="search_tools",
        description=(
            "Search the domain-tool catalog and return exact call signatures "
            "(tools.<category>.<name>(params) -> dict) for tools matching a query. "
            "Use before calling an unfamiliar domain tool inside run_python."
        ),
        args_schema=SearchToolsArgs,
        func=_sync_unsupported,
        coroutine=_coroutine,
    )
