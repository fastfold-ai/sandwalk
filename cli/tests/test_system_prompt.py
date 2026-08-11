"""Tests for agent.system_prompt builder wiring (not prompt copy)."""

import sys
from types import ModuleType
from unittest.mock import patch

from agent.system_prompt import _load_installed_skills, build_system_prompt


def _session(config=None):
    return type("Session", (), {"config": config})()


class TestSystemPrompt:
    def test_load_installed_skills_uses_configured_budgets(self):
        config = type(
            "Cfg",
            (),
            {
                "get": lambda self, key, default=None: {
                    "agent.skills.max_catalog_entries": "12",
                    "agent.skills.max_active": "bad-value",
                    "agent.skills.max_prompt_chars": 5000,
                }.get(key, default),
            },
        )()

        with patch("agent.skills.build_skills_prompt", return_value="skills") as build:
            assert _load_installed_skills(_session(config), "fold TP53") == "skills"

        build.assert_called_once_with(
            user_request="fold TP53",
            max_catalog_entries=12,
            max_active_skills=6,
            max_active_chars=5000,
            catalog_description_chars=140,
            index_snippet_chars=8000,
        )

    def test_load_installed_skills_without_session_uses_defaults(self):
        with patch("agent.skills.build_skills_prompt", return_value="skills") as build:
            assert _load_installed_skills() == "skills"
        assert build.call_args.kwargs["max_catalog_entries"] == 250

    @patch("agent.system_prompt._load_installed_skills", return_value="")
    @patch("agent.ptc_tools.build_tool_catalog", return_value="## Compact catalog")
    def test_build_ptc_passes_exclude_categories(self, mock_catalog, mock_skills):
        prompt = build_system_prompt(
            _session(),
            include_skills=False,
            runtime="deepagents",
            tool_mode="ptc",
            exclude_categories={"unsafe"},
        )
        assert isinstance(prompt, str) and prompt
        assert "Skill creation and installation truth" in prompt
        assert "installation_verified=true" in prompt
        assert 'Draft created, but it is not installed.' in prompt
        mock_catalog.assert_called_once_with(
            exclude_categories={"unsafe"},
            exclude_tools=set(),
        )

    @patch("agent.system_prompt._load_installed_skills", return_value="")
    @patch("agent.ptc_tools.build_tool_catalog", side_effect=RuntimeError("catalog failed"))
    def test_build_ptc_survives_catalog_error(self, mock_catalog, mock_skills):
        prompt = build_system_prompt(_session(), tool_mode="ptc")
        assert isinstance(prompt, str) and prompt

    @patch("agent.system_prompt._load_installed_skills", return_value="")
    def test_build_survives_optional_section_import_errors(self, mock_skills):
        workflows = ModuleType("agent.workflows")
        workflows.format_workflow_index_for_llm = lambda: (_ for _ in ()).throw(
            RuntimeError("workflow failure")
        )

        with patch.dict(sys.modules, {"agent.workflows": workflows}):
            prompt = build_system_prompt(_session())

        assert isinstance(prompt, str) and prompt

    @patch("agent.system_prompt._load_installed_skills", return_value="")
    def test_main_prompt_stays_under_size_budget(self, mock_skills):
        prompt = build_system_prompt(_session(), include_skills=False)
        assert len(prompt) < 40_000

    def test_domain_subagents_registered(self):
        from agent.deepagents_runtime.subagents import build_domain_subagents

        by_name = {s["name"]: s for s in build_domain_subagents()}
        assert "domain-expert" in by_name
        assert "bio-coder" in by_name
        assert by_name["domain-expert"]["system_prompt"]
        assert by_name["bio-coder"]["system_prompt"]
