"""Knowledge Level policy + prompt/tool surface differences."""

from __future__ import annotations

from types import SimpleNamespace

from agent.knowledge_level import knowledge_flags, resolve_knowledge_level
from agent.system_prompt.builder import build_system_prompt


class _Cfg(dict):
    def get(self, key, default=None):
        return super().get(key, default)


def test_resolve_knowledge_level_defaults_and_invalid():
    assert resolve_knowledge_level(None) == "high"
    assert resolve_knowledge_level(_Cfg()) == "high"
    assert resolve_knowledge_level(_Cfg({"agent.knowledge_level": "medium"})) == "medium"
    assert resolve_knowledge_level(_Cfg({"agent.knowledge_level": "LOW"})) == "low"
    assert resolve_knowledge_level(_Cfg({"agent.knowledge_level": "nope"})) == "high"


def test_medium_and_low_flags():
    high = knowledge_flags("high")
    med = knowledge_flags("medium")
    low = knowledge_flags("low")

    assert high.excluded_deepagents_tools == frozenset()
    assert high.include_domain_subagents
    assert high.ptc_catalog == "full"
    assert not high.omit_workflow_index

    assert med.excluded_deepagents_tools == frozenset(
        {"write_todos", "execute", "task"}
    )
    assert not med.include_domain_subagents
    assert med.ptc_catalog == "stub"
    assert med.omit_workflow_index
    assert med.short_synthesis

    assert low.excluded_deepagents_tools == frozenset(
        {"write_todos", "execute", "task", "edit_file", "glob", "grep"}
    )
    assert not low.include_domain_subagents
    assert low.ptc_catalog == "stub"
    assert low.omit_synthesis
    assert low.omit_workflow_index


def test_prompt_keeps_credentials_and_skills_guidance_at_all_levels(tmp_path):
    for level in ("high", "medium", "low"):
        cfg = _Cfg({"agent.knowledge_level": level, "agent.plan_preview": False})
        session = SimpleNamespace(config=cfg)
        prompt = build_system_prompt(
            session,
            include_skills=False,
            runtime="deepagents",
            tool_mode="ptc",
            workspace_path=str(tmp_path),
            sandbox_backend="builtin",
        )
        assert "Credentials" in prompt or "Integrations" in prompt or "FASTFOLD" in prompt
        # Skills progressive-disclosure guidance stays (index itself is deepagents).
        assert "skill" in prompt.lower()
        if level == "high":
            assert "When You Are Ready to Answer" in prompt
            assert "Operating Mode" in prompt
        if level == "low":
            assert "When You Are Ready to Answer" not in prompt
            assert "Workflow" not in prompt or "workflow index" not in prompt.lower()


def test_low_omits_full_ptc_catalog_high_includes_it(monkeypatch, tmp_path):
    catalog = "## Domain tool catalog\n- tools.foo.bar"

    def _fake_catalog(**kwargs):
        return catalog

    monkeypatch.setattr("agent.ptc_tools.build_tool_catalog", _fake_catalog)

    high_cfg = _Cfg({"agent.knowledge_level": "high", "agent.plan_preview": False})
    low_cfg = _Cfg({"agent.knowledge_level": "low", "agent.plan_preview": False})
    high = build_system_prompt(
        SimpleNamespace(config=high_cfg),
        include_skills=False,
        runtime="deepagents",
        tool_mode="ptc",
        workspace_path=str(tmp_path),
    )
    low = build_system_prompt(
        SimpleNamespace(config=low_cfg),
        include_skills=False,
        runtime="deepagents",
        tool_mode="ptc",
        workspace_path=str(tmp_path),
    )
    assert catalog in high
    assert catalog not in low
    assert "search_tools" in low
    assert len(low) < len(high)


def test_measure_excludes_deepagents_tools_for_low():
    from agent.deepagents_runtime.prompt_budget import measure_deepagents_builtin_tool_schemas
    from agent.knowledge_level import knowledge_flags

    flags = knowledge_flags("low")
    _text, names = measure_deepagents_builtin_tool_schemas(
        domain_tools=[],
        system_prompt="You are helpful.",
        skills_sources=[],
        excluded_tools=flags.excluded_deepagents_tools,
        include_domain_subagents=flags.include_domain_subagents,
    )
    assert "write_todos" not in names
    assert "execute" not in names
    assert "task" not in names
    # Core filesystem tools remain so skills / workspace work.
    assert "read_file" in names
    assert "ls" in names
    assert "write_file" in names
    assert "edit_file" not in names
    assert "glob" not in names


def test_knowledge_level_middleware_strips_todo_and_task_prompts():
    from langchain_core.messages import SystemMessage

    from agent.deepagents_runtime.knowledge_level_middleware import (
        apply_knowledge_level_to_system_message,
    )
    from agent.deepagents_runtime.middleware_prompts import middleware_system_prompt_text
    from agent.knowledge_level import knowledge_flags

    excluded = knowledge_flags("low").excluded_deepagents_tools
    message = SystemMessage(
        content=[
            {"type": "text", "text": "You are sandwalk."},
            {"type": "text", "text": "## `write_todos`\n\nUse write_todos always."},
            {"type": "text", "text": "## Skills System\n\n- **fold**: fold proteins"},
            {
                "type": "text",
                "text": "## `task` (subagent spawner)\n\nUse task for isolation.",
            },
        ]
    )
    filtered = apply_knowledge_level_to_system_message(message, excluded)
    assert filtered is not None
    texts = [block.get("text", "") for block in filtered.content if isinstance(block, dict)]
    assert any("sandwalk" in text for text in texts)
    assert any("Skills System" in text for text in texts)
    assert not any("write_todos" in text for text in texts)
    assert not any("## `task`" in text for text in texts)

    middleware = middleware_system_prompt_text(excluded_tools=excluded)
    assert "write_todos" not in middleware
    assert "## `task`" not in middleware
    assert "Filesystem" in middleware or "filesystem" in middleware.lower()
