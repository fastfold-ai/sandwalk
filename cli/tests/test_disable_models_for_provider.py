"""Models turn off when their LLM provider has no API key."""

from __future__ import annotations

from pathlib import Path

from agent.config import Config
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
    assert all(mid.startswith("gemini-") for mid in hidden)
    assert set(hidden) <= set(cfg.hidden_models())


def test_sync_hides_models_when_key_missing(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent.config.CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr("agent.config.CONFIG_FILE", tmp_path / "cfg" / "config.json")
    (tmp_path / "cfg").mkdir(parents=True, exist_ok=True)
    cfg = Config({})
    cfg.save()

    assert sync_models_for_unconfigured_providers(cfg) is True
    hidden = set(cfg.hidden_models())
    assert "gemini-3.5-flash" in hidden
    # Second pass is a no-op.
    assert sync_models_for_unconfigured_providers(cfg) is False
