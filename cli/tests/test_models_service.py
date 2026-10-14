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
from agent_server.models import (
    CreateAgentModelRequest,
    UpdateAgentModelRequest,
    UpsertModelProfileRequest,
)
from agent_server.models_service import ModelsService


@pytest.fixture()
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import agent.config as config_mod

    config_dir = tmp_path / ".sandwalk"
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
    assert "claude-opus-5" in ids
    assert "claude-opus-5-5" in ids
    assert "claude-sonnet-5" in ids
    assert "claude-fable-5-1" in ids
    assert "gpt-5.5" in ids
    assert "gpt-6-astra" in ids


def test_catalog_defaults_migration(tmp_path, monkeypatch):
    import agent.config as config_mod

    config_dir = tmp_path / ".sandwalk"
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
    assert "claude-opus-5" not in hidden
    assert "claude-opus-5-5" not in hidden
    assert "claude-sonnet-5" not in hidden
    assert "claude-fable-5-1" not in hidden
    assert "claude-opus-4-8" in hidden
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
    assert any(
        item.id == "local-model-a"
        and item.profile_id == created.id
        and item.backend == "ollama"
        for item in discovered.data
    )

    preview = service.discover_endpoint(
        backend="ollama",
        base_url="http://127.0.0.1:11434/v1",
    )
    assert preview.profile_id == "preview"
    assert preview.models == ["local-model-a"]
    assert preview.health == "healthy"

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
            "api_key": "sk-local-test-secret",
        },
    )
    assert created.status_code == 201
    profile_id = created.json()["id"]
    assert created.json()["hasApiKey"] is True
    assert created.json()["apiKeyPreview"]

    revealed = client.get(f"/v1/model-profiles/{profile_id}/secret")
    assert revealed.status_code == 200
    secret_body = revealed.json()
    assert secret_body["configured"] is True
    assert secret_body["value"] == "sk-local-test-secret"

    probed = client.post(f"/v1/model-profiles/{profile_id}/probe")
    assert probed.status_code == 200
    assert "route-model" in probed.json()["models"]

    discovered = client.post(
        "/v1/model-profiles/discover",
        json={
            "backend": "lm_studio",
            "baseUrl": "http://127.0.0.1:1234/v1",
        },
    )
    assert discovered.status_code == 200
    body = discovered.json()
    assert body["profileId"] == "preview"
    assert "route-model" in body["models"]

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
    # Discovered Zen ids surface under provider=opencode even when the same
    # bare id is also curated for Moonshot / DeepSeek / Qwen.
    assert opencode_ids == {"kimi-k2.7-code", "glm-5.2", "deepseek-v4-flash"}
    assert any(
        item.id == "kimi-k2.7-code" and item.provider == "moonshot"
        for item in listed.data
    )
    glm = next(
        item
        for item in listed.data
        if item.id == "glm-5.2" and item.provider == "opencode"
    )
    # Enabled even when Qwen/Moonshot/DeepSeek lack keys (provider-scoped hide).
    assert glm.enabled is True
    assert glm.source == "cloud"
    assert glm.label == "GLM 5.2"
    kimi = next(
        item
        for item in listed.data
        if item.id == "kimi-k2.7-code" and item.provider == "opencode"
    )
    assert kimi.enabled is True

    # No models when discover=False (static catalog has no opencode entries).
    static = service.list_models(discover=False)
    assert all(item.provider != "opencode" for item in static.data)


def test_shared_model_ids_can_exist_under_multiple_providers(
    isolated_config: Config, monkeypatch: pytest.MonkeyPatch
):
    """Same bare id (kimi-k3, glm-5.2, deepseek-v4-pro) across providers."""
    from agent.config import Config as ConfigCls
    from agent_server.models import UpdateAgentModelRequest

    cfg = ConfigCls.load()
    cfg.set("llm.opencode_api_key", "oc-test-key")
    cfg.set("llm.qwen_api_key", "qwen-test-key")
    cfg.set("llm.moonshot_api_key", "moonshot-test-key")
    cfg.set("llm.deepseek_api_key", "deepseek-test-key")
    cfg.save()

    monkeypatch.setattr(
        "agent_server.models_service.probe_compatible_profile",
        lambda **_kwargs: {
            "health": "ok",
            "models": ["kimi-k3", "glm-5.2", "deepseek-v4-pro"],
            "models_source": "v1_models",
            "error": None,
        },
    )

    service = ModelsService()
    listed = service.list_models(discover=True)

    kimi_rows = [item for item in listed.data if item.id == "kimi-k3"]
    providers = {item.provider for item in kimi_rows}
    assert {"moonshot", "opencode"} <= providers
    assert all(item.enabled for item in kimi_rows)

    glm_rows = [item for item in listed.data if item.id == "glm-5.2"]
    assert {"qwen", "opencode"} <= {item.provider for item in glm_rows}

    deepseek_rows = [item for item in listed.data if item.id == "deepseek-v4-pro"]
    assert {"deepseek", "qwen", "opencode"} <= {
        item.provider for item in deepseek_rows
    }

    # Toggling OpenCode off must not hide the Moonshot row.
    service.update_model(
        "kimi-k3",
        UpdateAgentModelRequest(enabled=False, provider="opencode"),
    )
    after = service.list_models(discover=True)
    assert (
        next(
            item
            for item in after.data
            if item.id == "kimi-k3" and item.provider == "opencode"
        ).enabled
        is False
    )
    assert (
        next(
            item
            for item in after.data
            if item.id == "kimi-k3" and item.provider == "moonshot"
        ).enabled
        is True
    )


