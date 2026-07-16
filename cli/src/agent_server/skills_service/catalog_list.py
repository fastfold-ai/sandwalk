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

    def _summary(self, info) -> SkillSummary:
        return SkillSummary(
            name=info.name,
            description=info.description or "",
            tags=list(info.tags or []),
            source=info.source or "",
            author=info.author or ("fastfold-ai" if info.source == "bundled" else ""),
            version=info.version,
            updated_at=info.updated_at or None,
            icon_src=self._icon_source(info),
            enabled=bool(getattr(info, "enabled", True)),
        )

    def list(self) -> list[SkillSummary]:
        from agent_server import skills_service as _skills_service

        return [self._summary(info) for info in _skills_service.list_skills()]

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
        summary = self._summary(info)
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
