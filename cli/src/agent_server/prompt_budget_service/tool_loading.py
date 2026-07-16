"""Build the domain + MCP + deepagents-builtin tool sets for a budget estimate."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from agent_server.prompt_budget_service.context import BudgetContext

logger = logging.getLogger("prompt_budget")


@dataclass
class ToolSets:
    final_domain: list[Any] = field(default_factory=list)
    final_mcp: list[Any] = field(default_factory=list)
    final_tools: list[Any] = field(default_factory=list)
    merged: list[Any] = field(default_factory=list)


async def build_tool_sets(
    *,
    session: Any,
    provider: str,
    tool_mode: str,
    exclude_cats: set[str],
    ctx: BudgetContext,
) -> ToolSets:
    from agent.deepagents_runtime import (
        create_ct_langchain_tools,
        create_external_mcp_tools,
        finalize_tools_for_provider,
    )

    tools, _sandbox, _buf, _dmap = create_ct_langchain_tools(
        session,
        exclude_categories=exclude_cats,
        exclude_tools=ctx.exclude_tool_names,
        provider=provider,
        tool_mode=tool_mode,
    )
    domain_before = list(tools)
    domain_names = {getattr(t, "name", "") for t in domain_before}
    try:
        external = await create_external_mcp_tools(ctx.mcp_servers)
    except Exception as exc:  # noqa: BLE001
        logger.warning("prompt budget MCP load failed: %s", exc)
        external = []
    mcp_before = [t for t in external if getattr(t, "name", "") not in domain_names]
    merged = list(domain_before) + list(mcp_before)
    final_tools = finalize_tools_for_provider(merged, provider)

    # Split post-cap tools back into domain vs MCP for honest counts.
    final_domain = [t for t in final_tools if getattr(t, "name", "") in domain_names]
    final_mcp = [t for t in final_tools if getattr(t, "name", "") not in domain_names]

    return ToolSets(
        final_domain=final_domain,
        final_mcp=final_mcp,
        final_tools=final_tools,
        merged=merged,
    )
