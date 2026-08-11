"""HTTP coverage for integrations and specialists routes."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from agent.config import Config
from agent_server.app import create_app


def test_integrations_http_crud(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent.config.CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr("agent.config.CONFIG_FILE", tmp_path / "cfg" / "config.json")
    (tmp_path / "cfg").mkdir(parents=True, exist_ok=True)
    Config({}).save()

    app = create_app(store_path=tmp_path / "agent.db", allowed_hosts=["testserver"])
    with TestClient(app) as client:
        listing = client.get("/v1/integrations")
        assert listing.status_code == 200
        keys = {item["key"] for item in listing.json()["data"]}
        assert "anthropic" in keys

        detail = client.get("/v1/integrations/anthropic")
        assert detail.status_code == 200

        ibm = client.get("/v1/integrations/ibm-rxn")
        assert ibm.status_code == 200
        assert ibm.json()["unlocks"][0]["id"] == "chemistry.retrosynthesis"
        assert ibm.json()["unlocks"][0]["requirement"] == "built_in"

        installed_cli = tmp_path / "bin" / "boltz-api"
        monkeypatch.setattr(
            "agent_server.integrations_service.capabilities.install_boltz_cli",
            lambda: installed_cli,
        )
        monkeypatch.setattr(
            "agent_server.integrations_service.provider.find_boltz_cli",
            lambda: installed_cli,
        )
        installed = client.post(
            "/v1/integrations/boltz/capabilities/boltz-api-cli/install"
        )
        assert installed.status_code == 200, installed.text
        boltz_cli = next(
            unlock
            for unlock in installed.json()["unlocks"]
            if unlock["id"] == "boltz-api-cli"
        )
        assert boltz_cli["installed"] is True
        assert boltz_cli["statusDetail"] == str(installed_cli)

        installed_npx = tmp_path / "bin" / "npx"
        monkeypatch.setattr(
            "agent_server.integrations_service.capabilities.install_npx_skills_cli",
            lambda: installed_npx,
        )
        monkeypatch.setattr(
            "agent_server.integrations_service.provider.find_npx_skills_cli",
            lambda: installed_npx,
        )
        skills_cli = client.post(
            "/v1/integrations/skills-sh/capabilities/npx-skills-cli/install"
        )
        assert skills_cli.status_code == 200, skills_cli.text
        npx_unlock = next(
            unlock
            for unlock in skills_cli.json()["unlocks"]
            if unlock["id"] == "npx-skills-cli"
        )
        assert npx_unlock["installed"] is True
        assert npx_unlock["statusDetail"] == str(installed_npx)

        updated = client.put(
            "/v1/integrations/anthropic",
            json={"value": "sk-ant-api03-validkey"},
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["configured"] is True
        assert updated.json()["fields"][0]["updatedAt"] is not None

        from agent.doctor.model_provider_http import ModelsProbeResult

        monkeypatch.setattr(
            "agent_server.integrations_service.mutate.probe_llm_api_key",
            lambda *_a, **_k: ModelsProbeResult(
                ok=True,
                message="Anthropic API key works (1 models).",
                model_count=1,
                status_code=200,
            ),
        )

        validated = client.post("/v1/integrations/anthropic/validate")
        assert validated.status_code == 200
        body = validated.json()
        assert body["ok"] is True
        assert "API key works" in body["message"]

        revealed = client.get("/v1/integrations/anthropic/secret")
        assert revealed.status_code == 200
        secret_body = revealed.json()
        assert secret_body["configured"] is True
        assert secret_body["value"] == "sk-ant-api03-validkey"
        assert secret_body["envVar"]

        removed = client.delete("/v1/integrations/anthropic")
        assert removed.status_code == 200
        assert removed.json()["configured"] is False
        # Clearing the key also turns that provider's models off.
        hidden = set(Config.load().hidden_models())
        assert any(mid.startswith("claude-") for mid in hidden)

        missing = client.get("/v1/integrations/not-real")
        assert missing.status_code == 404


def test_specialists_http_crud(tmp_path: Path):
    app = create_app(store_path=tmp_path / "agent.db", allowed_hosts=["testserver"])
    with TestClient(app) as client:
        seeded = client.get("/v1/specialists")
        assert seeded.status_code == 200
        assert len(seeded.json()["data"]) >= 1

        created = client.post(
            "/v1/specialists",
            json={
                "name": "HTTP Specialist",
                "slug": "http-specialist",
                "description": "Test",
                "skillNames": ["fold"],
            },
        )
        assert created.status_code == 201
        specialist_id = created.json()["id"]

        fetched = client.get(f"/v1/specialists/{specialist_id}")
        assert fetched.status_code == 200

        patched = client.patch(
            f"/v1/specialists/{specialist_id}",
            json={"name": "Updated Specialist", "enabled": False},
        )
        assert patched.status_code == 200
        assert patched.json()["enabled"] is False

        deleted = client.delete(f"/v1/specialists/{specialist_id}")
        assert deleted.status_code == 200
        assert deleted.json()["deleted"] is True


def test_mcp_catalog_and_skills_routes(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "agent_server.skills_service.SkillsService.list",
        lambda self: [],
    )
    monkeypatch.setattr(
        "agent_server.skills_service.SkillsService.suggested_sources",
        lambda self: [],
    )

    app = create_app(store_path=tmp_path / "agent.db", allowed_hosts=["testserver"])
    with TestClient(app) as client:
        catalog = client.get("/v1/mcp-servers/catalog")
        assert catalog.status_code == 200
        assert len(catalog.json()["data"]) >= 1

        skills = client.get("/v1/skills")
        assert skills.status_code == 200
        assert skills.json()["data"] == []

        sources = client.get("/v1/skills/sources")
        assert sources.status_code == 200
