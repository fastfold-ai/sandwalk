"""Build the full LangChain tool list for the deepagents graph from the ct registry."""

from __future__ import annotations

from typing import Any

from agent.deepagents_runtime.chat_model import (
    _cap_tools_for_openai,
    provider_needs_openai_tool_cap,
)
from agent.deepagents_runtime.langchain_tools_sandbox import attach_sandbox_tools
from agent.deepagents_runtime.langchain_tools_setup import (
    build_native_domain_tools,
    build_ptc_domain_tools,
    make_unique_namer,
)


def create_ct_langchain_tools(
    session,
    *,
    exclude_categories: set[str] | None = None,
    exclude_tools: set[str] | None = None,
    include_run_python: bool = True,
    provider: str = "anthropic",
    tool_mode: str = "native",
    session_id: str | None = None,
) -> tuple[list, Any, list[dict], dict[str, str]]:
    """Build LangChain tools for the deepagents graph from the ct registry.

    ``tool_mode`` selects the strategy:

    - ``"native"`` (default): every domain tool is exposed as its own
      ``StructuredTool`` schema.
    - ``"ptc"``: Programmatic Tool Calling. Domain tools are injected as Python
      callables into the run_python sandbox (the model calls them in code), so
      only ``run_python``/``run_r``/``shell_run``/``search_tools`` are exposed as
      tool schemas. This sharply reduces per-call input tokens and removes the
      OpenAI tool-count ceiling.

    Returns ``(tools, sandbox, code_trace_buffer, display_name_map)`` where
    ``display_name_map`` maps the sanitized (provider-safe) tool name back to
    the original dotted name for trace rendering.
    """
    from tools import ensure_loaded

    ensure_loaded()
    exclude_categories = exclude_categories or set()
    exclude_tools = exclude_tools or set()
    code_trace_buffer: list[dict] = []

    display_name_map: dict[str, str] = {}
    used_names: set[str] = set()
    unique_name = make_unique_namer(used_names)

    ptc = str(tool_mode).strip().lower() == "ptc"
    tools_namespace = None

    if ptc:
        tools, tools_namespace = build_ptc_domain_tools(
            session,
            exclude_categories=exclude_categories,
            exclude_tools=exclude_tools,
            display_name_map=display_name_map,
            used_names=used_names,
            unique_name=unique_name,
        )
    else:
        tools = build_native_domain_tools(
            session,
            exclude_categories=exclude_categories,
            exclude_tools=exclude_tools,
            display_name_map=display_name_map,
            unique_name=unique_name,
        )

    sandbox = None
    if include_run_python:
        sandbox = attach_sandbox_tools(
            tools,
            session,
            code_trace_buffer=code_trace_buffer,
            tools_namespace=tools_namespace,
            session_id=session_id,
            display_name_map=display_name_map,
            used_names=used_names,
            ptc=ptc,
        )

    # Soft-cap native fan-out early so traces stay small; runner still applies
    # ``finalize_tools_for_provider`` after MCP tools are merged (Neurosnap
    # alone can exceed OpenAI's 128-tool limit).
    if not ptc and provider_needs_openai_tool_cap(provider):
        tools = _cap_tools_for_openai(tools)

    return tools, sandbox, code_trace_buffer, display_name_map
