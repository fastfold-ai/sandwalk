"""``AgentStore`` — composed from the domain mixins in this package."""

from __future__ import annotations

from agent_server.store.automations import AutomationMixin
from agent_server.store.base import AgentStoreBase
from agent_server.store.connectors import ConnectorMixin
from agent_server.store.events import EventMixin
from agent_server.store.library import LibraryMixin
from agent_server.store.mcp_servers import McpServerMixin
from agent_server.store.messages import MessageMixin
from agent_server.store.projects import ProjectMixin
from agent_server.store.session_queries import SessionQueryMixin
from agent_server.store.session_updates import SessionUpdateMixin
from agent_server.store.sessions import SessionCreateMixin
from agent_server.store.sites import SiteMixin
from agent_server.store.specialist_updates import SpecialistUpdateMixin
from agent_server.store.specialists import SpecialistMixin
from agent_server.store.terminal_sessions import TerminalSessionMixin
from agent_server.store.usage import UsageMixin
from agent_server.store.workspace_items import WorkspaceItemMixin


class AgentStore(
    SessionCreateMixin,
    SessionQueryMixin,
    SessionUpdateMixin,
    ProjectMixin,
    SpecialistMixin,
    SpecialistUpdateMixin,
    MessageMixin,
    EventMixin,
    McpServerMixin,
    LibraryMixin,
    SiteMixin,
    ConnectorMixin,
    TerminalSessionMixin,
    WorkspaceItemMixin,
    UsageMixin,
    AutomationMixin,
    AgentStoreBase,
):
    """Small durable store shared by CLI and web transports.

    Behavior lives in the mixins above, grouped by domain (sessions, projects,
    specialists, messages, events, MCP servers); lifecycle (open/close/schema)
    lives in :class:`AgentStoreBase`. See that class's docstring for the
    durability rules this store follows.
    """
