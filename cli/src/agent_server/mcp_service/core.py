"""``McpService`` — composed from the mixins in this package."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

from agent_server.mcp_service.service_catalog import CatalogMixin
from agent_server.mcp_service.service_credentials import CredentialsMixin
from agent_server.mcp_service.service_custom_auth import CustomAuthMixin
from agent_server.mcp_service.service_enable import EnableMixin
from agent_server.mcp_service.service_install import InstallMixin
from agent_server.mcp_service.service_oauth_complete import OAuthCompleteMixin
from agent_server.mcp_service.service_oauth_start import OAuthStartMixin
from agent_server.mcp_service.service_runtime import RuntimeMixin
from agent_server.mcp_service.service_validate import ValidateMixin
from agent_server.store import AgentStore


@dataclass
class McpService(
    CatalogMixin,
    CredentialsMixin,
    EnableMixin,
    InstallMixin,
    ValidateMixin,
    OAuthStartMixin,
    CustomAuthMixin,
    OAuthCompleteMixin,
    RuntimeMixin,
):
    """MCP catalog connect, credential resolution, OAuth, and probe orchestration.

    Behavior lives in the mixins above, grouped by concern (catalog listing,
    credentials, enable/disable, validate, OAuth start/complete, custom-server
    auth, runtime resolution); see :mod:`agent_server.mcp_service` for the
    module-level helpers (headers, health cache, probing, OAuth discovery)
    these mixins build on.
    """

    store: AgentStore
    public_base_url: str = "http://127.0.0.1:8787"
    _lock: threading.RLock = field(default_factory=threading.RLock)