def test_format_discovered_model_label():
    from agent.model_catalog import (
        format_discovered_model_label,
        opencode_model_uses_anthropic,
    )

    assert format_discovered_model_label("kimi-k2.7-code") == "Kimi K2.7 Code"
    assert format_discovered_model_label("deepseek-v4-flash") == "DeepSeek V4 Flash"
    assert (
        format_discovered_model_label("deepseek/deepseek-v4-flash")
        == "DeepSeek V4 Flash 0423"
    )
    assert (
        format_discovered_model_label("deepseek/deepseek-v4-flash-0731")
        == "DeepSeek V4 Flash 0731"
    )
    assert format_discovered_model_label("deepseek-v4-flash-0731") == "DeepSeek V4 Flash 0731"
    assert format_discovered_model_label("gpt-5.1") == "GPT 5.1"
    assert format_discovered_model_label("gpt-5.6-luna") == "GPT 5.6 Luna"
    assert format_discovered_model_label("glm-5") == "GLM 5"
    assert format_discovered_model_label("glm-5.2") == "GLM 5.2"
    assert opencode_model_uses_anthropic("claude-sonnet-5") is True
    assert opencode_model_uses_anthropic("qwen3.7-plus") is True
    assert opencode_model_uses_anthropic("minimax-m3") is False
    assert opencode_model_uses_anthropic("kimi-k2.7-code") is False


def test_openai_model_requires_responses_api():
    from agent.model_catalog import openai_model_requires_responses_api

    assert openai_model_requires_responses_api("gpt-5.3-codex") is True
    assert openai_model_requires_responses_api("gpt-5.2-codex") is True
    assert openai_model_requires_responses_api("gpt-5.1-codex-mini") is True
    assert openai_model_requires_responses_api("gpt-5.6") is True
    assert openai_model_requires_responses_api("gpt-5.6-sol") is True
    assert openai_model_requires_responses_api("gpt-6-astra") is True
    assert openai_model_requires_responses_api("gpt-5.6-terra") is True
    assert openai_model_requires_responses_api("gpt-5.5") is True
    assert openai_model_requires_responses_api("gpt-5.4-mini") is True
    assert openai_model_requires_responses_api("gpt-5.4-pro") is True
    assert openai_model_requires_responses_api("o3-mini") is True
    assert openai_model_requires_responses_api("gpt-4o") is False
    assert openai_model_requires_responses_api("gpt-5-chat-latest") is False


