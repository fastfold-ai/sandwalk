"""Credentials prompt section — names only, no secret values."""

from unittest.mock import patch

from agent.system_prompt.credentials_section import build_credentials_section


def test_credentials_section_lists_configured_names():
    with (
        patch(
            "agent.config.listed_integration_env_vars",
            return_value=["FASTFOLD_API_KEY", "BOLTZ_API_KEY"],
        ),
        patch("agent.config.sync_sandwalk_path_env", return_value=[]),
    ):
        text = build_credentials_section()
    assert "FASTFOLD_API_KEY" in text
    assert "BOLTZ_API_KEY" in text
    assert "SANDWALK_SKILLS_DIR" in text
    assert "Configured env vars (present)" in text
    assert "sk-" not in text


def test_credentials_section_empty_integrations():
    with (
        patch("agent.config.listed_integration_env_vars", return_value=[]),
        patch("agent.config.sync_sandwalk_path_env", return_value=[]),
    ):
        text = build_credentials_section()
    assert "No Integrations API keys" in text
    assert "SANDWALK_CONFIG_DIR" in text


@patch("agent.system_prompt._load_installed_skills", return_value="")
def test_system_prompt_includes_credentials_section(mock_skills):
    from agent.system_prompt import build_system_prompt

    with (
        patch(
            "agent.config.listed_integration_env_vars",
            return_value=["FASTFOLD_API_KEY"],
        ),
        patch("agent.config.sync_sandwalk_path_env", return_value=[]),
    ):
        prompt = build_system_prompt(
            type("Session", (), {"config": None})(),
            include_skills=False,
        )
    assert "## Credentials & paths (host shell)" in prompt
    assert "`FASTFOLD_API_KEY`" in prompt
