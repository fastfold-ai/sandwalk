"""Models turn off when their LLM provider has no API key."""

from __future__ import annotations

from pathlib import Path

from agent.config import Config
from agent.model_catalog import CATALOG_DEFAULTS_VERSION
from agent_server.models_service import ModelsService
from agent_server.models_service.mutate import (
    disable_models_for_provider,
    sync_models_for_unconfigured_providers,
)


def test_disable_models_for_provider_hides_google(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent.config.CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr("agent.config.CONFIG_FILE", tmp_path / "cfg" / "config.json")
    (tmp_path / "cfg").mkdir(parents=True, exist_ok=True)
    cfg = Config({})
    cfg.save()

    hidden = disable_models_for_provider(cfg, "google")
    assert hidden
    assert all(mid.startswith("google:") for mid in hidden)
    assert set(hidden) <= set(cfg.hidden_models())


def test_sync_hides_models_when_key_missing(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent.config.CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr("agent.config.CONFIG_FILE", tmp_path / "cfg" / "config.json")
    (tmp_path / "cfg").mkdir(parents=True, exist_ok=True)
    cfg = Config({})
    cfg.save()

    assert sync_models_for_unconfigured_providers(cfg) is True
    hidden = set(cfg.hidden_models())
    assert "google:gemini-3.5-flash" in hidden
    # Second pass is a no-op.
    assert sync_models_for_unconfigured_providers(cfg) is False


def test_enabled_only_omits_unconfigured_provider_models(
    tmp_path: Path, monkeypatch
):
    """enabled_only must not surface models when the provider has no key —
    even if a prior toggle left them un-hidden.
    """
    import agent.config as config_mod

    config_dir = tmp_path / "cfg"
    config_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config_mod, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config_mod, "CONFIG_FILE", config_dir / "config.json")
    monkeypatch.setattr(
        config_mod, "CONFIG_BACKUP_FILE", config_dir / "config.json.bak"
    )
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    Config(
        {
            "llm.hidden_models": [],
            "llm.catalog_defaults_version": CATALOG_DEFAULTS_VERSION,
        }
    ).save()

    listed = ModelsService().list_models(enabled_only=True, discover=False)
    providers = {item.provider for item in listed.data}
    assert "anthropic" not in providers
    assert "openai" not in providers
    assert "google" not in providers
