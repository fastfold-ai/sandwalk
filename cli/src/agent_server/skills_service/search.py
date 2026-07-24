"""skills.sh catalog search, leaderboard, and install-count enrichment mixin."""

from __future__ import annotations

import re
import time
from typing import Any
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request

from agent_server.models import CatalogLeaderboard, CatalogSkill
from agent_server.skills_service.auth import SKILLS_SH_BASE_URL

_LEADERBOARD_VIEWS = frozenset({"all-time", "trending", "hot"})
# Homepage "All Time (986,330)" is not pagination.total (~unique skills).
_ALL_TIME_TOTAL_RE = re.compile(r'allTimeTotal\\?":\s*(\d+)')
_all_time_total_cache: tuple[float, int] | None = None
_ALL_TIME_TOTAL_TTL_S = 300.0


def _catalog_skill_from_item(item: dict[str, Any]) -> CatalogSkill:
    return CatalogSkill(
        id=str(item.get("id") or ""),
        slug=str(item.get("slug") or ""),
        name=str(item.get("name") or ""),
        source=str(item.get("source") or ""),
        installs=int(item.get("installs") or 0),
        source_type=str(item.get("sourceType") or ""),
        install_url=(
            str(item.get("installUrl")) if item.get("installUrl") is not None else None
        ),
        url=str(item.get("url")) if item.get("url") is not None else None,
    )


def _catalog_skills_from_payload(payload: object) -> list[CatalogSkill]:
    if not isinstance(payload, dict):
        return []
    items = payload.get("data")
    if not isinstance(items, list):
        return []
    results: list[CatalogSkill] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        results.append(_catalog_skill_from_item(item))
    return results


def _fetch_skills_sh_all_time_total() -> int:
    """Read the homepage All Time badge count (skills.sh SSR ``allTimeTotal``)."""
    global _all_time_total_cache
    now = time.time()
    if _all_time_total_cache is not None:
        cached_at, cached_value = _all_time_total_cache
        if now - cached_at < _ALL_TIME_TOTAL_TTL_S and cached_value > 0:
            return cached_value

    import agent_server.skills_service as skills_service

    request = Request(
        f"{SKILLS_SH_BASE_URL}/",
        headers={
            "Accept": "text/html",
            "User-Agent": "sandwalk-skills-leaderboard/1.0",
        },
        method="GET",
    )
    try:
        with skills_service.urlopen(request, timeout=15) as response:
            body = response.read().decode("utf-8", errors="replace")
    except (URLError, TimeoutError, OSError):
        if _all_time_total_cache is not None:
            return _all_time_total_cache[1]
        return 0

    match = _ALL_TIME_TOTAL_RE.search(body)
    if not match:
        if _all_time_total_cache is not None:
            return _all_time_total_cache[1]
        return 0
    value = int(match.group(1))
    _all_time_total_cache = (now, value)
    return value


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
        return _catalog_skills_from_payload(payload)

    def list_catalog_leaderboard(
        self,
        view: str = "all-time",
        page: int = 0,
        per_page: int = 50,
    ) -> CatalogLeaderboard:
        """Paginated skills.sh leaderboard (All Time / Trending / Hot)."""
        view_value = str(view or "all-time").strip().lower()
        if view_value not in _LEADERBOARD_VIEWS:
            view_value = "all-time"
        page_value = max(0, int(page))
        per_page_value = max(1, min(int(per_page), 100))
        params = urlencode(
            {
                "view": view_value,
                "page": page_value,
                "per_page": per_page_value,
            }
        )
        endpoint = f"{SKILLS_SH_BASE_URL}/api/v1/skills?{params}"
        all_time_total = _fetch_skills_sh_all_time_total()
        try:
            payload = self._skills_sh_request_json(
                endpoint, operation="skills.sh leaderboard"
            )
        except LookupError:
            return CatalogLeaderboard(
                data=[],
                view=view_value,
                page=page_value,
                per_page=per_page_value,
                all_time_total=all_time_total,
            )

        data = _catalog_skills_from_payload(payload)
        pagination = payload.get("pagination") if isinstance(payload, dict) else None
        if not isinstance(pagination, dict):
            pagination = {}
        total = int(pagination.get("total") or len(data))
        has_more = bool(pagination.get("hasMore"))
        return CatalogLeaderboard(
            data=data,
            view=view_value,
            page=int(
                pagination.get("page")
                if pagination.get("page") is not None
                else page_value
            ),
            per_page=int(
                pagination.get("perPage")
                if pagination.get("perPage") is not None
                else per_page_value
            ),
            total=total,
            all_time_total=all_time_total,
            has_more=has_more,
            count=len(data),
        )

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
