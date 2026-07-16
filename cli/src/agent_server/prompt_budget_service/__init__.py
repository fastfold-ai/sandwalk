"""Live input-token context estimates for Dashboard → Prompts.

Aligned with Deep Agents *input context* composition
(https://docs.langchain.com/oss/python/deepagents/context-engineering):

  custom system prompt (USER) + harness BASE + skills index + tool schemas

Runtime context (LangGraph ``context=`` / store) is *not* LLM input — see
https://docs.langchain.com/oss/python/concepts/context

Split package — re-exports the public surface previously defined in
``agent_server/prompt_budget_service.py`` so existing imports keep working.
"""

from __future__ import annotations

from agent.config import Config
from agent_server.models import PromptBudgetResponse, PromptBudgetToolCounts
from agent_server.prompt_budget_service.context import resolve_budget_context
from agent_server.prompt_budget_service.prompt_build import build_prompt
from agent_server.prompt_budget_service.tokens import (
    bucket_from_text,
    estimate_tokens,
    tool_schema_text,
)
from agent_server.prompt_budget_service.tool_loading import build_tool_sets
from agent_server.prompt_budget_service.warnings_build import build_warnings
from agent_server.store import AgentStore

# Re-exported for backward-compat imports (e.g. tests importing this name directly).
_estimate_tokens = estimate_tokens


class PromptBudgetService:
    def __init__(self, store: AgentStore) -> None:
        self._store = store

    async def estimate(
        self,
        *,
        specialist_id: str | None = None,
        project_id: str | None = None,
        sample_query: str | None = None,  # kept for API compat; not in static estimate
    ) -> PromptBudgetResponse:
        _ = sample_query
        from tools import EXPERIMENTAL_CATEGORIES

        cfg = Config.load()
        model = str(cfg.get("llm.model") or "")
        provider = str(cfg.get("llm.provider") or "anthropic").strip().lower()
        tool_mode = str(cfg.get("agent.tool_mode") or "ptc").strip().lower()
        exclude_cats: set[str] = set()
        if not cfg.get("agent.enable_experimental_tools", False):
            exclude_cats = set(EXPERIMENTAL_CATEGORIES)

        ctx = resolve_budget_context(
            self._store, cfg, specialist_id=specialist_id, project_id=project_id
        )

        from agent.session import Session

        session = Session(config=cfg, verbose=False, mode="batch")
        tool_sets = await build_tool_sets(
            session=session,
            provider=provider,
            tool_mode=tool_mode,
            exclude_cats=exclude_cats,
            ctx=ctx,
        )

        tool_names = [getattr(t, "name", "") for t in tool_sets.final_tools]
        prompt = build_prompt(
            session=session,
            tool_names=tool_names,
            tool_mode=tool_mode,
            exclude_cats=exclude_cats,
            ctx=ctx,
            project_context=ctx.project_context,
            final_tools=tool_sets.final_tools,
            cfg=cfg,
            model=model,
        )

        deepagents_count = len(prompt.deepagents_names)
        uncapped_total = len(tool_sets.merged) + max(deepagents_count, 1)

        domain_text = "\n\n".join(tool_schema_text(t) for t in tool_sets.final_domain)
        mcp_text = "\n\n".join(tool_schema_text(t) for t in tool_sets.final_mcp)

        buckets = [
            bucket_from_text(
                id="system_prompt",
                label="System prompt (USER + BASE)",
                text=prompt.assembled_system,
                model=model,
                children=prompt.section_children,
            ),
            bucket_from_text(
                id="domain_tools",
                label="Domain / runtime tool schemas",
                text=domain_text,
                model=model,
                count=len(tool_sets.final_domain),
            ),
            bucket_from_text(
                id="mcp_tools",
                label="MCP tool schemas",
                text=mcp_text,
                model=model,
                count=len(tool_sets.final_mcp),
            ),
            bucket_from_text(
                id="deepagents",
                label="Deep Agents builtin tool schemas",
                text=prompt.deepagents_text,
                model=model,
                count=deepagents_count,
            ),
            bucket_from_text(
                id="skills",
                label="Skills index (progressive disclosure)",
                text=prompt.skills_text,
                model=model,
                count=prompt.skill_count,
            ),
        ]

        total_chars = sum(b.chars for b in buckets)
        total_tokens = sum(b.tokens for b in buckets)
        _, tokenizer = estimate_tokens(prompt.user_system_prompt[:12_000], model=model)

        tool_total = len(tool_sets.final_tools) + deepagents_count
        warnings = build_warnings(
            provider=provider,
            uncapped_total=uncapped_total,
            tool_total=tool_total,
            deepagents_count=deepagents_count,
            total_tokens=total_tokens,
            specialist=ctx.specialist,
        )

        specialist = ctx.specialist
        return PromptBudgetResponse(
            total_tokens=total_tokens,
            total_chars=total_chars,
            tokenizer=tokenizer,
            tool_mode=tool_mode,
            provider=provider,
            model=model or None,
            specialist_id=specialist.id if specialist else None,
            specialist_name=specialist.name if specialist else None,
            tool_counts=PromptBudgetToolCounts(
                domain=len(tool_sets.final_domain),
                mcp=len(tool_sets.final_mcp),
                deepagents=deepagents_count,
                total=tool_total,
                openai_cap=128,
            ),
            buckets=buckets,
            warnings=warnings,
            sample_query="",
        )


__all__ = ["PromptBudgetService", "_estimate_tokens"]
