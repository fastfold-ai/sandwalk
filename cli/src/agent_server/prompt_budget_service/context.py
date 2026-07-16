"""Resolve specialist/project/MCP context for a prompt-budget estimate."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent.config import Config
from agent_server.models import Specialist
from agent_server.store import AgentStore


@dataclass
class BudgetContext:
    specialist: Specialist | None = None
    project_context: str | None = None
    specialist_instructions: str | None = None
    allowed_skill_names: list[str] | None = None
    allowed_tool_names: list[str] | None = None
    mcp_servers: list[Any] = field(default_factory=list)
    exclude_tool_names: set[str] = field(default_factory=set)


def resolve_budget_context(
    store: AgentStore,
    cfg: Config,
    *,
    specialist_id: str | None,
    project_id: str | None,
) -> BudgetContext:
    from agent_server.default_specialists import filter_mcp_servers_for_specialist
    from agent_server.mcp_service import McpService
    from tools import ensure_loaded, registry

    ctx = BudgetContext(mcp_servers=McpService(store).resolve_runtime_servers())

    if specialist_id:
        ctx.specialist = store.get_specialist(str(specialist_id).strip())

    if project_id:
        project = store.get_project(str(project_id).strip())
        if project and project.agent_context:
            ctx.project_context = project.agent_context

    if ctx.specialist is not None:
        specialist = ctx.specialist
        if specialist.instructions and specialist.instructions.strip():
            ctx.specialist_instructions = specialist.instructions.strip()
        ctx.allowed_skill_names = list(specialist.skill_names or [])
        ctx.allowed_tool_names = list(specialist.tool_names or [])
        ctx.mcp_servers = filter_mcp_servers_for_specialist(
            ctx.mcp_servers,
            mcp_server_ids=list(specialist.mcp_server_ids or []),
            mcp_catalog_ids=list(specialist.mcp_catalog_ids or []),
        )

    ctx.exclude_tool_names = set(cfg.hidden_tools())
    if ctx.allowed_tool_names is not None:
        ensure_loaded()
        allow = {str(n).strip() for n in ctx.allowed_tool_names if str(n).strip()}
        for tool_obj in registry.list_tools():
            if tool_obj.name not in allow:
                ctx.exclude_tool_names.add(tool_obj.name)

    return ctx
