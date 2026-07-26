"""Route registration for the agent_server FastAPI app."""

from __future__ import annotations

from fastapi import FastAPI

from agent_server.app_deps import AppDeps
from agent_server.routes.account import register_account_routes
from agent_server.routes.auth import register_auth_routes
from agent_server.routes.connectors import register_connector_routes
from agent_server.routes.datasets_tools import register_dataset_tool_routes
from agent_server.routes.health import register_health_routes
from agent_server.routes.integrations import register_integration_routes
from agent_server.routes.library import register_library_routes
from agent_server.routes.mcp_catalog import register_mcp_catalog_routes
from agent_server.routes.mcp_catalog_connect import register_mcp_catalog_connect_routes
from agent_server.routes.mcp_oauth import register_mcp_oauth_routes
from agent_server.routes.mcp_servers import register_mcp_server_routes
from agent_server.routes.mcp_servers_connect import register_mcp_server_connect_routes
from agent_server.routes.mcp_servers_manage import register_mcp_server_manage_routes
from agent_server.routes.model_profiles import register_model_profile_routes
from agent_server.routes.models import register_model_routes
from agent_server.routes.projects import register_project_routes
from agent_server.routes.sessions import register_session_routes
from agent_server.routes.sessions_events import register_session_event_routes
from agent_server.routes.sessions_messages import register_message_routes
from agent_server.routes.sessions_pty import register_pty_routes
from agent_server.routes.sessions_sandbox import register_session_sandbox_routes
from agent_server.routes.sessions_sandbox_stream import register_session_sandbox_stream_routes
from agent_server.routes.sessions_workspace import register_workspace_routes
from agent_server.routes.sessions_workspace_mutate import register_workspace_mutate_routes
from agent_server.routes.settings import register_settings_routes
from agent_server.routes.skills import register_skill_routes
from agent_server.routes.slack_oauth_return import register_slack_oauth_return_routes
from agent_server.routes.specialists import register_specialist_routes


def register_all_routes(app: FastAPI, deps: AppDeps) -> None:
    """Register every `/v1/*` route on `app`. Auth middleware is wired separately."""
    register_auth_routes(app, deps)
    register_health_routes(app, deps)
    register_mcp_server_routes(app, deps)
    register_mcp_server_manage_routes(app, deps)
    register_mcp_server_connect_routes(app, deps)
    register_mcp_catalog_routes(app, deps)
    register_mcp_catalog_connect_routes(app, deps)
    register_mcp_oauth_routes(app, deps)
    register_integration_routes(app, deps)
    register_settings_routes(app, deps)
    register_account_routes(app, deps)
    register_model_routes(app, deps)
    register_model_profile_routes(app, deps)
    register_dataset_tool_routes(app, deps)
    register_skill_routes(app, deps)
    register_project_routes(app, deps)
    register_library_routes(app, deps)
    register_connector_routes(app, deps)
    register_slack_oauth_return_routes(app, deps)
    register_specialist_routes(app, deps)
    register_session_routes(app, deps)
    register_session_sandbox_routes(app, deps)
    register_session_sandbox_stream_routes(app, deps)
    register_message_routes(app, deps)
    register_workspace_routes(app, deps)
    register_workspace_mutate_routes(app, deps)
    register_pty_routes(app, deps)
    register_session_event_routes(app, deps)
