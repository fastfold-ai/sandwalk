"""Assemble the system prompt text + per-section buckets for a budget estimate."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from agent_server.models import PromptBudgetBucket
from agent_server.prompt_budget_service.context import BudgetContext
from agent_server.prompt_budget_service.tokens import bucket_from_text

logger = logging.getLogger("prompt_budget")


@dataclass
class PromptBuild:
    user_system_prompt: str = ""
    assembled_system: str = ""
    section_children: list[PromptBudgetBucket] = field(default_factory=list)
    skills_text: str = ""
    skill_count: int = 0
    deepagents_text: str = ""
    deepagents_names: list[str] = field(default_factory=list)


def build_prompt(
    *,
    session: Any,
    tool_names: list[str],
    tool_mode: str,
    exclude_cats: set[str],
    ctx: BudgetContext,
    project_context: str | None,
    final_tools: list[Any],
    cfg: Any,
    model: str | None,
) -> PromptBuild:
    from deepagents.graph import BASE_AGENT_PROMPT

    from agent.deepagents_runtime import (
        build_skills_index_text,
        measure_deepagents_builtin_tool_schemas,
        resolve_skill_source_dirs,
    )
    from agent.system_prompt import build_system_prompt

    result = PromptBuild()
    result.user_system_prompt = build_system_prompt(
        session,
        tool_names=tool_names,
        include_skills=False,
        runtime="deepagents",
        tool_mode=tool_mode,
        exclude_categories=exclude_cats,
        exclude_tools=ctx.exclude_tool_names,
        project_context=project_context,
        specialist_instructions=ctx.specialist_instructions,
    )

    # Deep Agents assembles USER → BASE (harness) → middleware skills.
    deepagents_base = str(BASE_AGENT_PROMPT or "")
    result.assembled_system = (
        f"{result.user_system_prompt}\n\n{deepagents_base}"
        if deepagents_base.strip()
        else result.user_system_prompt
    )

    result.section_children = [
        bucket_from_text(
            id="sandwalk_system",
            label="sandwalk system prompt",
            text=result.user_system_prompt,
            model=model,
        ),
        bucket_from_text(
            id="deepagents_base",
            label="Deep Agents BASE prompt",
            text=deepagents_base,
            model=model,
        ),
    ]
    remainder = result.user_system_prompt
    if ctx.specialist_instructions:
        block = f"\n## Specialist Instructions\n\n{ctx.specialist_instructions}"
        if block in remainder:
            result.section_children.append(
                bucket_from_text(
                    id="specialist", label="Specialist instructions", text=block, model=model
                )
            )
    if project_context:
        block = f"\n## Project Context\n\n{str(project_context).strip()}"
        if block in remainder:
            result.section_children.append(
                bucket_from_text(id="project", label="Project context", text=block, model=model)
            )

    result.skills_text, result.skill_count = build_skills_index_text(ctx.allowed_skill_names)
    skills_sources = resolve_skill_source_dirs(ctx.allowed_skill_names)

    try:
        deepagents_text, deepagents_names = measure_deepagents_builtin_tool_schemas(
            domain_tools=final_tools,
            system_prompt=result.user_system_prompt,
            skills_sources=skills_sources,
            config=cfg,
        )
        result.deepagents_text, result.deepagents_names = deepagents_text, deepagents_names
    except Exception as exc:  # noqa: BLE001
        logger.warning("prompt budget deepagents tool measure failed: %s", exc)
        result.deepagents_text, result.deepagents_names = "", []

    return result
