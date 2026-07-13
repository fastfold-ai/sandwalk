"""Unit tests for agent_server.skills_service."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from agent_server.skills_service import SkillsService


def _skill_info(**kwargs):
    defaults = {
        "name": "demo-skill",
        "description": "Demo",
        "tags": ["bio"],
        "source": "local",
        "author": "tester",
        "version": "1.0",
        "updated_at": "2026-01-01",
        "icon": "",
        "enabled": True,
        "path": None,
        "directory": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_list_and_suggested_sources(monkeypatch):
    monkeypatch.setattr(
        "agent_server.skills_service.list_skills",
        lambda: [_skill_info(name="fold", description="Fold proteins")],
    )
    svc = SkillsService()
    items = svc.list()
    assert len(items) == 1
    assert items[0].name == "fold"
    sources = svc.suggested_sources()
    assert sources
    assert all(source.provider for source in sources)


def test_icon_source_http_and_file(tmp_path: Path, monkeypatch):
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    (skill_dir / "icon.svg").write_text("<svg/>", encoding="utf-8")
    info = _skill_info(
        name="my-skill",
        icon="https://cdn.example/icon.png",
        directory=str(skill_dir),
    )
    assert SkillsService._icon_source(info) == "https://cdn.example/icon.png"

    info_local = _skill_info(name="my-skill", icon="", directory=str(skill_dir))
    assert SkillsService._icon_source(info_local) == "/v1/skills/my-skill/icon"


def test_get_skill_detail(tmp_path: Path, monkeypatch):
    skill_dir = tmp_path / "detail-skill"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("# Skill body", encoding="utf-8")
    info = _skill_info(
        name="detail-skill",
        path=skill_md,
        directory=str(skill_dir),
    )
    monkeypatch.setattr("agent_server.skills_service.skill_info", lambda name: info if name == "detail-skill" else None)
    svc = SkillsService()
    detail = svc.get("detail-skill")
    assert detail is not None
    assert "Skill body" in detail.content
    assert svc.get("missing") is None


def test_install_remove_upgrade(monkeypatch):
    monkeypatch.setattr(
        "agent_server.skills_service.install_skill",
        lambda source: {"ok": True, "summary": "installed", "installed": ["fold"]},
    )
    monkeypatch.setattr(
        "agent_server.skills_service.remove_skill",
        lambda name: {"ok": True, "summary": "removed"},
    )
    monkeypatch.setattr(
        "agent_server.skills_service.upgrade_skills",
        lambda: {"ok": True, "summary": "upgraded", "added": ["a"], "updated": ["b"], "failed": []},
    )
    svc = SkillsService()
    assert svc.install("fold").ok is True
    assert svc.remove("fold").ok is True
    upgraded = svc.upgrade()
    assert upgraded.ok is True
    assert "a" in upgraded.installed


def test_set_enabled_and_batch(monkeypatch):
    info = _skill_info(name="batch-skill", enabled=False)
    monkeypatch.setattr(
        "agent_server.skills_service.set_skill_enabled",
        lambda name, enabled: {"ok": True, "summary": "ok"},
    )
    monkeypatch.setattr(
        "agent_server.skills_service.remove_skill",
        lambda name: {"ok": name == "good", "summary": "gone" if name == "good" else "missing"},
    )
    monkeypatch.setattr(
        "agent_server.skills_service.skill_info",
        lambda name: info if name == "batch-skill" else None,
    )
    svc = SkillsService()
    summary = svc.set_enabled("batch-skill", True)
    assert summary is not None
    assert summary.name == "batch-skill"

    batch = svc.batch_action("remove", ["good", "good", "bad"])
    assert batch.requested == 2
    assert "good" in batch.succeeded
    assert any(item.name == "bad" for item in batch.failed)


def test_search_catalog_short_query(monkeypatch):
    svc = SkillsService()
    assert svc.search_catalog("a") == []


def test_search_catalog_with_mock(monkeypatch):
    payload = {
        "data": [
            {
                "id": "1",
                "slug": "fold",
                "name": "Fold",
                "source": "fastfold-ai/skills",
                "installs": 10,
                "sourceType": "git",
            }
        ]
    }

    monkeypatch.setattr(
        "agent_server.skills_service.SkillsService._skills_sh_token",
        lambda self: "token",
    )
    monkeypatch.setattr(
        "agent_server.skills_service.SkillsService._skills_sh_request_json",
        lambda self, endpoint, operation="": payload,
    )
    svc = SkillsService()
    results = svc.search_catalog("fold", limit=5)
    assert len(results) == 1
    assert results[0].slug == "fold"


def test_catalog_detail_and_audit(monkeypatch):
    monkeypatch.setattr(
        "agent_server.skills_service.SkillsService._skills_sh_token",
        lambda self: "token",
    )
    monkeypatch.setattr(
        "agent_server.skills_service.SkillsService._skills_sh_request_json",
        lambda self, endpoint, operation="": {
            "id": "src/fold",
            "source": "src",
            "slug": "fold",
            "installs": 1,
            "files": [{"path": "SKILL.md", "contents": "# Fold"}],
            "audits": [
                {
                    "provider": "bot",
                    "slug": "fold",
                    "status": "pass",
                    "summary": "ok",
                    "categories": ["safe"],
                }
            ],
        },
    )
    svc = SkillsService()
    detail = svc.get_catalog_detail("src", "fold")
    assert detail.slug == "fold"
    assert detail.files and detail.files[0].path == "SKILL.md"

    audit = svc.get_catalog_audit("src", "fold")
    assert audit.audits[0].status == "pass"


def test_install_uploaded_zip(tmp_path: Path, monkeypatch):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("demo-skill/SKILL.md", "# Demo")
    data = buf.getvalue()

    monkeypatch.setattr(
        "agent_server.skills_service.install_skill",
        lambda source: {"ok": True, "summary": "ok", "installed": ["demo-skill"]},
    )
    svc = SkillsService()
    result = svc.install_uploaded_file("bundle.zip", data)
    assert result.ok is True
    assert "demo-skill" in result.installed


def test_install_uploaded_md_and_errors(monkeypatch):
    svc = SkillsService()
    empty = svc.install_uploaded_file("x.zip", b"")
    assert empty.ok is False

    monkeypatch.setattr(
        "agent_server.skills_service.install_skill",
        lambda source: {"ok": True, "summary": "ok", "installed": ["solo"]},
    )
    md = svc.install_uploaded_file("solo/SKILL.md", b"# Solo")
    assert md.ok is True

    bad = svc.install_uploaded_file("file.txt", b"data")
    assert bad.ok is False


def test_skills_sh_token_missing(monkeypatch):
    monkeypatch.setattr(
        "agent_server.skills_service.Config.load",
        lambda: MagicMock(get=lambda key, default=None: default),
    )
    monkeypatch.delenv("VERCEL_OIDC_TOKEN", raising=False)
    svc = SkillsService()
    with pytest.raises(RuntimeError, match="Vercel"):
        svc._skills_sh_token()
