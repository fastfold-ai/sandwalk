"""Route registration for the agent_server FastAPI app."""

from __future__ import annotations

from fastapi import FastAPI

from agent_server.app_deps import AppDeps
from agent_server.routes.account import register_account_routes
from agent_server.routes.auth import register_auth_routes
from agent_server.routes.automations import register_automation_and_ssh_routes
from agent_server.routes.bench import register_bench_routes
from agent_server.routes.capy import register_capy_routes
from agent_server.routes.chatgpt_auth import register_chatgpt_auth_routes
from agent_server.routes.connectors import register_connector_routes
from agent_server.routes.dashboard_layout import register_dashboard_layout_routes
from agent_server.routes.datasets_tools import register_dataset_tool_routes
from agent_server.routes.events_mux import register_events_mux_routes
from agent_server.routes.external_agents import register_external_agent_routes
from agent_server.routes.health import register_health_routes
from agent_server.routes.integrations import register_integration_routes
from agent_server.routes.library import register_library_routes
from agent_server.routes.llama_runtime import register_llama_runtime_routes
from agent_server.routes.mcp_catalog import register_mcp_catalog_routes
from agent_server.routes.mcp_catalog_connect import register_mcp_catalog_connect_routes
from agent_server.routes.mcp_oauth import register_mcp_oauth_routes
from agent_server.routes.mcp_servers import register_mcp_server_routes
from agent_server.routes.mcp_servers_connect import register_mcp_server_connect_routes
from agent_server.routes.mcp_servers_manage import register_mcp_server_manage_routes
from agent_server.routes.memory import register_memory_routes
from agent_server.routes.model_profiles import register_model_profile_routes
from agent_server.routes.models import register_model_routes
from agent_server.routes.offline_status import register_offline_status_routes
from agent_server.routes.projects import register_project_routes
from agent_server.routes.session_events_global import (
    register_session_events_global_routes,
)
from agent_server.routes.sessions import register_session_routes
from agent_server.routes.sessions_events import register_session_event_routes
from agent_server.routes.sessions_messages import register_message_routes
from agent_server.routes.sessions_pty import register_pty_routes
from agent_server.routes.sessions_sandbox import register_session_sandbox_routes
from agent_server.routes.sessions_sandbox_stream import register_session_sandbox_stream_routes
from agent_server.routes.sessions_workspace import register_workspace_routes
from agent_server.routes.sessions_workspace_mutate import register_workspace_mutate_routes
from agent_server.routes.settings import register_settings_routes
from agent_server.routes.sites import register_site_routes
from agent_server.routes.skills import register_skill_routes
from agent_server.routes.slack_oauth_return import register_slack_oauth_return_routes
from agent_server.routes.specialists import register_specialist_routes
from agent_server.routes.terminals import register_terminal_routes
from agent_server.routes.ui_commands import register_ui_command_routes
from agent_server.routes.usage import register_usage_routes
from agent_server.routes.workspace_items import register_workspace_item_routes


def register_all_routes(app: FastAPI, deps: AppDeps) -> None:
    """Register every `/v1/*` route on `app`. Auth middleware is wired separately."""
    register_auth_routes(app, deps)
    register_chatgpt_auth_routes(app, deps)
    register_health_routes(app, deps)
    register_offline_status_routes(app, deps)
    register_mcp_server_routes(app, deps)
    register_mcp_server_manage_routes(app, deps)
    register_mcp_server_connect_routes(app, deps)
    register_mcp_catalog_routes(app, deps)
    register_mcp_catalog_connect_routes(app, deps)
    register_mcp_oauth_routes(app, deps)
    register_integration_routes(app, deps)
    register_settings_routes(app, deps)
    register_bench_routes(app, deps)
    register_capy_routes(app, deps)
    register_ui_command_routes(app, deps)
    register_account_routes(app, deps)
    register_model_routes(app, deps)
    register_model_profile_routes(app, deps)
    register_dataset_tool_routes(app, deps)
    register_skill_routes(app, deps)
    register_site_routes(app, deps)
    register_project_routes(app, deps)
    register_library_routes(app, deps)
    register_llama_runtime_routes(app, deps)
    register_memory_routes(app, deps)
    register_automation_and_ssh_routes(app, deps)
    register_connector_routes(app, deps)
    register_slack_oauth_return_routes(app, deps)
    register_specialist_routes(app, deps)
    register_session_routes(app, deps)
    register_usage_routes(app, deps)
    register_dashboard_layout_routes(app, deps)
    register_session_sandbox_routes(app, deps)
    register_session_sandbox_stream_routes(app, deps)
    register_message_routes(app, deps)
    register_workspace_routes(app, deps)
    register_workspace_mutate_routes(app, deps)
    register_pty_routes(app, deps)
    register_terminal_routes(app, deps)
    register_external_agent_routes(app, deps)
    register_workspace_item_routes(app, deps)
    register_session_event_routes(app, deps)
    register_session_events_global_routes(app, deps)
    register_events_mux_routes(app, deps)