def test_model_supports_reasoning_effort():
    from agent.model_catalog import (
        effective_reasoning_effort,
        model_supports_reasoning_effort,
        reasoning_effort_options,
    )

    assert model_supports_reasoning_effort("openai", "gpt-5.6-sol") is True
    assert model_supports_reasoning_effort("openai", "gpt-6-astra") is True
    assert model_supports_reasoning_effort("openai", "o3-mini") is True
    assert model_supports_reasoning_effort("opencode", "gpt-5.2") is True
    assert model_supports_reasoning_effort("anthropic", "claude-opus-5") is True
    assert model_supports_reasoning_effort("anthropic", "claude-opus-5-5") is True
    assert model_supports_reasoning_effort("anthropic", "claude-opus-4-8") is True
    assert model_supports_reasoning_effort("anthropic", "claude-sonnet-5") is True
    assert model_supports_reasoning_effort("anthropic", "claude-fable-5") is True
    assert model_supports_reasoning_effort("anthropic", "claude-fable-5-1") is True
    assert model_supports_reasoning_effort("anthropic", "claude-sonnet-4-6") is True
    assert model_supports_reasoning_effort("anthropic", "claude-haiku-4-5-20251001") is False
    assert model_supports_reasoning_effort("google", "gemini-4-argon") is True
    assert model_supports_reasoning_effort("google", "gemini-3.5-flash") is True
    assert model_supports_reasoning_effort("google", "gemini-3.1-pro-preview") is True
    assert model_supports_reasoning_effort("meta", "muse-wonder-1.0") is True
    assert model_supports_reasoning_effort("meta", "muse-spark-1.3") is True
    assert model_supports_reasoning_effort("xai", "grok-4.5") is True
    assert model_supports_reasoning_effort("xai", "grok-4.3") is True
    assert model_supports_reasoning_effort("xai", "grok-4.20") is True
    assert model_supports_reasoning_effort("moonshot", "kimi-k2.6") is True
    assert model_supports_reasoning_effort("moonshot", "kimi-k3") is False
    assert (
        model_supports_reasoning_effort(
            "local", "gemma-4", compatible_backend="unsloth"
        )
        is True
    )
    assert model_supports_reasoning_effort("nvidia", "nvidia/nemotron-3-ultra-550b-a55b") is False
    assert model_supports_reasoning_effort("openai", "gpt-5-chat-latest") is False
    assert (
        model_supports_reasoning_effort(
            "openrouter", "anthropic/claude-sonnet-5"
        )
        is True
    )
    assert (
        model_supports_reasoning_effort(
            "openrouter", "anthropic/claude-haiku-4.5"
        )
        is True
    )
    assert (
        model_supports_reasoning_effort(
            "openrouter", "openai/gpt-6-astra"
        )
        is True
    )
    assert (
        model_supports_reasoning_effort(
            "openrouter", "openai/gpt-5.6-terra"
        )
        is True
    )
    assert (
        model_supports_reasoning_effort(
            "openrouter", "openai/gpt-5.6-luna"
        )
        is True
    )
    assert (
        model_supports_reasoning_effort(
            "openrouter", "qwen/qwen3.7-flash"
        )
        is True
    )
    assert (
        model_supports_reasoning_effort(
            "openrouter", "thinkingmachines/inkling"
        )
        is True
    )
    assert (
        model_supports_reasoning_effort(
            "openrouter", "google/gemini-2.5-pro"
        )
        is True
    )
    assert (
        model_supports_reasoning_effort(
            "openrouter", "google/gemini-2.5-flash"
        )
        is True
    )
    assert (
        model_supports_reasoning_effort("openrouter", "x-ai/grok-4.5") is True
    )
    assert (
        model_supports_reasoning_effort(
            "openrouter", "deepseek/deepseek-chat-v3.1"
        )
        is True
    )
    assert (
        model_supports_reasoning_effort("openrouter", "openai/gpt-4o-mini")
        is False
    )
    assert (
        model_supports_reasoning_effort("openrouter", "moonshotai/kimi-k2")
        is False
    )
    assert (
        model_supports_reasoning_effort("openrouter", "qwen/qwen3-max") is False
    )
    assert (
        model_supports_reasoning_effort(
            "openrouter", "mistralai/mistral-large-2512"
        )
        is False
    )
    assert reasoning_effort_options("openai", "gpt-5.6-sol") == [
        "low",
        "medium",
        "high",
    ]
    assert reasoning_effort_options("anthropic", "claude-sonnet-5") == [
        "low",
        "medium",
        "high",
    ]
    assert reasoning_effort_options("google", "gemini-3.5-flash") == [
        "low",
        "medium",
        "high",
    ]
    assert effective_reasoning_effort(effort="high", fast=False) == "high"
    assert effective_reasoning_effort(effort="high", fast=True) == "none"
    assert (
        effective_reasoning_effort(effort="high", fast=True, model_id="gpt-5-mini")
        == "minimal"
    )
    assert (
        effective_reasoning_effort(effort="low", fast=False, model_id="gpt-5.5-pro")
        == "medium"
    )
    assert effective_reasoning_effort(effort="bogus", fast=False) == "medium"

    from agent.model_catalog import (
        effective_anthropic_effort,
        effective_gemini_thinking_level,
        effective_openrouter_reasoning,
        effective_xai_reasoning_effort,
    )

    assert effective_anthropic_effort(effort="high", fast=False) == "high"
    assert effective_anthropic_effort(effort="high", fast=True) == "low"
    assert effective_anthropic_effort(effort="none", fast=False) == "low"
    assert effective_gemini_thinking_level(effort="high", fast=False) == "high"
    assert effective_gemini_thinking_level(effort="medium", fast=False) == "medium"
    assert effective_gemini_thinking_level(effort="low", fast=False) == "low"
    assert effective_gemini_thinking_level(effort="high", fast=True) == "minimal"
    assert (
        effective_xai_reasoning_effort(effort="high", fast=True, model_id="grok-4.5")
        == "low"
    )
    assert (
        effective_xai_reasoning_effort(effort="high", fast=True, model_id="grok-4.3")
        == "none"
    )
    assert effective_openrouter_reasoning(
        effort="high", fast=False, model_id="anthropic/claude-sonnet-5"
    ) == {"effort": "high"}
    assert effective_openrouter_reasoning(
        effort="high", fast=True, model_id="anthropic/claude-sonnet-5"
    ) == {"effort": "low"}
    assert effective_openrouter_reasoning(
        effort="medium", fast=True, model_id="anthropic/claude-opus-5"
    ) == {"effort": "low"}
    assert effective_openrouter_reasoning(
        effort="medium", fast=False, model_id="openai/gpt-6-astra"
    ) == {"effort": "medium"}
    assert effective_openrouter_reasoning(
        effort="medium", fast=True, model_id="openai/gpt-6-astra"
    ) == {"effort": "low"}
    assert effective_openrouter_reasoning(
        effort="high", fast=True, model_id="openai/gpt-5.6-terra"
    ) == {"effort": "none"}
    assert effective_openrouter_reasoning(
        effort="high", fast=True, model_id="x-ai/grok-4.5"
    ) == {"effort": "low"}
    assert effective_openrouter_reasoning(
        effort="high", fast=True, model_id="google/gemini-2.5-pro"
    ) == {"effort": "low"}
    assert effective_openrouter_reasoning(
        effort="medium", fast=False, model_id="google/gemini-2.5-flash"
    ) == {"effort": "medium"}
    assert effective_openrouter_reasoning(
        effort="high", fast=True, model_id="deepseek/deepseek-chat-v3.1"
    ) == {"effort": "none"}
    assert effective_openrouter_reasoning(
        effort="high", fast=True, model_id="meta/muse-spark-1.2"
    ) == {"effort": "low"}
    from agent.model_catalog import (
        model_supports_reasoning_fast,
        openrouter_model_reasoning_mandatory,
    )

    assert openrouter_model_reasoning_mandatory("meta/muse-spark-1.2") is True
    assert (
        model_supports_reasoning_fast("openrouter", "meta/muse-spark-1.2")
        is False
    )
    assert (
        model_supports_reasoning_fast("openrouter", "anthropic/claude-sonnet-5")
        is True
    )


