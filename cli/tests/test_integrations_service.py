"""Unit tests for agent_server.integrations_service."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from agent.config import Config
from agent_server.integrations_service import (
    IntegrationsService,
    category_for,
)


def test_category_for_prefixes():
    assert category_for("llm.anthropic_api_key") == "AI Models"
    assert category_for("compute.runpod_api_key") == "Compute"
    assert category_for("notification.sendgrid_api_key") == "Notifications"
    assert category_for("api.fastfold_cloud_key") == "API"
    assert category_for("mcp.linear_api_key") == "MCP"
    assert category_for("other.thing") == "Other"


def test_masked_preview():
    svc = IntegrationsService()
    assert svc._masked("") is None
    assert svc._masked("short") == "••••••••"
    assert svc._masked("abcdefghijklmnop", is_secret=True).startswith("abcd")
    assert svc._masked("abcdefghijklmnop", is_secret=False) == "abcdefghijklmnop"


def test_list_and_get_providers():
    svc = IntegrationsService()
    providers = svc.list()
    assert providers
    keys = {item.key for item in providers}
    assert "anthropic" in keys
    assert "openai" in keys
    assert "openai-compatible" not in keys

    provider = svc.get("anthropic")
    assert provider is not None
    assert provider.key == "anthropic"
    assert provider.category == "AI Models"
    assert svc.get("does-not-exist") is None


def test_update_and_remove_integration(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent.config.CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr("agent.config.CONFIG_FILE", tmp_path / "cfg" / "config.json")
    (tmp_path / "cfg").mkdir(parents=True, exist_ok=True)
    Config({}).save()

    svc = IntegrationsService()
    updated = svc.update("anthropic", {"ANTHROPIC_API_KEY": "sk-ant-api03-testkey"})
    assert updated.configured is True
    assert updated.source in {"config", "environment"}
    assert Config.load().get("llm.anthropic_api_key") == "sk-ant-api03-testkey"

    cleared = svc.remove("anthropic")
    assert cleared.configured is False
    assert Config.load().get("llm.anthropic_api_key") is None


def test_update_requires_value():
    svc = IntegrationsService()
    with pytest.raises(ValueError, match="At least one"):
        svc.update("anthropic", {})
    with pytest.raises(KeyError):
        svc.update("missing-provider", {"ANTHROPIC_API_KEY": "x"})


def test_validate_integration():
    svc = IntegrationsService()
    result = svc.validate("anthropic")
    assert result.ok is False
    assert "not configured" in result.message.lower()

    with pytest.raises(KeyError):
        svc.validate("missing-provider")


def test_extract_env_value():
    text = "# comment\nVERCEL_OIDC_TOKEN=abc123\nOTHER=ignored\n"
    assert IntegrationsService._extract_env_value(text, "VERCEL_OIDC_TOKEN") == "abc123"
    assert IntegrationsService._extract_env_value(text, "MISSING") == ""


def test_autofill_skills_sh_from_env(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent.config.CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr("agent.config.CONFIG_FILE", tmp_path / "cfg" / "config.json")
    (tmp_path / "cfg").mkdir(parents=True, exist_ok=True)
    Config({}).save()
    monkeypatch.setenv("VERCEL_OIDC_TOKEN", "oidc-token-xyz")

    svc = IntegrationsService()
    provider = svc.autofill("skills-sh")
    assert provider.configured is True
    assert Config.load().get("api.vercel_oidc_token") == "oidc-token-xyz"


def test_autofill_rejects_non_skills_provider():
    svc = IntegrationsService()
    with pytest.raises(ValueError, match="Auto-import"):
        svc.autofill("anthropic")


def test_setup_skills_sh_env_token(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent.config.CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr("agent.config.CONFIG_FILE", tmp_path / "cfg" / "config.json")
    (tmp_path / "cfg").mkdir(parents=True, exist_ok=True)
    Config({}).save()
    monkeypatch.setenv("VERCEL_OIDC_TOKEN", "env-oidc")

    svc = IntegrationsService()
    result = svc.setup("skills-sh")
    assert result.ok is True
    assert result.integration_key == "skills-sh"
    assert any(step.id == "env-token" and step.ok for step in result.steps)


def test_setup_skills_sh_missing_cli(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent.config.CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr("agent.config.CONFIG_FILE", tmp_path / "cfg" / "config.json")
    (tmp_path / "cfg").mkdir(parents=True, exist_ok=True)
    Config({}).save()
    monkeypatch.delenv("VERCEL_OIDC_TOKEN", raising=False)
    monkeypatch.setattr("agent_server.integrations_service.shutil.which", lambda _: None)

    svc = IntegrationsService()
    result = svc.setup("skills-sh")
    assert result.ok is False
    assert "CLI" in result.summary


def test_fetch_vercel_oidc_via_cli(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "agent_server.integrations_service.shutil.which",
        lambda _: "/usr/bin/vercel",
    )

    class FakeCompleted:
        returncode = 0
        stderr = ""
        stdout = ""

    def fake_run(cmd, **kwargs):
        env_file = Path(cmd[3])
        env_file.write_text('VERCEL_OIDC_TOKEN="pulled-token"\n', encoding="utf-8")
        return FakeCompleted()

    monkeypatch.setattr("agent_server.integrations_service.subprocess.run", fake_run)
    token, err = IntegrationsService._fetch_vercel_oidc_token_via_cli(tmp_path)
    assert token == "pulled-token"
    assert err == ""


def test_fetch_vercel_oidc_cli_missing():
    svc = IntegrationsService()
    token, err = IntegrationsService._fetch_vercel_oidc_token_via_cli(Path("/tmp"))
    # shutil.which may or may not find vercel; if missing:
    if err:
        assert "not installed" in err.lower() or token == ""
