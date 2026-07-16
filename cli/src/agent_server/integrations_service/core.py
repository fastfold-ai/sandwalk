"""``IntegrationsService`` assembled from focused mixins."""

from __future__ import annotations

from agent_server.integrations_service.mutate import MutateMixin
from agent_server.integrations_service.provider import ProviderMixin
from agent_server.integrations_service.setup import SetupMixin
from agent_server.integrations_service.vercel import VercelMixin


class IntegrationsService(ProviderMixin, MutateMixin, VercelMixin, SetupMixin):
    """Shared implementation behind CLI keys and web integrations."""