def test_openrouter_model_omits_temperature():
    from agent.model_catalog import openrouter_model_omits_temperature

    assert openrouter_model_omits_temperature("openai/gpt-6-astra") is True
    assert openrouter_model_omits_temperature("openai/gpt-5.6-terra") is True
    assert openrouter_model_omits_temperature("anthropic/claude-opus-5") is True
    assert openrouter_model_omits_temperature("openai/gpt-4o-mini") is False


def test_anthropic_model_omits_temperature():
    from agent.model_catalog import anthropic_model_omits_temperature

    assert anthropic_model_omits_temperature("claude-opus-5") is True
    assert anthropic_model_omits_temperature("claude-opus-5-5") is True
    assert anthropic_model_omits_temperature("claude-opus-4-8") is True
    assert anthropic_model_omits_temperature("claude-sonnet-5") is True
    assert anthropic_model_omits_temperature("claude-fable-5") is True
    assert anthropic_model_omits_temperature("claude-fable-5-1") is True
    assert anthropic_model_omits_temperature("claude-opus-4-6") is False
    assert anthropic_model_omits_temperature("claude-sonnet-4-6") is False
    assert anthropic_model_omits_temperature("claude-sonnet-4-5-20250929") is False


def test_resolve_catalog_model_id():
    from agent.model_catalog import resolve_catalog_model_id

    assert resolve_catalog_model_id("gemini-3.1-pro") == "gemini-3.1-pro-preview"
    assert resolve_catalog_model_id("gemini-3.1-pro-preview") == "gemini-3.1-pro-preview"
    assert resolve_catalog_model_id("gemini-3.5-flash") == "gemini-3.5-flash"


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


def test_model_preferences_http_routes(isolated_config: Config, tmp_path: Path):
    app = create_app(store_path=tmp_path / "agent-prefs.db", allowed_hosts=["testserver"])
    client = TestClient(app)

    empty = client.get("/v1/models/preferences")
    assert empty.status_code == 200
    assert empty.json()["favorites"] == []
    assert empty.json()["recent"] == []

    toggled = client.post(
        "/v1/models/preferences/favorite",
        json={"provider": "deepseek", "model": "deepseek-v4-flash"},
    )
    assert toggled.status_code == 200
    body = toggled.json()
    assert body["favorite"] is True
    assert body["favorites"] == ["deepseek:deepseek-v4-flash"]

    again = client.get("/v1/models/preferences")
    assert again.status_code == 200
    assert again.json()["favorites"] == ["deepseek:deepseek-v4-flash"]

    untoggled = client.post(
        "/v1/models/preferences/favorite",
        json={"provider": "deepseek", "model": "deepseek-v4-flash"},
    )
    assert untoggled.status_code == 200
    assert untoggled.json()["favorite"] is False
    assert untoggled.json()["favorites"] == []
