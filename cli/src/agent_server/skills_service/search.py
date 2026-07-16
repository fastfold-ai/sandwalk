"""skills.sh catalog search and install-count enrichment mixin."""

from __future__ import annotations

from urllib.parse import urlencode

from agent_server.models import CatalogSkill
from agent_server.skills_service.auth import SKILLS_SH_BASE_URL


class SearchMixin:
    def search_catalog(self, query: str, limit: int = 12) -> list[CatalogSkill]:
        query_value = str(query or "").strip()
        if len(query_value) < 2:
            return []
        bounded_limit = max(1, min(int(limit), 50))
        params = urlencode({"q": query_value, "limit": bounded_limit})
        endpoint = f"{SKILLS_SH_BASE_URL}/api/v1/skills/search?{params}"
        try:
            payload = self._skills_sh_request_json(endpoint, operation="skills.sh search")
        except LookupError:
            return []

        items = payload.get("data")
        if not isinstance(items, list):
            return []
        results: list[CatalogSkill] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            results.append(
                CatalogSkill(
                    id=str(item.get("id") or ""),
                    slug=str(item.get("slug") or ""),
                    name=str(item.get("name") or ""),
                    source=str(item.get("source") or ""),
                    installs=int(item.get("installs") or 0),
                    source_type=str(item.get("sourceType") or ""),
                    install_url=(
                        str(item.get("installUrl"))
                        if item.get("installUrl") is not None
                        else None
                    ),
                    url=str(item.get("url")) if item.get("url") is not None else None,
                )
            )
        return results

    @staticmethod
    def _normalize_skill_key(value: str) -> str:
        return str(value or "").strip().lower().replace("-", "_").strip("/")

    def _installs_from_search(self, source: str, skill: str) -> int | None:
        """skills.sh detail often returns installs=0; search has the real count."""
        skill_key = self._normalize_skill_key(skill)
        source_key = self._normalize_skill_key(source)
        if not skill_key:
            return None
        try:
            results = self.search_catalog(skill, limit=10)
        except Exception:
            return None
        best: int | None = None
        for item in results:
            name_key = self._normalize_skill_key(item.name or item.slug or "")
            if name_key != skill_key:
                continue
            item_source = self._normalize_skill_key(item.source or "")
            if source_key and item_source and item_source != source_key:
                continue
            installs = int(item.installs or 0)
            if best is None or installs > best:
                best = installs
        return best
