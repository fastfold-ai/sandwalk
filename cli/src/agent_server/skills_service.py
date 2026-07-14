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
    CatalogSkill,
    CatalogSkillAudit,
    CatalogSkillAuditEntry,
    CatalogSkillDetail,
    CatalogSkillFile,
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
    def _jwt_expired(token: str, *, skew_seconds: int = 120) -> bool:
        """Return True when a JWT looks past expiry (Vercel OIDC lasts ~12h)."""
        try:
            import base64
            import time

            parts = token.split(".")
            if len(parts) != 3:
                return False
            payload_b64 = parts[1]
            pad = "=" * ((4 - len(payload_b64) % 4) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_b64 + pad))
            exp = payload.get("exp")
            if not isinstance(exp, (int, float)):
                return False
            return time.time() >= float(exp) - skew_seconds
        except Exception:
            return False

    @classmethod
    def _refresh_vercel_oidc_token(cls) -> str:
        """Pull a fresh VERCEL_OIDC_TOKEN via the linked Vercel CLI project."""
        from agent.config import sync_process_env_from_config
        from agent_server.integrations_service import IntegrationsService

        workspace = IntegrationsService._vercel_workspace_dir()
        token, err = IntegrationsService._fetch_vercel_oidc_token_via_cli(workspace)
        token = str(token or "").strip()
        if not token:
            detail = f" {err}" if err else ""
            raise RuntimeError(
                "skills.sh authentication required. Open Integrations → Vercel "
                "and run setup (vercel login / link / env pull), or set "
                f"VERCEL_OIDC_TOKEN.{detail}"
            )
        config = Config.load()
        config.set("api.vercel_oidc_token", token)
        config.save()
        os.environ["VERCEL_OIDC_TOKEN"] = token
        sync_process_env_from_config(config)
        return token

    @classmethod
    def _skills_sh_token(cls, *, force_refresh: bool = False) -> str:
        if force_refresh:
            return cls._refresh_vercel_oidc_token()

        config = Config.load()
        config_token = str(config.get("api.vercel_oidc_token") or "").strip()
        token = str(
            os.environ.get("VERCEL_OIDC_TOKEN")
            or config_token
            or ""
        ).strip()
        if token and not cls._jwt_expired(token):
            return token
        # Missing or expired (~12h) — refresh via Vercel CLI when linked.
        try:
            return cls._refresh_vercel_oidc_token()
        except RuntimeError:
            if token:
                raise RuntimeError(
                    "Vercel OIDC token expired and could not be refreshed. "
                    "Open Integrations → Vercel and run setup again."
                ) from None
            raise RuntimeError(
                "Vercel integration is not configured. Open Integrations → Vercel "
                "and run setup, or set VERCEL_OIDC_TOKEN."
            ) from None

    def _skills_sh_request_json(
        self,
        endpoint: str,
        *,
        operation: str,
        _retried: bool = False,
    ) -> dict[str, Any]:
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
                if not _retried:
                    try:
                        self._skills_sh_token(force_refresh=True)
                    except RuntimeError as refresh_exc:
                        raise RuntimeError(str(refresh_exc)) from exc
                    return self._skills_sh_request_json(
                        endpoint, operation=operation, _retried=True
                    )
                raise RuntimeError(
                    "skills.sh authentication failed (token rejected). "
                    "Open Integrations → Vercel and refresh setup."
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
