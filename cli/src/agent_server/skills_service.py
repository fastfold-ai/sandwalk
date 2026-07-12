"""Web-facing adapter around the CLI's canonical skill manager."""

from __future__ import annotations

import json
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from agent.config import Config
from agent.skills import (
    SUGGESTED_SKILL_SOURCES,
    install_skill,
    list_skills,
    remove_skill,
    set_skill_enabled,
    skill_info,
    upgrade_skills,
)
from agent_server.models import (
    CatalogSkillAudit,
    CatalogSkillAuditEntry,
    CatalogSkillDetail,
    CatalogSkillFile,
    CatalogSkill,
    SkillBatchAction,
    SkillBatchActionFailure,
    SkillBatchActionResponse,
    SkillDetail,
    SkillMutationResponse,
    SkillSource,
    SkillSummary,
)

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

_SKILLS_SH_BASE_URL = "https://skills.sh"


class SkillsService:
    @staticmethod
    def _icon_source(info) -> str | None:
        raw_icon = str(getattr(info, "icon", "") or "").strip()
        if raw_icon.startswith(("http://", "https://", "data:", "/")):
            return raw_icon
        if SkillsService._icon_file_path(info):
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
        return [self._summary(info) for info in list_skills()]

    def suggested_sources(self) -> list[SkillSource]:
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

    @staticmethod
    def _skills_sh_token() -> str:
        config = Config.load()
        config_token = str(config.get("api.vercel_oidc_token") or "").strip()
        token = str(
            os.environ.get("VERCEL_OIDC_TOKEN")
            or config_token
            or ""
        ).strip()
        if not token:
            raise RuntimeError(
                "Vercel integration is not configured. Set VERCEL_OIDC_TOKEN "
                "in Integrations (/keys)."
            )
        return token

    def _skills_sh_request_json(self, endpoint: str, *, operation: str) -> dict[str, Any]:
        headers = {
            "accept": "application/json",
            "authorization": f"Bearer {self._skills_sh_token()}",
        }
        request = Request(endpoint, headers=headers, method="GET")
        try:
            with urlopen(request, timeout=8) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code == 401:
                raise RuntimeError(
                    "skills.sh authentication required. Configure VERCEL_OIDC_TOKEN "
                    "in Integrations (/keys)."
                ) from exc
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="ignore").strip()
            except Exception:
                detail = ""
            if exc.code == 404:
                raise LookupError(detail or "Not found.") from exc
            suffix = f" {detail}" if detail else ""
            raise RuntimeError(f"{operation} failed ({exc.code}).{suffix}") from exc
        except URLError as exc:
            raise RuntimeError(f"{operation} is unavailable.") from exc
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"{operation} returned an invalid response.") from exc

        if not isinstance(payload, dict):
            raise RuntimeError(f"{operation} returned an invalid response.")
        return payload

    def search_catalog(self, query: str, limit: int = 12) -> list[CatalogSkill]:
        query_value = str(query or "").strip()
        if len(query_value) < 2:
            return []
        bounded_limit = max(1, min(int(limit), 50))
        params = urlencode({"q": query_value, "limit": bounded_limit})
        endpoint = f"{_SKILLS_SH_BASE_URL}/api/v1/skills/search?{params}"
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

    def get_catalog_detail(self, source: str, skill: str) -> CatalogSkillDetail:
        source_value = str(source or "").strip().strip("/")
        skill_value = str(skill or "").strip().strip("/")
        if not source_value or not skill_value:
            raise ValueError("Both source and skill are required.")
        endpoint = (
            f"{_SKILLS_SH_BASE_URL}/api/v1/skills/"
            f"{quote(source_value, safe='/')}/{quote(skill_value, safe='')}"
        )
        payload = self._skills_sh_request_json(
            endpoint,
            operation="skills.sh skill detail",
        )
        files_payload = payload.get("files")
        files: list[CatalogSkillFile] | None = None
        if isinstance(files_payload, list):
            normalized_files: list[CatalogSkillFile] = []
            for item in files_payload:
                if not isinstance(item, dict):
                    continue
                path = str(item.get("path") or "").strip()
                if not path:
                    continue
                normalized_files.append(
                    CatalogSkillFile(
                        path=path,
                        contents=str(item.get("contents") or ""),
                    )
                )
            files = normalized_files
        return CatalogSkillDetail(
            id=str(payload.get("id") or f"{source_value}/{skill_value}"),
            source=str(payload.get("source") or source_value),
            slug=str(payload.get("slug") or skill_value),
            installs=int(payload.get("installs") or 0),
            hash=str(payload.get("hash")) if payload.get("hash") is not None else None,
            files=files,
        )

    def get_catalog_audit(self, source: str, skill: str) -> CatalogSkillAudit:
        source_value = str(source or "").strip().strip("/")
        skill_value = str(skill or "").strip().strip("/")
        if not source_value or not skill_value:
            raise ValueError("Both source and skill are required.")
        endpoint = (
            f"{_SKILLS_SH_BASE_URL}/api/v1/skills/audit/"
            f"{quote(source_value, safe='/')}/{quote(skill_value, safe='')}"
        )
        try:
            payload = self._skills_sh_request_json(
                endpoint,
                operation="skills.sh audit",
            )
        except LookupError:
            return CatalogSkillAudit(
                id=f"{source_value}/{skill_value}",
                source=source_value,
                slug=skill_value,
                audits=[],
            )
        audits_payload = payload.get("audits")
        audits: list[CatalogSkillAuditEntry] = []
        if isinstance(audits_payload, list):
            for item in audits_payload:
                if not isinstance(item, dict):
                    continue
                audits.append(
                    CatalogSkillAuditEntry(
                        provider=str(item.get("provider") or ""),
                        slug=str(item.get("slug") or ""),
                        status=str(item.get("status") or ""),
                        summary=str(item.get("summary") or ""),
                        audited_at=(
                            str(item.get("auditedAt"))
                            if item.get("auditedAt") is not None
                            else None
                        ),
                        risk_level=(
                            str(item.get("riskLevel"))
                            if item.get("riskLevel") is not None
                            else None
                        ),
                        categories=[
                            str(category)
                            for category in item.get("categories") or []
                            if str(category).strip()
                        ],
                    )
                )
        return CatalogSkillAudit(
            id=str(payload.get("id") or f"{source_value}/{skill_value}"),
            source=str(payload.get("source") or source_value),
            slug=str(payload.get("slug") or skill_value),
            audits=audits,
        )

    def get(self, name: str) -> SkillDetail | None:
        info = skill_info(name)
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
        info = skill_info(name)
        if info is None:
            return None
        return self._icon_file_path(info)

    def install(self, source: str) -> SkillMutationResponse:
        # Same path as `fastfold skills add`: git/archive first, then npx fallback.
        # Nested layouts (e.g. skills/.curated/<name>) are resolved by skill name.
        result = install_skill(source)
        return SkillMutationResponse(
            ok=bool(result.get("ok")),
            summary=str(result.get("summary") or ""),
            installed=[str(item) for item in result.get("installed") or []],
        )

    def remove(self, name: str) -> SkillMutationResponse:
        result = remove_skill(name)
        return SkillMutationResponse(
            ok=bool(result.get("ok")),
            summary=str(result.get("summary") or ""),
        )

    def upgrade(self) -> SkillMutationResponse:
        result = upgrade_skills()
        installed = [
            *[str(item) for item in result.get("added") or []],
            *[str(item) for item in result.get("updated") or []],
        ]
        return SkillMutationResponse(
            ok=not bool(result.get("failed")),
            summary=str(result.get("summary") or ""),
            installed=installed,
        )

    def install_uploaded_file(self, filename: str | None, data: bytes) -> SkillMutationResponse:
        if not data:
            return SkillMutationResponse(
                ok=False,
                summary="Uploaded file is empty.",
            )

        name = (filename or "upload").strip() or "upload"
        suffix = Path(name).suffix.lower()

        with tempfile.TemporaryDirectory(prefix="fastfold-skill-upload-") as tmp:
            tmp_dir = Path(tmp)
            source_path: Path

            if suffix in {".zip", ".skill"}:
                archive_path = tmp_dir / name
                archive_path.write_bytes(data)
                extract_dir = tmp_dir / "extracted"
                extract_dir.mkdir(parents=True, exist_ok=True)
                try:
                    with zipfile.ZipFile(archive_path) as archive:
                        extract_root = extract_dir.resolve()
                        for member in archive.infolist():
                            target = (extract_dir / member.filename).resolve()
                            if target != extract_root and extract_root not in target.parents:
                                return SkillMutationResponse(
                                    ok=False,
                                    summary="Archive contains invalid file paths.",
                                )
                        archive.extractall(extract_dir)
                except zipfile.BadZipFile:
                    return SkillMutationResponse(
                        ok=False,
                        summary="Uploaded archive is not a valid .zip/.skill bundle.",
                    )
                source_path = extract_dir
            elif suffix == ".md":
                skill_dir_name = (
                    Path(name).parent.name
                    if Path(name).name.lower() == "skill.md" and Path(name).parent.name
                    else Path(name).stem
                ) or "uploaded_skill"
                skill_dir = tmp_dir / skill_dir_name
                skill_dir.mkdir(parents=True, exist_ok=True)
                (skill_dir / "SKILL.md").write_bytes(data)
                source_path = skill_dir
            else:
                return SkillMutationResponse(
                    ok=False,
                    summary="Unsupported upload type. Use .zip, .skill, or SKILL.md.",
                )

            result = install_skill(str(source_path))
            return SkillMutationResponse(
                ok=bool(result.get("ok")),
                summary=str(result.get("summary") or ""),
                installed=[str(item) for item in result.get("installed") or []],
            )

    def set_enabled(self, name: str, enabled: bool) -> SkillSummary | None:
        result = set_skill_enabled(name, enabled)
        if not result.get("ok"):
            return None
        info = skill_info(name)
        if info is None:
            return None
        return self._summary(info)

    def batch_action(self, action: SkillBatchAction, names: list[str]) -> SkillBatchActionResponse:
        requested_names = [str(name).strip() for name in names if str(name).strip()]
        deduped_names: list[str] = []
        seen: set[str] = set()
        for name in requested_names:
            if name in seen:
                continue
            seen.add(name)
            deduped_names.append(name)

        succeeded: list[str] = []
        failed: list[SkillBatchActionFailure] = []
        for name in deduped_names:
            if action == "remove":
                result = remove_skill(name)
            else:
                result = set_skill_enabled(name, enabled=(action == "enable"))
            if result.get("ok"):
                succeeded.append(name)
            else:
                failed.append(
                    SkillBatchActionFailure(
                        name=name,
                        reason=str(result.get("summary") or "Unknown error"),
                    )
                )

        total = len(deduped_names)
        return SkillBatchActionResponse(
            ok=not failed,
            action=action,
            requested=total,
            succeeded=succeeded,
            failed=failed,
            summary=f"{action.title()} completed: {len(succeeded)}/{total} succeeded.",
        )
