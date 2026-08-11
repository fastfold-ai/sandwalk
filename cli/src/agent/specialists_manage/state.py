"""Active-specialist config state and context application."""

from __future__ import annotations

from typing import Any

from agent.config import Config
from agent_server.models import Specialist
from agent_server.store import AgentStore

CLI_SPECIALIST_CONFIG_KEY = "agent.cli_specialist"


def _store() -> AgentStore:
    return AgentStore()


def resolve_specialist_ref(ref: str, store: AgentStore | None = None) -> Specialist | None:
    return (store or _store()).resolve_specialist_ref(ref)


def get_active_specialist_ref(config: Config | None = None) -> str | None:
    cfg = config or Config.load()
    value = str(cfg.get(CLI_SPECIALIST_CONFIG_KEY, "") or "").strip()
    return value or None


def set_active_specialist_ref(ref: str | None, config: Config | None = None) -> None:
    cfg = config or Config.load()
    if ref and str(ref).strip():
        cfg.set(CLI_SPECIALIST_CONFIG_KEY, str(ref).strip())
    else:
        cfg.set(CLI_SPECIALIST_CONFIG_KEY, "")
    cfg.save()


def get_active_specialist(
    config: Config | None = None,
    store: AgentStore | None = None,
) -> Specialist | None:
    ref = get_active_specialist_ref(config)
    if not ref:
        return None
    return resolve_specialist_ref(ref, store)


def apply_specialist_to_context(
    context: dict[str, Any] | None,
    specialist: Specialist | None,
    *,
    store: AgentStore | None = None,
) -> dict[str, Any]:
    """Mutate/return run context with specialist instructions, skills, and MCPs.

    When *specialist* is None, injects all enabled MCP servers (same as the
    local-web agent server with no session specialist). When a specialist is
    set, MCP servers are filtered to that specialist's allowlist.
    """
    ctx = dict(context or {})
    from agent_server.mcp_service import McpService

    agent_store = store or _store()
    servers = McpService(agent_store).resolve_runtime_servers()

    if specialist is None:
        ctx.pop("specialist_instructions", None)
        ctx.pop("allowed_skill_names", None)
        ctx["mcp_servers"] = servers
        return ctx

    instructions = (specialist.instructions or "").strip()
    if instructions:
        ctx["specialist_instructions"] = instructions
    else:
        ctx.pop("specialist_instructions", None)

    ctx["allowed_skill_names"] = list(specialist.skill_names or [])

    from agent_server.default_specialists import filter_mcp_servers_for_specialist

    ctx["mcp_servers"] = filter_mcp_servers_for_specialist(
        servers,
        mcp_server_ids=list(specialist.mcp_server_ids or []),
        mcp_catalog_ids=list(getattr(specialist, "mcp_catalog_ids", None) or []),
    )
    return ctx
