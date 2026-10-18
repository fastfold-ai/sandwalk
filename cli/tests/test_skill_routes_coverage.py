"""Skill HTTP routes with a fake skills service."""

from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent_server.models.skills import (
    CatalogLeaderboard,
    CatalogSkill,
    CatalogSkillAudit,
    CatalogSkillDetail,
    SkillBatchActionResponse,
    SkillDepsInstallResponse,
    SkillDepsStatus,
    SkillDetail,
    SkillMutationResponse,
    SkillSource,
)
from agent_server.routes import skills as skill_routes


def _detail(name="fold"):
    return SkillDetail(
        name=name,
        description="d",
        source="local",
        author="me",
        content="# skill",
        directory="/skills/fold",
    )


class _Skills:
    def list(self):
        return [_detail()]

    def suggested_sources(self):
        return [SkillSource(provider="github", source="org/repo", url="https://example.com", description="src")]

    def search_catalog(self, q, limit):
        if q == "down":
            raise RuntimeError("catalog down")
        return [CatalogSkill(id="1", slug=q, name=q, source="org")]

    def list_catalog_leaderboard(self, view, page, per_page):
        if view == "hot":
            raise RuntimeError("leaderboard down")
        return CatalogLeaderboard(data=[], view=view, page=page, per_page=per_page)

    def get_catalog_detail(self, source, skill):
        if skill == "bad":
            raise ValueError("bad skill")
        if skill == "missing":
            raise LookupError("")
        if skill == "down":
            raise RuntimeError("detail down")
        return CatalogSkillDetail(id="1", source=source, slug=skill)

    def get_catalog_audit(self, source, skill):
        if skill == "bad":
            raise ValueError("bad")
        if skill == "down":
            raise RuntimeError("audit down")
        return CatalogSkillAudit(id="1", source=source, slug=skill)

    def get(self, name):
        if name == "missing":
            return None
        return _detail(name)

    def get_icon_path(self, name):
        if name == "missing":
            return None
        from pathlib import Path
        path = Path("/tmp") / "skill-icon.txt"
        path.write_text("icon")
        return path

    def get_deps(self, name):
        if name == "missing":
            raise LookupError("no skill")
        return SkillDepsStatus(adapter_id="pip", skill_name=name, status="ok", summary="ready")

    def doctor_deps(self, name):
        if name == "missing":
            raise LookupError("no skill")
        return self.get_deps(name)

    def install_deps(self, name, force=False):
        if name == "missing":
            raise LookupError("no skill")
        status = self.get_deps(name)
        if name == "fail":
            return SkillDepsInstallResponse(ok=False, summary="cannot install", status=status)
        return SkillDepsInstallResponse(ok=True, summary="installed", status=status)

    def set_enabled(self, name, enabled):
        if name == "missing":
            return None
        return _detail(name)

    def batch_action(self, action, names):
        return SkillBatchActionResponse(
            ok=True,
            action=action,
            requested=len(names),
            succeeded=list(names),
            summary="done",
        )

    def install(self, source):
        if source == "bad":
            return SkillMutationResponse(ok=False, summary="nope")
        return SkillMutationResponse(ok=True, summary="installed", installed=[source])

    def install_uploaded_file(self, filename, data):
        if not data:
            return SkillMutationResponse(ok=False, summary="empty")
        return SkillMutationResponse(ok=True, summary=filename or "file")

    def remove(self, name):
        if name == "missing":
            return SkillMutationResponse(ok=False, summary="missing")
        return SkillMutationResponse(ok=True, summary="removed")

    def upgrade(self):
        return SkillMutationResponse(ok=True, summary="upgraded")


def test_skill_routes(monkeypatch):
    monkeypatch.setattr("agent_server.ttl_cache.invalidate", lambda prefix: None)
    monkeypatch.setattr("agent_server.ttl_cache.cached", lambda key, ttl, fn: fn())
    app = FastAPI()
    skill_routes.register_skill_routes(app, SimpleNamespace(skills_service=_Skills()))
    client = TestClient(app)

    assert client.get("/v1/skills").status_code == 200
    assert client.get("/v1/skills/sources").status_code == 200
    assert client.get("/v1/skills/catalog/search", params={"q": "ab"}).status_code == 200
    assert client.get("/v1/skills/catalog/search", params={"q": "down"}).status_code == 502
    assert client.get("/v1/skills/catalog/leaderboard").status_code == 200
    assert client.get("/v1/skills/catalog/leaderboard", params={"view": "hot"}).status_code == 502
    assert client.get("/v1/skills/catalog/detail", params={"source": "org", "skill": "fold"}).status_code == 200
    assert client.get("/v1/skills/catalog/detail", params={"source": "org", "skill": "bad"}).status_code == 400
    assert client.get("/v1/skills/catalog/detail", params={"source": "org", "skill": "missing"}).status_code == 404
    assert client.get("/v1/skills/catalog/detail", params={"source": "org", "skill": "down"}).status_code == 502
    assert client.get("/v1/skills/catalog/audit", params={"source": "org", "skill": "fold"}).status_code == 200
    assert client.get("/v1/skills/catalog/audit", params={"source": "org", "skill": "bad"}).status_code == 400
    assert client.get("/v1/skills/catalog/audit", params={"source": "org", "skill": "down"}).status_code == 502

    assert client.get("/v1/skills/fold").status_code == 200
    assert client.get("/v1/skills/missing").status_code == 404
    icon = client.get("/v1/skills/fold/icon")
    assert icon.status_code == 200
    assert client.get("/v1/skills/missing/icon").status_code == 404
    assert client.get("/v1/skills/fold/deps").status_code == 200
    assert client.get("/v1/skills/missing/deps").status_code == 404
    assert client.get("/v1/skills/fold/deps/doctor").status_code == 200
    assert client.get("/v1/skills/missing/deps/doctor").status_code == 404
    assert client.post("/v1/skills/fold/deps/install", json={"force": True}).status_code == 200
    assert client.post("/v1/skills/fail/deps/install", json={}).status_code == 400
    assert client.post("/v1/skills/missing/deps/install").status_code == 404

    assert client.patch("/v1/skills/fold", json={}).status_code == 400
    assert client.patch("/v1/skills/missing", json={"enabled": False}).status_code == 404
    assert client.patch("/v1/skills/fold", json={"enabled": False}).status_code == 200
    batch = client.post("/v1/skills/batch", json={"action": "enable", "names": ["fold"]})
    assert batch.status_code == 200
    assert client.post("/v1/skills", json={"source": "org/repo"}).status_code == 200
    assert client.post("/v1/skills", json={"source": "bad"}).status_code == 400
    uploaded = client.post("/v1/skills/upload", files={"file": ("skill.md", b"# hi", "text/markdown")})
    assert uploaded.status_code == 200
    empty = client.post("/v1/skills/upload", files={"file": ("skill.md", b"", "text/markdown")})
    assert empty.status_code == 400
    assert client.delete("/v1/skills/fold").status_code == 200
    assert client.delete("/v1/skills/missing").status_code == 400
    assert client.post("/v1/skills/upgrade").status_code == 200
