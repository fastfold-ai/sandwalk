"""Project + specialist context gathering for a session run."""

from __future__ import annotations

from dataclasses import dataclass

from agent_server.store import AgentStore


@dataclass
class RunContext:
    mcp_servers: list
    project_context: str | None
    specialist_instructions: str | None
    allowed_skill_names: list[str] | None
    allowed_tool_names: list[str] | None
    sandbox_backend: str | None
    provider: str | None = None
    model: str | None = None
    openai_profile_id: str | None = None


def build_run_context(store: AgentStore, session_id: str) -> RunContext:
    from agent_server.mcp_service import McpService

    mcp_servers = McpService(store).resolve_runtime_servers()
    project_context = None
    specialist_instructions = None
    allowed_skill_names = None
    allowed_tool_names = None
    current = store.get_session(session_id)
    if current and current.project_id:
        project = store.get_project(current.project_id)
        if project and project.agent_context:
            project_context = project.agent_context
    if current and current.specialist_id:
        specialist = store.get_specialist(current.specialist_id)
        if specialist is not None:
            from agent_server.default_specialists import filter_mcp_servers_for_specialist

            if specialist.instructions and specialist.instructions.strip():
                specialist_instructions = specialist.instructions.strip()
            allowed_skill_names = list(specialist.skill_names or [])
            # Explicit allowlist (may be empty → no domain registry tools).
            allowed_tool_names = list(specialist.tool_names or [])
            mcp_servers = filter_mcp_servers_for_specialist(
                mcp_servers,
                mcp_server_ids=list(specialist.mcp_server_ids or []),
                mcp_catalog_ids=list(specialist.mcp_catalog_ids or []),
            )
    return RunContext(
        mcp_servers=mcp_servers,
        project_context=project_context,
        specialist_instructions=specialist_instructions,
        allowed_skill_names=allowed_skill_names,
        allowed_tool_names=allowed_tool_names,
        sandbox_backend=current.sandbox_backend if current else None,
        provider=current.provider if current else None,
        model=current.model if current else None,
        openai_profile_id=current.openai_profile_id if current else None,
    )
