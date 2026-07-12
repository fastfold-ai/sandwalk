"""Tests for agent.system_prompt builder."""

import sys
from types import ModuleType
from unittest.mock import patch

from agent.system_prompt import _load_installed_skills, build_system_prompt


class TestSystemPrompt:
    @patch("agent.system_prompt._load_installed_skills", return_value="")
    def test_build_system_prompt_includes_identity(self, mock_skills):
        session = type("Session", (), {"config": type("Cfg", (), {
            "get": lambda self, key, default=None: default,
        })()})()

        prompt = build_system_prompt(session, tool_names=["target.druggability", "run_python"])
        assert "fastfold-agent-cli" in prompt or "Fastfold Agent" in prompt
        assert "Available Tools" in prompt
        assert "run_python" in prompt

    @patch("agent.system_prompt._load_installed_skills", return_value="## Skills\n- fold")
    def test_build_includes_skills_section(self, mock_skills):
        session = type("Session", (), {"config": type("Cfg", (), {
            "get": lambda self, key, default=None: default,
        })()})()

        prompt = build_system_prompt(session)
        assert "fold" in prompt

    @patch("agent.system_prompt._load_installed_skills", return_value="")
    def test_build_includes_data_and_history(self, mock_skills):
        session = type("Session", (), {"config": type("Cfg", (), {
            "get": lambda self, key, default=None: default,
        })()})()

        prompt = build_system_prompt(
            session,
            data_context="L1000 data available",
            history="User: prior question",
        )
        assert "L1000 data available" in prompt
        assert "prior question" in prompt

    def test_load_installed_skills_uses_configured_budgets(self):
        config = type("Cfg", (), {
            "get": lambda self, key, default=None: {
                "agent.skills.max_catalog_entries": "12",
                "agent.skills.max_active": "bad-value",
                "agent.skills.max_prompt_chars": 5000,
            }.get(key, default),
        })()
        session = type("Session", (), {"config": config})()

        with patch("agent.skills.build_skills_prompt", return_value="skills") as build:
            assert _load_installed_skills(session, "fold TP53") == "skills"

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
    def test_build_ptc_prompt_and_deepagents_filesystem(self, mock_catalog, mock_skills):
        session = type("Session", (), {"config": None})()

        prompt = build_system_prompt(
            session,
            include_skills=False,
            runtime="deepagents",
            tool_mode="ptc",
            exclude_categories={"unsafe"},
        )

        assert "Compact catalog" in prompt
        assert "Other tools" in prompt
        assert "Skills & Filesystem" in prompt
        mock_catalog.assert_called_once_with(exclude_categories={"unsafe"})

    @patch("agent.system_prompt._load_installed_skills", return_value="")
    @patch("agent.ptc_tools.build_tool_catalog", side_effect=RuntimeError("catalog failed"))
    def test_build_ptc_prompt_survives_catalog_error(self, mock_catalog, mock_skills):
        session = type("Session", (), {"config": None})()
        prompt = build_system_prompt(session, tool_mode="ptc")
        assert "Other tools" in prompt

    @patch("agent.system_prompt._load_installed_skills", return_value="")
    def test_build_survives_optional_prompt_section_import_errors(self, mock_skills):
        session = type("Session", (), {"config": None})()
        workflows = ModuleType("agent.workflows")
        workflows.format_workflows_for_llm = lambda: (_ for _ in ()).throw(
            RuntimeError("workflow failure")
        )
        knowledge = ModuleType("agent.knowledge")
        code = ModuleType("tools.code")

        with patch.dict(
            sys.modules,
            {
                "agent.workflows": workflows,
                "agent.knowledge": knowledge,
                "tools.code": code,
            },
        ):
            prompt = build_system_prompt(session)

        assert "When You Are Ready to Answer" in prompt
