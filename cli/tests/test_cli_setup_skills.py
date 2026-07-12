"""CLI tests for setup_cmd and skills subcommands with heavy mocking."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from agent.config import Config
from agent.skills import SkillInfo
from cli import (
    add_skills_cmd,
    app,
    setup_cmd,
    skill_add,
    skill_find,
    skill_info_cmd,
    skill_install,
    skill_remove,
)

runner = CliRunner()


def _mock_cfg(monkeypatch, data=None):
    cfg = Config(data=dict(data or {}))
    monkeypatch.setattr(Config, "load", classmethod(lambda cls: cfg))
    return cfg


def _stub_setup_flow(monkeypatch):
    """Minimal mocks so setup_cmd can finish without prompts."""
    monkeypatch.delenv("ANTHROPIC_FOUNDRY_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_FOUNDRY_RESOURCE", raising=False)
    monkeypatch.setattr("cli._prompt_setup_providers", lambda default: ["anthropic"])
    monkeypatch.setattr(
        "cli._resolve_provider_key",
        lambda cfg, provider, cli_key=None, openai_base_url=None, compatible_backend=None: (
            cli_key or "sk-ant-api03-test"
        ),
    )
    monkeypatch.setattr("cli._prompt_fastfold_cloud_api_key", lambda cfg, cli_key: None)
    monkeypatch.setattr("cli._prompt_boltz_api_key", lambda cfg, cli_key: None)
    monkeypatch.setattr("cli._prompt_install_skills", lambda skills_arg=None, skip=False: None)
    monkeypatch.setattr("cli._prompt_install_boltz_stack", lambda boltz_key: None)
    monkeypatch.setattr("agent.doctor.run_checks", lambda cfg: [])
    monkeypatch.setattr("agent.doctor.to_table", lambda checks: "")
    monkeypatch.setattr("agent.doctor.has_errors", lambda checks: False)


class TestSetupCmd:
    def test_setup_cmd_anthropic_non_interactive(self, monkeypatch):
        cfg = _mock_cfg(monkeypatch)
        _stub_setup_flow(monkeypatch)

        setup_cmd(
            api_key="sk-ant-api03-abc",
            provider="anthropic",
            skip_skills=True,
        )

        assert cfg.get("llm.provider") == "anthropic"
        assert cfg.get("llm.anthropic_api_key") == "sk-ant-api03-abc"

    def test_setup_cmd_foundry_early_exit(self, monkeypatch, capsys):
        cfg = _mock_cfg(monkeypatch)
        monkeypatch.setenv("ANTHROPIC_FOUNDRY_API_KEY", "foundry-key")
        monkeypatch.delenv("ANTHROPIC_FOUNDRY_RESOURCE", raising=False)

        setup_cmd(provider="anthropic")

        captured = capsys.readouterr()
        assert "Azure AI Foundry detected" in captured.out
        assert cfg.get("llm.provider") == "anthropic"

    def test_setup_cmd_skips_skills_install(self, monkeypatch):
        cfg = _mock_cfg(monkeypatch)
        _stub_setup_flow(monkeypatch)
        called = {"skills": False}

        def _track_skills(skills_arg=None, skip=False):
            called["skills"] = True
            assert skip is True

        monkeypatch.setattr("cli._prompt_install_skills", _track_skills)

        setup_cmd(provider="anthropic", api_key="sk-ant-api03-x", skip_skills=True)
        assert called["skills"] is True
        assert cfg.get("llm.anthropic_api_key") == "sk-ant-api03-x"

    def test_setup_cmd_installs_skills_from_arg(self, monkeypatch):
        cfg = _mock_cfg(monkeypatch)
        _stub_setup_flow(monkeypatch)
        installed = []

        def _install(skills_arg=None, skip=False):
            installed.append(skills_arg)

        monkeypatch.setattr("cli._prompt_install_skills", _install)

        setup_cmd(
            provider="anthropic",
            api_key="sk-ant-api03-x",
            skills="fold,fastfold-ai/skills@skills/md",
        )
        assert installed == ["fold,fastfold-ai/skills@skills/md"]

    def test_setup_cmd_invalid_default_provider_from_config(self, monkeypatch):
        cfg = _mock_cfg(monkeypatch, {"llm.provider": "bogus"})
        _stub_setup_flow(monkeypatch)

        setup_cmd(api_key="sk-ant-api03-x", skip_skills=True)
        assert cfg.get("llm.provider") == "anthropic"

    def test_setup_cmd_anthropic_warning_declined(self, monkeypatch):
        cfg = _mock_cfg(monkeypatch)
        monkeypatch.setattr("cli._prompt_setup_providers", lambda default: ["anthropic"])
        monkeypatch.setattr(
            "cli._resolve_provider_key",
            lambda cfg, provider, cli_key=None, openai_base_url=None, compatible_backend=None: "not-an-ant-key",
        )
        monkeypatch.setattr("builtins.input", lambda _: "n")

        with pytest.raises((SystemExit, Exception)):
            setup_cmd(provider="anthropic", skip_skills=True)

        assert cfg.get("llm.anthropic_api_key") is None

    def test_setup_cmd_cli_runner(self, monkeypatch):
        cfg = _mock_cfg(monkeypatch)
        _stub_setup_flow(monkeypatch)

        result = runner.invoke(
            app,
            [
                "setup",
                "--provider",
                "anthropic",
                "--api-key",
                "sk-ant-api03-cli",
                "--skip-skills",
            ],
        )
        assert result.exit_code == 0
        assert cfg.get("llm.anthropic_api_key") == "sk-ant-api03-cli"

    def test_setup_cmd_saves_boltz_api_key(self, monkeypatch):
        cfg = _mock_cfg(monkeypatch)
        _stub_setup_flow(monkeypatch)
        monkeypatch.setattr("cli._prompt_boltz_api_key", lambda _cfg, cli_key: cli_key)

        setup_cmd(
            provider="anthropic",
            api_key="sk-ant-api03-cli",
            boltz_api_key="sk_bc_test_cli",
            skip_skills=True,
        )

        assert cfg.get("api.boltz_api_key") == "sk_bc_test_cli"


class TestSkillAddInstall:
    @patch("agent.skills.install_skill")
    def test_skill_add_success(self, mock_install):
        mock_install.return_value = {
            "ok": True,
            "summary": "Installed fold",
            "via": "git",
            "installed": ["fold"],
        }

        result = runner.invoke(app, ["skills", "add", "fastfold-ai/skills@skills/fold"])
        assert result.exit_code == 0
        assert "Installed fold" in result.stdout
        mock_install.assert_called_once_with("fastfold-ai/skills@skills/fold")

    @patch("agent.skills.install_skill")
    def test_skill_add_failure_exits_one(self, mock_install):
        mock_install.return_value = {"ok": False, "summary": "install failed"}

        result = runner.invoke(app, ["skills", "add", "bad/source"])
        assert result.exit_code == 1
        assert "install failed" in result.stdout

    @patch("agent.skills.install_skill")
    def test_skill_install_alias(self, mock_install):
        mock_install.return_value = {"ok": True, "summary": "ok", "via": "local"}

        result = runner.invoke(app, ["skills", "install", "/tmp/skill"])
        assert result.exit_code == 0
        mock_install.assert_called_once_with("/tmp/skill")

    @patch("agent.skills.install_skill")
    def test_skill_add_direct_call_npx_method(self, mock_install):
        mock_install.return_value = {"ok": True, "summary": "npx ok", "via": "npx"}

        skill_add("vercel-labs/skills")
        mock_install.assert_called_once()


class TestSkillRemove:
    @patch("agent.skills.remove_skill")
    def test_skill_remove_success(self, mock_remove):
        mock_remove.return_value = {"ok": True, "summary": "Removed fold"}

        result = runner.invoke(app, ["skills", "remove", "fold"])
        assert result.exit_code == 0
        assert "Removed fold" in result.stdout

    @patch("agent.skills.remove_skill")
    def test_skill_remove_not_found(self, mock_remove):
        mock_remove.return_value = {"ok": False, "summary": "Skill fold not installed"}

        result = runner.invoke(app, ["skills", "remove", "fold"])
        assert result.exit_code == 1


class TestSkillFind:
    @patch("agent.skills.discover_skills")
    def test_skill_find_with_results(self, mock_discover):
        mock_discover.return_value = [
            {
                "name": "fold",
                "install_source": "fastfold-ai/skills@skills/fold",
                "description": "Protein folding",
            }
        ]

        result = runner.invoke(app, ["skills", "find", "fold"])
        assert result.exit_code == 0
        assert "fold" in result.stdout
        mock_discover.assert_called_once_with("fold")

    @patch("agent.skills.discover_skills")
    def test_skill_find_no_results_exits(self, mock_discover):
        mock_discover.return_value = []

        result = runner.invoke(app, ["skills", "find", "nope"])
        assert "No matching skills" in result.stdout

    @patch("agent.skills.discover_skills")
    def test_skill_find_without_query(self, mock_discover):
        mock_discover.return_value = [
            {
                "name": "md",
                "install_source": "fastfold-ai/skills@skills/md",
                "description": "MD workflow",
            }
        ]

        result = runner.invoke(app, ["skills", "find"])
        assert result.exit_code == 0
        mock_discover.assert_called_once_with(None)


class TestSkillInfo:
    @patch("agent.skills.skill_info")
    def test_skill_info_cmd_success(self, mock_info):
        mock_info.return_value = SkillInfo(
            name="fold",
            description="Fold proteins",
            tags=["folding", "api"],
            path=Path("/tmp/fold/SKILL.md"),
            source="global",
        )

        result = runner.invoke(app, ["skills", "info", "fold"])
        assert result.exit_code == 0
        assert "fold" in result.stdout
        assert "Fold proteins" in result.stdout
        assert "folding" in result.stdout

    @patch("agent.skills.skill_info")
    def test_skill_info_cmd_not_installed(self, mock_info):
        mock_info.return_value = None

        result = runner.invoke(app, ["skills", "info", "missing"])
        assert result.exit_code == 1
        assert "not installed" in result.stdout


class TestAddSkillsCmd:
    @patch("cli.skill_add")
    def test_add_skills_cmd_delegates(self, mock_add):
        result = runner.invoke(app, ["add", "skills", "owner/repo@skills/foo"])
        assert result.exit_code == 0
        mock_add.assert_called_once_with("owner/repo@skills/foo")

    def test_add_skills_cmd_direct(self):
        with patch("cli.skill_add") as mock_add:
            add_skills_cmd("local/path")
            mock_add.assert_called_once_with("local/path")


class TestPromptInstallSkills:
    def test_prompt_install_skills_non_interactive_skips(self, monkeypatch, capsys):
        from cli import _prompt_install_skills

        monkeypatch.setattr("cli.sys.stdin.isatty", lambda: False)
        monkeypatch.setattr("cli.sys.stdout.isatty", lambda: False)

        _prompt_install_skills()
        captured = capsys.readouterr()
        assert "Skipping skills install" in captured.out

    def test_prompt_install_skills_explicit_sources(self, monkeypatch):
        from cli import _prompt_install_skills

        called = []

        def _install(sources):
            called.extend(sources)

        monkeypatch.setattr("cli._install_skill_sources", _install)
        _prompt_install_skills(skills_arg="fold,md")
        assert called == ["fold", "md"]
