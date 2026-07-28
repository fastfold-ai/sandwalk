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
from agent_server.integrations_service.capabilities import install_boltz_cli


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


def test_integration_unlocks_match_wired_tools_and_skills():
    svc = IntegrationsService()

    ibm = svc.get("ibm-rxn")
    assert ibm is not None
    assert [unlock.id for unlock in ibm.unlocks] == ["chemistry.retrosynthesis"]

    fastfold = svc.get("fastfold-cloud")
    assert fastfold is not None
    assert {unlock.id for unlock in fastfold.unlocks} == {
        "fold",
        "protein_design_boltzgen",
        "md_openmm_calvados",
        "md_openmmdl",
        "slack_report",
        "slack-relay-agent",
    }
    assert all(
        unlock.source for unlock in fastfold.unlocks if unlock.kind == "skill"
    )
    relay = next(
        unlock for unlock in fastfold.unlocks if unlock.id == "slack-relay-agent"
    )
    assert relay.kind == "capability"
    assert relay.requirement == "ambient"

    slack = svc.get("slack")
    assert slack is not None
    assert [unlock.id for unlock in slack.unlocks] == ["slack.send_message"]
    assert slack.unlocks[0].requirement == "connector"

    tavily = svc.get("tavily")
    assert tavily is not None
    assert tavily.category == "MCP"


def test_install_boltz_cli_capability_reports_verified_status(
    monkeypatch,
):
    installed = Path("/tmp/boltz-api")
    monkeypatch.setattr(
        "agent_server.integrations_service.capabilities.install_boltz_cli",
        lambda: installed,
    )
    monkeypatch.setattr(
        "agent_server.integrations_service.provider.find_boltz_cli",
        lambda: installed,
    )

    provider = IntegrationsService().install_capability("boltz", "boltz-api-cli")

    capability = next(
        unlock for unlock in provider.unlocks if unlock.id == "boltz-api-cli"
    )
    assert capability.installable is True
    assert capability.installed is True
    assert capability.status_detail == str(installed)


def test_boltz_cli_installer_downloads_runs_and_verifies(monkeypatch):
    installed = Path("/tmp/boltz-api")
    state = {"installed": False}
    response = MagicMock()
    response.text = "#!/bin/sh\ninstall boltz-api"
    response.raise_for_status.return_value = None
    monkeypatch.setattr(
        "agent_server.integrations_service.capabilities.find_boltz_cli",
        lambda: installed if state["installed"] else None,
    )
    monkeypatch.setattr(
        "agent_server.integrations_service.capabilities.shutil.which",
        lambda name: "/bin/sh" if name == "sh" else None,
    )
    monkeypatch.setattr(
        "agent_server.integrations_service.capabilities.httpx.get",
        lambda *_args, **_kwargs: response,
    )

    def fake_run(*args, **kwargs):
        state["installed"] = True
        assert args[0] == ["/bin/sh"]
        assert kwargs["input"] == response.text
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(
        "agent_server.integrations_service.capabilities.subprocess.run",
        fake_run,
    )

    assert install_boltz_cli() == installed
    response.raise_for_status.assert_called_once()


def test_update_and_remove_integration(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent.config.CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr("agent.config.CONFIG_FILE", tmp_path / "cfg" / "config.json")
    (tmp_path / "cfg").mkdir(parents=True, exist_ok=True)
    Config({}).save()

    svc = IntegrationsService()
    updated = svc.update("anthropic", {"ANTHROPIC_API_KEY": "sk-ant-api03-testkey"})
    assert updated.configured is True
    assert updated.source in {"config", "environment"}
    assert updated.fields[0].updated_at is not None
    assert Config.load().get("llm.anthropic_api_key") == "sk-ant-api03-testkey"
    assert "llm.anthropic_api_key" in Config.load().get("integrations.updated_at")

    cleared = svc.remove("anthropic")
    assert cleared.configured is False
    assert Config.load().get("llm.anthropic_api_key") is None
    assert Config.load().get("integrations.updated_at") == {}


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


@pytest.mark.parametrize(
    ("status_code", "ok", "message"),
    [
        (200, True, "Boltz API key works."),
        (401, False, "Invalid API key."),
    ],
)
def test_validate_boltz_calls_auth_endpoint(
    monkeypatch, status_code: int, ok: bool, message: str
):
    monkeypatch.setenv("BOLTZ_API_KEY", "sk_bc_test")
    response = MagicMock(status_code=status_code)
    request = MagicMock(return_value=response)
    monkeypatch.setattr(
        "agent_server.integrations_service.mutate.httpx.get",
        request,
    )

    result = IntegrationsService().validate("boltz")

    assert result.ok is ok
    assert result.message == message
    request.assert_called_once_with(
        "https://api.boltz.bio/compute/v1/auth/me",
        headers={
            "Accept": "application/json",
            "x-api-key": "sk_bc_test",
            "User-Agent": (
                "Mozilla/5.0 (compatible; Sandwalk/1.0; "
                "+https://github.com/fastfold-ai/sandwalk)"
            ),
        },
        timeout=15.0,
        follow_redirects=True,
    )


@pytest.mark.parametrize(
    ("status_code", "ok", "message"),
    [
        (200, True, "Fastfold Cloud API key works."),
        (401, False, "Invalid API key."),
    ],
)
def test_validate_fastfold_cloud_calls_users_me(
    monkeypatch, status_code: int, ok: bool, message: str
):
    monkeypatch.setenv("FASTFOLD_API_KEY", "sk-ff-test")
    response = MagicMock(status_code=status_code)
    request = MagicMock(return_value=response)
    monkeypatch.setattr(
        "agent_server.integrations_service.mutate.httpx.get",
        request,
    )

    result = IntegrationsService().validate("fastfold-cloud")

    assert result.ok is ok
    assert result.message == message
    request.assert_called_once_with(
        "https://api.fastfold.ai/v1/users/me",
        headers={
            "Accept": "application/json",
            "Authorization": "Bearer sk-ff-test",
            "User-Agent": (
                "Mozilla/5.0 (compatible; Sandwalk/1.0; "
                "+https://github.com/fastfold-ai/sandwalk)"
            ),
        },
        timeout=15.0,
        follow_redirects=True,
    )


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


def test_fetch_vercel_oidc_cli_missing(monkeypatch):
    """Force the CLI to be absent rather than hoping it is.

    This previously called through to whatever `vercel` was on PATH. On a
    machine that has it installed and no saved credentials, that starts an
    OAuth device flow and blocks until the 45s subprocess timeout.
    """
    monkeypatch.setattr(
        "agent_server.integrations_service.shutil.which", lambda _name: None
    )
    token, err = IntegrationsService._fetch_vercel_oidc_token_via_cli(Path("/tmp"))
    assert token == ""
    assert "not installed" in err.lower()
