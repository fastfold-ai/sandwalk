"""``SkillsService`` assembled from focused mixins."""

from __future__ import annotations

from agent_server.skills_service.auth import AuthMixin
from agent_server.skills_service.catalog_detail import CatalogDetailMixin
from agent_server.skills_service.catalog_list import CatalogListMixin
from agent_server.skills_service.deps import DepsMixin
from agent_server.skills_service.mutate import MutateMixin
from agent_server.skills_service.search import SearchMixin


class SkillsService(
    CatalogListMixin,
    AuthMixin,
    SearchMixin,
    CatalogDetailMixin,
    MutateMixin,
    DepsMixin,
):
    """Web-facing adapter around the CLI's canonical skill manager."""
