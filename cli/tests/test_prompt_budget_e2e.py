"""End-to-end: Prompts estimate vs real Deep Agents input context."""

from __future__ import annotations

import asyncio
from pathlib import Path

from agent.config import Config
from agent.deepagents_runtime import (
    build_skills_index_text,
    create_ct_langchain_tools,
    finalize_tools_for_provider,
    measure_deepagents_builtin_tool_schemas,
    resolve_skill_source_dirs,
)
from agent.session import Session
from agent.skills import list_skills
from agent.system_prompt import build_system_prompt
from agent_server.prompt_budget_service import PromptBudgetService, _estimate_tokens
from agent_server.store import AgentStore
from deepagents.graph import BASE_AGENT_PROMPT


def test_resolve_skill_source_dirs_respects_enabled_toggle():
    """Disabling skills in the UI must shrink what deepagents receives."""
    enabled = list_skills(enabled_only=True)
    assert enabled, "expected at least one enabled skill in the test environment"

    # Stage-only for enabled names — not raw roots with every on-disk skill.
    sources = resolve_skill_source_dirs(None)
    assert sources, "enabled skills should stage into a temp root"
    staged = Path(sources[0])
    staged_dirs = [p for p in staged.iterdir() if p.is_dir()]
    assert len(staged_dirs) == len(enabled)

    empty = resolve_skill_source_dirs([])
    assert empty == []


def test_build_skills_index_scales_with_enabled_count():
    all_text, all_count = build_skills_index_text(
        [s.name for s in list_skills(enabled_only=False)]
    )
    en_text, en_count = build_skills_index_text(None)
    assert all_count >= en_count
    all_tok, _ = _estimate_tokens(all_text)
    en_tok, _ = _estimate_tokens(en_text)
    if all_count > en_count + 5:
        assert all_tok > en_tok


def test_measure_deepagents_builtins_returns_real_schemas():
    cfg = Config.load()
    session = Session(config=cfg, verbose=False, mode="batch")
    tools, *_ = create_ct_langchain_tools(
        session, provider="openai", tool_mode="ptc"
    )
    tools = finalize_tools_for_provider(list(tools), "openai")
    sp = build_system_prompt(
        session,
        tool_names=[t.name for t in tools],
        include_skills=False,
        runtime="deepagents",
        tool_mode="ptc",
    )
    skills = resolve_skill_source_dirs(None)
    text, names = measure_deepagents_builtin_tool_schemas(
        domain_tools=tools,
        system_prompt=sp,
        skills_sources=skills,
        config=cfg,
    )
    assert "read_file" in names or "ls" in names
    assert "task" in names or "write_todos" in names
    tokens, _ = _estimate_tokens(text)
    # Real schemas are thousands of tokens — not the old ~500 placeholder.
    assert tokens > 2000, tokens
    assert len(text) > 5000


def test_prompt_budget_matches_assembled_input_context(tmp_path: Path):
    """Prompts total ≈ USER + BASE + skills + domain + deepagents schemas."""
    store = AgentStore(tmp_path / "budget.db")

    async def _run():
        return await PromptBudgetService(store).estimate(specialist_id=None)

    est = asyncio.run(_run())
    by_id = {b.id: b for b in est.buckets}

    assert "system_prompt" in by_id
    assert "skills" in by_id
    assert "deepagents" in by_id
    assert "user" not in by_id

    # Skills bucket must reflect enabled skills, not directory count (3).
    enabled_n = len(list_skills(enabled_only=True))
    assert by_id["skills"].count == enabled_n

    # Deepagents builtins measured from a real graph.
    assert (by_id["deepagents"].count or 0) >= 6
    assert by_id["deepagents"].tokens > 2000

    # System prompt includes Deep Agents BASE.
    base_tok, _ = _estimate_tokens(BASE_AGENT_PROMPT)
    assert by_id["system_prompt"].tokens >= base_tok

    # Independent reconstruction should land within ~12% of the service total
    # (assembly whitespace / child double-count is avoided in service totals).
    cfg = Config.load()
    session = Session(config=cfg, verbose=False, mode="batch")
    tools, *_ = create_ct_langchain_tools(
        session, provider=str(cfg.get("llm.provider") or "openai"), tool_mode="ptc"
    )
    tools = finalize_tools_for_provider(list(tools), "openai")
    user_sp = build_system_prompt(
        session,
        tool_names=[t.name for t in tools],
        include_skills=False,
        runtime="deepagents",
        tool_mode="ptc",
    )
    skills_text, _ = build_skills_index_text(None)
    deep_text, deep_names = measure_deepagents_builtin_tool_schemas(
        domain_tools=tools,
        system_prompt=user_sp,
        skills_sources=resolve_skill_source_dirs(None),
        config=cfg,
    )
    domain_text = "\n\n".join(
        f"{t.name}\n{t.description or ''}" for t in tools
    )
    recon = (
        _estimate_tokens(user_sp + "\n\n" + BASE_AGENT_PROMPT)[0]
        + _estimate_tokens(skills_text)[0]
        + _estimate_tokens(deep_text)[0]
        + _estimate_tokens(domain_text)[0]
    )
    # Service total should track reconstruction closely.
    ratio = est.total_tokens / max(recon, 1)
    assert 0.85 <= ratio <= 1.20, (
        f"estimate={est.total_tokens} recon={recon} ratio={ratio:.3f} "
        f"deep={deep_names} skills={by_id['skills'].count}"
    )

    # With only enabled skills, total should be well under the old ~42k
    # all-skills-on-disk first turn when few skills are enabled.
    if enabled_n <= 15:
        assert est.total_tokens < 38000, est.total_tokens


def test_prompt_budget_fast_specialist_scopes_skills(tmp_path: Path):
    store = AgentStore(tmp_path / "budget.db")
    fast = store.get_specialist_by_slug("fast-computational-scientist")
    assert fast is not None

    async def _run():
        return await PromptBudgetService(store).estimate(specialist_id=fast.id)

    est = asyncio.run(_run())
    skills = next(b for b in est.buckets if b.id == "skills")
    assert skills.count == len(fast.skill_names)
    assert est.tool_counts.mcp == 0
