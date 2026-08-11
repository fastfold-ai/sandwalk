"""Installed-skill listing, icons, and detail lookup mixin.

Calls ``list_skills``/``skill_info`` via a lazy self-import (not a direct
``from agent.skills import ...`` at module scope) so tests that monkeypatch
``agent_server.skills_service.list_skills``/``...skill_info`` are honored,
matching this module's behavior from before the split.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from agent_server.models import SkillDetail, SkillSource, SkillSummary

_ICON_FILE_CANDIDATES = (
    "icon.svg",
    "icon.png",
    "icon.jpg",
    "icon.jpeg",
    "icon.webp",
    "logo.svg",
    "logo.png",
    "logo.jpg",
    "logo.jpeg",
    "logo.webp",
    "assets/icon.svg",
    "assets/icon.png",
    "assets/icon.jpg",
    "assets/icon.jpeg",
    "assets/icon.webp",
    "assets/logo.svg",
    "assets/logo.png",
    "assets/logo.jpg",
    "assets/logo.jpeg",
    "assets/logo.webp",
)


class CatalogListMixin:
    @staticmethod
    def _icon_source(info) -> str | None:
        raw_icon = str(getattr(info, "icon", "") or "").strip()
        if raw_icon.startswith(("http://", "https://", "data:", "/")):
            return raw_icon
        if CatalogListMixin._icon_file_path(info):
            return f"/v1/skills/{quote(info.name, safe='')}/icon"
        return None

    @staticmethod
    def _icon_file_path(info) -> Path | None:
        skill_dir = getattr(info, "directory", None)
        if skill_dir is None:
            return None
        root = Path(skill_dir).resolve()

        raw_icon = str(getattr(info, "icon", "") or "").strip()
        if raw_icon and not raw_icon.startswith(("http://", "https://", "data:", "/")):
            requested = (root / raw_icon).resolve()
            if requested.is_file() and (requested == root or root in requested.parents):
                return requested

        for rel in _ICON_FILE_CANDIDATES:
            candidate = (root / rel).resolve()
            if candidate.is_file() and (candidate == root or root in candidate.parents):
                return candidate
        return None

    def _summary(self, info, *, update: dict | None = None) -> SkillSummary:
        from agent.skills.models import (
            USER_CREATED_CATEGORY,
            display_author,
            is_user_created_skill,
        )

        author = display_author(info)
        if author in {"-", ""}:
            author = info.author or ("sandwalk" if info.source == "bundled" else "")
        category = str(getattr(info, "category", "") or "").strip()
        if is_user_created_skill(info):
            category = USER_CREATED_CATEGORY
        elif (info.source or "") == "bundled" and not category:
            category = "Built-in"
        update = update or {}
        from agent.skills.deps import has_runtime_deps

        return SkillSummary(
            name=info.name,
            description=info.description or "",
            tags=list(info.tags or []),
            source=info.source or "",
            author=author,
            category=category,
            version=info.version,
            updated_at=info.updated_at or None,
            icon_src=self._icon_source(info),
            enabled=bool(getattr(info, "enabled", True)),
            commit=getattr(info, "commit", None),
            update_available=bool(update.get("available")),
            latest_version=str(update["latest"]) if update.get("latest") else None,
            update_channel=str(update["channel"]) if update.get("channel") else None,
            has_runtime_deps=has_runtime_deps(info.name),
            deps_status=None,
        )

    @staticmethod
    def _updates_by_source(infos: list, *, force: bool = False) -> dict[str, dict]:
        """Map ``owner/repo`` → update info (one GitHub lookup per unique repo)."""
        from agent.skills.releases import (
            _owner_repo_from_source,
            check_github_skill_update,
        )

        by_repo: dict[str, dict] = {}
        checked: set[str] = set()
        for info in infos:
            source = str(getattr(info, "source", "") or "").strip()
            owner_repo = _owner_repo_from_source(source) if source else None
            if not owner_repo or owner_repo in checked:
                continue
            checked.add(owner_repo)
            try:
                update = check_github_skill_update(
                    source,
                    installed_release=getattr(info, "version", None),
                    installed_commit=getattr(info, "commit", None),
                    force=force,
                )
            except Exception:  # noqa: BLE001
                update = None
            if update:
                by_repo[owner_repo] = update
        return by_repo

    @staticmethod
    def _update_for_info(info, updates: dict[str, dict]) -> dict | None:
        from agent.skills.releases import _owner_repo_from_source

        source = str(getattr(info, "source", "") or "").strip()
        owner_repo = _owner_repo_from_source(source) if source else None
        if not owner_repo:
            return None
        return updates.get(owner_repo)

    def list(self) -> list[SkillSummary]:
        from agent_server import skills_service as _skills_service

        infos = list(_skills_service.list_skills())
        updates = self._updates_by_source(infos)
        return [
            self._summary(info, update=self._update_for_info(info, updates))
            for info in infos
        ]

    def suggested_sources(self) -> list[SkillSource]:
        from agent.skills import SUGGESTED_SKILL_SOURCES

        return [
            SkillSource(
                provider=str(item.get("provider") or ""),
                source=str(item.get("source") or ""),
                url=str(item.get("url") or ""),
                description=str(item.get("description") or ""),
            )
            for item in SUGGESTED_SKILL_SOURCES
            if isinstance(item, dict)
        ]

    def get(self, name: str) -> SkillDetail | None:
        from agent_server import skills_service as _skills_service

        info = _skills_service.skill_info(name)
        if info is None or info.path is None:
            return None
        try:
            content = info.path.read_text(encoding="utf-8")
        except OSError:
            content = ""
        # Force a fresh GitHub release check on the detail page so a just-published
        # tag is not hidden behind the short-lived local update cache.
        updates = self._updates_by_source([info], force=True)
        summary = self._summary(info, update=self._update_for_info(info, updates))
        return SkillDetail(
            **summary.model_dump(),
            content=content,
            directory=str(info.directory) if info.directory else None,
        )

    def get_icon_path(self, name: str) -> Path | None:
        from agent_server import skills_service as _skills_service

        info = _skills_service.skill_info(name)
        if info is None:
            return None
        return self._icon_file_path(info)
