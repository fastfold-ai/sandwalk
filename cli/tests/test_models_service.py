"""Tests for models catalog + profile management APIs."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent.config import Config
from agent.model_catalog import (
    CATALOG_DEFAULTS_VERSION,
    DEFAULT_DISABLED_MODELS,
    cloud_catalog_models,
)
from agent_server.app import create_app
from agent_server.models import CreateAgentModelRequest, UpdateAgentModelRequest, UpsertModelProfileRequest
from agent_server.models_service import ModelsService


@pytest.fixture()
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import agent.config as config_mod

    config_dir = tmp_path / ".fastfold-cli"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.json"
    monkeypatch.setattr(config_mod, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config_mod, "CONFIG_FILE", config_file)
    monkeypatch.setattr(config_mod, "CONFIG_BACKUP_FILE", config_dir / "config.json.bak")
    cfg = Config(
        {
            "llm.provider": "anthropic",
            "llm.model": "claude-sonnet-5",
            "llm.hidden_models": [],
            # Start already-migrated so tests control the hidden list explicitly.
            "llm.catalog_defaults_version": CATALOG_DEFAULTS_VERSION,
        }
    )
    cfg.save()
    return cfg


def test_cloud_catalog_excludes_custom_entry():
    ids = {item["id"] for item in cloud_catalog_models()}
    assert "__custom_openai_compatible__" not in ids
    assert "claude-sonnet-5" in ids
    assert "gpt-5.5" in ids


def test_catalog_defaults_migration(tmp_path, monkeypatch):
    import agent.config as config_mod

    config_dir = tmp_path / ".fastfold-cli"
    config_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config_mod, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config_mod, "CONFIG_FILE", config_dir / "config.json")
    monkeypatch.setattr(
        config_mod, "CONFIG_BACKUP_FILE", config_dir / "config.json.bak"
    )
    # Legacy config without the version marker triggers the one-time migration.
    Config({"llm.provider": "anthropic", "llm.hidden_models": []}).save()

    migrated = Config.load()
    hidden = set(migrated.hidden_models())
    assert DEFAULT_DISABLED_MODELS.issubset(hidden)
    # New-generation models remain enabled by default.
    assert "claude-sonnet-5" not in hidden
    assert "gpt-5.6-sol" not in hidden
    assert "gpt-5.5" not in hidden


def test_hidden_models_helpers(isolated_config: Config):
    cfg = Config.load()
    assert cfg.hidden_models() == []
    cfg.set_model_hidden("gpt-5.5", True)
    cfg.save()
    reloaded = Config.load()
    assert reloaded.is_model_hidden("gpt-5.5")
    assert "gpt-5.5" in reloaded.hidden_models()
    reloaded.set_model_hidden("gpt-5.5", False)
    reloaded.save()
    assert "gpt-5.5" not in Config.load().hidden_models()


def test_models_service_toggle_and_profile_crud(isolated_config: Config, monkeypatch: pytest.MonkeyPatch):
    service = ModelsService()

    def fake_probe(*, base_url: str, backend: str, api_key: str | None):
        return {
            "health": "healthy",
            "models": ["local-model-a"],
            "models_source": "/v1/models",
            "models_path": "/v1/models",
            "error": None,
        }

    monkeypatch.setattr(
        "agent_server.models_service.probe_compatible_profile",
        fake_probe,
    )

    listed = service.list_models(discover=False)
    assert listed.count >= len(cloud_catalog_models())
    cloud_ids = {item.id for item in listed.data if item.source == "cloud"}
    assert "claude-sonnet-4-5-20250929" in cloud_ids

    updated = service.update_model(
        "claude-sonnet-4-5-20250929",
        UpdateAgentModelRequest(enabled=False),
    )
    assert updated.enabled is False
    enabled_only = service.list_models(enabled_only=True, discover=False)
    assert all(item.id != "claude-sonnet-4-5-20250929" for item in enabled_only.data)

    created = service.upsert_profile(
        UpsertModelProfileRequest(
            label="Ollama Lab",
            backend="ollama",
            base_url="http://127.0.0.1:11434/v1",
            default_model="llama3.1",
        )
    )
    assert created.backend == "ollama"
    assert created.is_cloud is False

    profiles = service.list_profiles(include_cloud=False)
    assert any(item.id == created.id for item in profiles.data)

    discovered = service.list_models(discover=True)
    assert any(item.id == "local-model-a" and item.profile_id == created.id for item in discovered.data)

    with pytest.raises(ValueError, match="cannot be deleted"):
        service.delete_profile("openai_cloud")

    assert service.delete_profile(created.id) is True
    assert service.get_profile(created.id) is None


def test_models_http_routes(isolated_config: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "agent_server.models_service.probe_compatible_profile",
        lambda **kwargs: {
            "health": "healthy",
            "models": ["route-model"],
            "models_source": "/v1/models",
            "models_path": "/v1/models",
            "error": None,
        },
    )
    app = create_app(store_path=tmp_path / "agent.db", allowed_hosts=["testserver"])
    client = TestClient(app)

    models = client.get("/v1/models", params={"discover": "false"})
    assert models.status_code == 200
    payload = models.json()
    assert payload["count"] > 0

    model_id = "gpt-5.5"
    patched = client.patch(f"/v1/models/{model_id}", json={"enabled": False})
    assert patched.status_code == 200
    assert patched.json()["enabled"] is False

    created = client.post(
        "/v1/model-profiles",
        json={
            "label": "LM Studio",
            "backend": "lm_studio",
            "base_url": "http://127.0.0.1:1234/v1",
            "default_model": "local-chat",
        },
    )
    assert created.status_code == 201
    profile_id = created.json()["id"]

    probed = client.post(f"/v1/model-profiles/{profile_id}/probe")
    assert probed.status_code == 200
    assert "route-model" in probed.json()["models"]

    deleted = client.delete(f"/v1/model-profiles/{profile_id}")
    assert deleted.status_code == 200
    assert deleted.json()["ok"] is True

    blocked = client.delete("/v1/model-profiles/openai_cloud")
    assert blocked.status_code == 400


def test_custom_cloud_models(isolated_config: Config):
    service = ModelsService()
    created = service.create_custom_model(
        CreateAgentModelRequest(
            id="gpt-custom-lab",
            provider="openai",
            label="GPT Custom Lab",
        )
    )
    assert created.source == "custom"
    assert created.provider == "openai"
    assert created.id == "gpt-custom-lab"

    listed = service.list_models(discover=False)
    assert any(item.id == "gpt-custom-lab" and item.source == "custom" for item in listed.data)

    with pytest.raises(ValueError, match="already exists"):
        service.create_custom_model(
            CreateAgentModelRequest(
                id="gpt-custom-lab",
                provider="openai",
            )
        )

    with pytest.raises(ValueError, match="built-in catalog"):
        service.create_custom_model(
            CreateAgentModelRequest(
                id="gpt-5.5",
                provider="openai",
            )
        )

    assert service.delete_custom_model("gpt-custom-lab") is True
    listed_after = service.list_models(discover=False)
    assert all(item.id != "gpt-custom-lab" for item in listed_after.data)


def test_opencode_discovers_models_when_key_set(
    isolated_config: Config, monkeypatch: pytest.MonkeyPatch
):
    from agent.config import Config as ConfigCls

    cfg = ConfigCls.load()
    cfg.set("llm.opencode_api_key", "oc-test-key")
    cfg.save()

    monkeypatch.setattr(
        "agent_server.models_service.probe_compatible_profile",
        lambda **_kwargs: {
            "health": "ok",
            "models": ["kimi-k2.7-code", "glm-5.2", "deepseek-v4-flash"],
            "models_source": "v1_models",
            "error": None,
        },
    )

    service = ModelsService()
    listed = service.list_models(discover=True)
    opencode_ids = {
        item.id for item in listed.data if item.provider == "opencode"
    }
    assert "kimi-k2.7-code" in opencode_ids
    assert "glm-5.2" in opencode_ids
    kimi = next(item for item in listed.data if item.id == "kimi-k2.7-code")
    assert kimi.enabled is True
    assert kimi.source == "cloud"
    assert kimi.label == "Kimi K2.7 Code"

    # No models when discover=False (static catalog has no opencode entries).
    static = service.list_models(discover=False)
    assert all(item.provider != "opencode" for item in static.data)


def test_format_discovered_model_label():
    from agent.model_catalog import (
        format_discovered_model_label,
        opencode_model_uses_anthropic,
    )

    assert format_discovered_model_label("kimi-k2.7-code") == "Kimi K2.7 Code"
    assert format_discovered_model_label("deepseek-v4-flash") == "Deepseek V4 Flash"
    assert opencode_model_uses_anthropic("claude-sonnet-5") is True
    assert opencode_model_uses_anthropic("qwen3.7-plus") is True
    assert opencode_model_uses_anthropic("minimax-m3") is False
    assert opencode_model_uses_anthropic("kimi-k2.7-code") is False


def test_openai_model_requires_responses_api():
    from agent.model_catalog import openai_model_requires_responses_api

    assert openai_model_requires_responses_api("gpt-5.3-codex") is True
    assert openai_model_requires_responses_api("gpt-5.2-codex") is True
    assert openai_model_requires_responses_api("gpt-5.1-codex-mini") is True
    assert openai_model_requires_responses_api("gpt-5.5") is False
    assert openai_model_requires_responses_api("gpt-4o") is False


def test_custom_models_http_routes(isolated_config: Config, tmp_path: Path):
    app = create_app(store_path=tmp_path / "agent-custom.db", allowed_hosts=["testserver"])
    client = TestClient(app)

    created = client.post(
        "/v1/models",
        json={"id": "claude-custom-x", "provider": "anthropic", "label": "Claude Custom"},
    )
    assert created.status_code == 201
    assert created.json()["source"] == "custom"

    models = client.get("/v1/models", params={"discover": "false"})
    assert models.status_code == 200
    assert any(item["id"] == "claude-custom-x" for item in models.json()["data"])

    deleted = client.delete("/v1/models/claude-custom-x")
    assert deleted.status_code == 200
    assert deleted.json()["ok"] is True

    missing = client.delete("/v1/models/claude-custom-x")
    assert missing.status_code == 404
