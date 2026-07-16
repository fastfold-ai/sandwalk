"""skills.sh catalog detail and security-audit lookup mixin."""

from __future__ import annotations

from urllib.parse import quote

from agent_server.models import (
    CatalogSkillAudit,
    CatalogSkillAuditEntry,
    CatalogSkillDetail,
    CatalogSkillFile,
)
from agent_server.skills_service.auth import SKILLS_SH_BASE_URL


class CatalogDetailMixin:
    def get_catalog_detail(self, source: str, skill: str) -> CatalogSkillDetail:
        source_value = str(source or "").strip().strip("/")
        skill_value = str(skill or "").strip().strip("/")
        if not source_value or not skill_value:
            raise ValueError("Both source and skill are required.")
        endpoint = (
            f"{SKILLS_SH_BASE_URL}/api/v1/skills/"
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
        installs = int(payload.get("installs") or 0)
        if installs <= 0:
            enriched = self._installs_from_search(source_value, skill_value)
            if enriched is not None and enriched > 0:
                installs = enriched
        return CatalogSkillDetail(
            id=str(payload.get("id") or f"{source_value}/{skill_value}"),
            source=str(payload.get("source") or source_value),
            slug=str(payload.get("slug") or skill_value),
            installs=installs,
            hash=str(payload.get("hash")) if payload.get("hash") is not None else None,
            files=files,
        )

    def get_catalog_audit(self, source: str, skill: str) -> CatalogSkillAudit:
        source_value = str(source or "").strip().strip("/")
        skill_value = str(skill or "").strip().strip("/")
        if not source_value or not skill_value:
            raise ValueError("Both source and skill are required.")
        endpoint = (
            f"{SKILLS_SH_BASE_URL}/api/v1/skills/audit/"
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
