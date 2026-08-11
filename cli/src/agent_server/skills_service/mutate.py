"""Install/remove/upgrade/enable mixin for locally-managed skills.

Calls ``install_skill``/``remove_skill``/``upgrade_skills``/``set_skill_enabled``
via a lazy self-import so tests that monkeypatch
``agent_server.skills_service.<name>`` are honored, matching this module's
behavior from before the split.
"""

from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

from agent_server.models import (
    SkillBatchAction,
    SkillBatchActionFailure,
    SkillBatchActionResponse,
    SkillMutationResponse,
    SkillSummary,
)


class MutateMixin:
    def install(self, source: str) -> SkillMutationResponse:
        from agent_server import skills_service as _skills_service

        # Same path as `sandwalk skills add`: git/archive first, then npx fallback.
        # Nested layouts (e.g. skills/.curated/<name>) are resolved by skill name.
        result = _skills_service.install_skill(source)
        return SkillMutationResponse(
            ok=bool(result.get("ok")),
            summary=str(result.get("summary") or ""),
            installed=[str(item) for item in result.get("installed") or []],
        )

    def remove(self, name: str) -> SkillMutationResponse:
        from agent_server import skills_service as _skills_service

        result = _skills_service.remove_skill(name)
        return SkillMutationResponse(
            ok=bool(result.get("ok")),
            summary=str(result.get("summary") or ""),
        )

    def upgrade(self) -> SkillMutationResponse:
        from agent_server import skills_service as _skills_service

        result = _skills_service.upgrade_skills()
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
        from agent_server import skills_service as _skills_service

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

            result = _skills_service.install_skill(str(source_path))
            return SkillMutationResponse(
                ok=bool(result.get("ok")),
                summary=str(result.get("summary") or ""),
                installed=[str(item) for item in result.get("installed") or []],
            )

    def set_enabled(self, name: str, enabled: bool) -> SkillSummary | None:
        from agent_server import skills_service as _skills_service

        result = _skills_service.set_skill_enabled(name, enabled)
        if not result.get("ok"):
            return None
        info = _skills_service.skill_info(name)
        if info is None:
            return None
        return self._summary(info)

    def batch_action(self, action: SkillBatchAction, names: list[str]) -> SkillBatchActionResponse:
        from agent_server import skills_service as _skills_service

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
                result = _skills_service.remove_skill(name)
            else:
                result = _skills_service.set_skill_enabled(name, enabled=(action == "enable"))
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
