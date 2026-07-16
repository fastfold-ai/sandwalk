"""
Deep-agent (LangGraph) runtime backend for the Fastfold Agent CLI.

This is the model-agnostic alternative to the Claude Agent SDK path in
``runner.py``. It builds a :func:`deepagents.create_deep_agent` graph that:

- exposes the same 192 domain tools (wrapped as LangChain ``StructuredTool``
  objects around the existing ``mcp_server`` handlers),
- keeps the persistent ``run_python`` / ``run_r`` sandbox tools,
- loads installed skills natively via deepagents progressive disclosure
  (``skills=[...]``) so the system prompt stays compact for every provider, and
- is driven by a single model created through ``init_chat_model`` so Anthropic
  and OpenAI-compatible providers share one agentic loop.

The event consumer (:func:`process_events`) translates LangGraph
``astream_events`` into the ``trace_events`` schema, ``on_activity`` progress
callbacks, and result contract the UI, usage accounting, and export layers
expect.

Split into sibling modules to stay under the file-length cap: ``chat_model*``
(model factory), ``skills_*`` / ``prompt_budget`` (skills + prompt budgeting),
``mcp_tools`` (external MCP), ``tool_adapter`` / ``langchain_tools*`` (registry
-> LangChain tool adapter), and ``event_text`` / ``event_processor`` (the
``astream_events`` consumer).
"""

from __future__ import annotations

import logging

from agent.deepagents_runtime.chat_model import (
    OPENAI_TOOL_BUDGET,
    _cap_tools_for_openai,
    build_chat_model,
    finalize_tools_for_provider,
    provider_needs_openai_tool_cap,
)
from agent.deepagents_runtime.event_processor import process_events
from agent.deepagents_runtime.event_text import (
    _text_from_content,
    _tool_output_text,
    _usage_from_message,
)
from agent.deepagents_runtime.langchain_tools import create_ct_langchain_tools
from agent.deepagents_runtime.mcp_tools import create_external_mcp_tools
from agent.deepagents_runtime.prompt_budget import measure_deepagents_builtin_tool_schemas
from agent.deepagents_runtime.skills_index import build_skills_index_text
from agent.deepagents_runtime.skills_sources import (
    resolve_skill_source_dirs,
    skill_source_dirs,
    skill_source_dirs_for_names,
)
from agent.deepagents_runtime.tool_adapter import (
    _args_schema_for,
    _make_lc_tool,
    _make_search_tools_tool,
    _sanitize_tool_name,
)

logger = logging.getLogger("deepagents_runtime")

# Fastfold skills intentionally use snake_case names (e.g. ``md_openmm_calvados``)
# that do not satisfy the stricter Agent Skills naming spec. They still load
# fine; silence the per-skill spec warnings to keep the CLI output clean while
# preserving genuine load errors.
logging.getLogger("deepagents.middleware.skills").setLevel(logging.ERROR)

__all__ = [
    "OPENAI_TOOL_BUDGET",
    "build_chat_model",
    "build_skills_index_text",
    "create_ct_langchain_tools",
    "create_external_mcp_tools",
    "finalize_tools_for_provider",
    "measure_deepagents_builtin_tool_schemas",
    "process_events",
    "provider_needs_openai_tool_cap",
    "resolve_skill_source_dirs",
    "skill_source_dirs",
    "skill_source_dirs_for_names",
]
