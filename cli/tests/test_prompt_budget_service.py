"""Tests for live prompt-budget estimates."""

from __future__ import annotations

import asyncio
from pathlib import Path

from agent.skills import list_skills
from agent_server.prompt_budget_service import PromptBudgetService
from agent_server.store import AgentStore


def test_prompt_budget_estimates_with_specialist(tmp_path: Path):
    store = AgentStore(tmp_path / "budget.db")
    fast = store.get_specialist_by_slug("fast-computational-scientist")
    assert fast is not None

    async def _run():
        none_est = await PromptBudgetService(store).estimate(sample_query="Hello")
        fast_est = await PromptBudgetService(store).estimate(
            specialist_id=fast.id, sample_query="Hello"
        )
        return none_est, fast_est

    none_est, fast_est = asyncio.run(_run())
    assert none_est.total_tokens > 0
    assert fast_est.total_tokens > 0
    assert none_est.tool_counts.total >= none_est.tool_counts.domain
    assert {b.id for b in none_est.buckets} >= {
        "system_prompt",
        "domain_tools",
        "mcp_tools",
        "skills",
        "deepagents",
    }
    assert "user" not in {b.id for b in none_est.buckets}
    system_bucket = next(b for b in none_est.buckets if b.id == "system_prompt")
    child_ids = {c.id for c in system_bucket.children}
    assert "sandwalk_system" in child_ids
    assert "deepagents_base" in child_ids
    assert fast_est.specialist_id == fast.id
    assert fast_est.specialist_name == fast.name
    skills_fast = next(b for b in fast_est.buckets if b.id == "skills")
    # The bucket counts skills that actually resolve, so compare against the
    # specialist's names that are installed here rather than all of them.
    installed = {s.name for s in list_skills(enabled_only=False)}
    assert skills_fast.count == len(installed & set(fast.skill_names))
