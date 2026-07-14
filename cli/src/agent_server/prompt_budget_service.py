"""Live input-token context estimates for Dashboard → Prompts.

Aligned with Deep Agents *input context* composition
(https://docs.langchain.com/oss/python/deepagents/context-engineering):

  custom system prompt (USER) + harness BASE + skills index + tool schemas

Runtime context (LangGraph ``context=`` / store) is *not* LLM input — see
https://docs.langchain.com/oss/python/concepts/context
"""

from __future__ import annotations

import json
import logging
from typing import Any

from agent.config import Config
from agent_server.models import (
    PromptBudgetBucket,
    PromptBudgetResponse,
    PromptBudgetToolCounts,
)
from agent_server.store import AgentStore

logger = logging.getLogger("prompt_budget")


def _estimate_tokens(text: str, *, model: str | None = None) -> tuple[int, str]:
    """Return (tokens, tokenizer_label). Prefer tiktoken on real text."""
    raw = text or ""
    if not raw:
        return 0, "tiktoken"
    try:
        import tiktoken

        encoding_name = "o200k_base"
        try:
            enc = tiktoken.encoding_for_model(str(model or "gpt-4o"))
            encoding_name = getattr(enc, "name", encoding_name) or encoding_name
        except Exception:
            try:
                enc = tiktoken.get_encoding("o200k_base")
            except Exception:
                enc = tiktoken.get_encoding("cl100k_base")
                encoding_name = "cl100k_base"
        # Cap encode size for pathological MCP dumps; scale linearly.
        limit = 400_000
        if len(raw) <= limit:
            return len(enc.encode(raw)), f"tiktoken:{encoding_name}"
        probe = len(enc.encode(raw[:limit]))
        return int(probe * (len(raw) / limit)), f"tiktoken:{encoding_name}"
    except Exception:
        return max(0, (len(raw) + 3) // 4), "chars/4"


def _tool_schema_text(tool: Any) -> str:
    name = str(getattr(tool, "name", "") or "")
    description = str(getattr(tool, "description", "") or "")
    schema: Any = {}
    args_schema = getattr(tool, "args_schema", None)
    if args_schema is not None:
        try:
            if hasattr(args_schema, "model_json_schema"):
                schema = args_schema.model_json_schema()
            elif isinstance(args_schema, dict):
                schema = args_schema
        except Exception:
            schema = {}
    try:
        schema_text = json.dumps(schema, ensure_ascii=True, default=str)
    except Exception:
        schema_text = str(schema)
    return f"{name}\n{description}\n{schema_text}"


def _bucket_from_text(
    *,
    id: str,
    label: str,
    text: str,
    model: str | None,
    count: int | None = None,
    children: list[PromptBudgetBucket] | None = None,
) -> PromptBudgetBucket:
    raw = text or ""
    tokens, _ = _estimate_tokens(raw, model=model)
    return PromptBudgetBucket(
        id=id,
        label=label,
        tokens=tokens,
        chars=len(raw),
        count=count,
        children=children or [],
    )


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
        from deepagents.graph import BASE_AGENT_PROMPT

        from agent.deepagents_runtime import (
            build_skills_index_text,
            create_ct_langchain_tools,
            create_external_mcp_tools,
            finalize_tools_for_provider,
            measure_deepagents_builtin_tool_schemas,
            resolve_skill_source_dirs,
        )
        from agent.session import Session
        from agent.system_prompt import build_system_prompt
        from agent_server.default_specialists import filter_mcp_servers_for_specialist
        from agent_server.mcp_service import McpService
        from tools import EXPERIMENTAL_CATEGORIES, ensure_loaded, registry

        cfg = Config.load()
        model = str(cfg.get("llm.model") or "")
        provider = str(cfg.get("llm.provider") or "anthropic").strip().lower()
        tool_mode = str(cfg.get("agent.tool_mode") or "ptc").strip().lower()
        exclude_cats: set[str] = set()
        if not cfg.get("agent.enable_experimental_tools", False):
            exclude_cats = set(EXPERIMENTAL_CATEGORIES)

        specialist = None
        if specialist_id:
            specialist = self._store.get_specialist(str(specialist_id).strip())

        project_context = None
        if project_id:
            project = self._store.get_project(str(project_id).strip())
            if project and project.agent_context:
                project_context = project.agent_context

        specialist_instructions = None
        allowed_skill_names = None
        allowed_tool_names = None
        mcp_servers = McpService(self._store).resolve_runtime_servers()
        if specialist is not None:
            if specialist.instructions and specialist.instructions.strip():
                specialist_instructions = specialist.instructions.strip()
            allowed_skill_names = list(specialist.skill_names or [])
            allowed_tool_names = list(specialist.tool_names or [])
            mcp_servers = filter_mcp_servers_for_specialist(
                mcp_servers,
                mcp_server_ids=list(specialist.mcp_server_ids or []),
                mcp_catalog_ids=list(specialist.mcp_catalog_ids or []),
            )

        exclude_tool_names = set(cfg.hidden_tools())
        if allowed_tool_names is not None:
            ensure_loaded()
            allow = {str(n).strip() for n in allowed_tool_names if str(n).strip()}
            for tool_obj in registry.list_tools():
                if tool_obj.name not in allow:
                    exclude_tool_names.add(tool_obj.name)

        session = Session(config=cfg, verbose=False, mode="batch")
        tools, _sandbox, _buf, _dmap = create_ct_langchain_tools(
            session,
            exclude_categories=exclude_cats,
            exclude_tools=exclude_tool_names,
            provider=provider,
            tool_mode=tool_mode,
        )
        domain_before = list(tools)
        domain_names = {getattr(t, "name", "") for t in domain_before}
        try:
            external = await create_external_mcp_tools(mcp_servers)
        except Exception as exc:  # noqa: BLE001
            logger.warning("prompt budget MCP load failed: %s", exc)
            external = []
        mcp_before = [
            t for t in external if getattr(t, "name", "") not in domain_names
        ]
        merged = list(domain_before) + list(mcp_before)
        final_tools = finalize_tools_for_provider(merged, provider)

        # Split post-cap tools back into domain vs MCP for honest counts.
        final_domain = [
            t for t in final_tools if getattr(t, "name", "") in domain_names
        ]
        final_mcp = [
            t for t in final_tools if getattr(t, "name", "") not in domain_names
        ]

        tool_names = [getattr(t, "name", "") for t in final_tools]
        user_system_prompt = build_system_prompt(
            session,
            tool_names=tool_names,
            include_skills=False,
            runtime="deepagents",
            tool_mode=tool_mode,
            exclude_categories=exclude_cats,
            exclude_tools=exclude_tool_names,
            project_context=project_context,
            specialist_instructions=specialist_instructions,
        )

        # Deep Agents assembles USER → BASE (harness) → middleware skills.
        deepagents_base = str(BASE_AGENT_PROMPT or "")
        assembled_system = (
            f"{user_system_prompt}\n\n{deepagents_base}"
            if deepagents_base.strip()
            else user_system_prompt
        )

        section_children: list[PromptBudgetBucket] = [
            _bucket_from_text(
                id="sandwalk_system",
                label="Sandwalk system prompt",
                text=user_system_prompt,
                model=model,
            ),
            _bucket_from_text(
                id="deepagents_base",
                label="Deep Agents BASE prompt",
                text=deepagents_base,
                model=model,
            ),
        ]
        remainder = user_system_prompt
        if specialist_instructions:
            block = f"\n## Specialist Instructions\n\n{specialist_instructions}"
            if block in remainder:
                section_children.append(
                    _bucket_from_text(
                        id="specialist",
                        label="Specialist instructions",
                        text=block,
                        model=model,
                    )
                )
        if project_context:
            block = f"\n## Project Context\n\n{str(project_context).strip()}"
            if block in remainder:
                section_children.append(
                    _bucket_from_text(
                        id="project",
                        label="Project context",
                        text=block,
                        model=model,
                    )
                )

        domain_text = "\n\n".join(_tool_schema_text(t) for t in final_domain)
        mcp_text = "\n\n".join(_tool_schema_text(t) for t in final_mcp)

        skills_text, skill_count = build_skills_index_text(allowed_skill_names)
        skills_sources = resolve_skill_source_dirs(allowed_skill_names)

        try:
            deepagents_text, deepagents_names = measure_deepagents_builtin_tool_schemas(
                domain_tools=final_tools,
                system_prompt=user_system_prompt,
                skills_sources=skills_sources,
                config=cfg,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("prompt budget deepagents tool measure failed: %s", exc)
            deepagents_text, deepagents_names = "", []

        deepagents_count = len(deepagents_names)
        uncapped_total = len(merged) + max(deepagents_count, 1)

        buckets = [
            _bucket_from_text(
                id="system_prompt",
                label="System prompt (USER + BASE)",
                text=assembled_system,
                model=model,
                children=section_children,
            ),
            _bucket_from_text(
                id="domain_tools",
                label="Domain / runtime tool schemas",
                text=domain_text,
                model=model,
                count=len(final_domain),
            ),
            _bucket_from_text(
                id="mcp_tools",
                label="MCP tool schemas",
                text=mcp_text,
                model=model,
                count=len(final_mcp),
            ),
            _bucket_from_text(
                id="deepagents",
                label="Deep Agents builtin tool schemas",
                text=deepagents_text,
                model=model,
                count=deepagents_count,
            ),
            _bucket_from_text(
                id="skills",
                label="Skills index (progressive disclosure)",
                text=skills_text,
                model=model,
                count=skill_count,
            ),
        ]

        total_chars = sum(b.chars for b in buckets)
        total_tokens = sum(b.tokens for b in buckets)
        _, tokenizer = _estimate_tokens(user_system_prompt[:12_000], model=model)

        tool_total = len(final_tools) + deepagents_count
        warnings: list[str] = []
        if provider == "openai" and uncapped_total > 128:
            warnings.append(
                f"OpenAI tool ceiling is 128; {uncapped_total} tools before cap "
                f"(kept {tool_total} including {deepagents_count} deepagents builtins)."
            )
        if provider == "openai" and tool_total > 116:
            warnings.append(
                f"Estimated {tool_total} tools after OpenAI headroom budget."
            )
        if total_tokens > 100_000:
            warnings.append(
                "Estimated input exceeds 100k tokens — trim MCP servers, use a "
                "lighter specialist, or keep PTC mode."
            )
        if specialist is not None and not (specialist.tool_names or []):
            warnings.append(
                "This specialist has an empty tool allowlist — only runtime "
                "pins (run_python / search_tools / shell) remain."
            )
        warnings.append(
            "Estimate is tiktoken on assembled text/schemas. Provider-billed "
            "input_tokens can be ~5–15% higher due to tools JSON envelope overhead."
        )

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
                domain=len(final_domain),
                mcp=len(final_mcp),
                deepagents=deepagents_count,
                total=tool_total,
                openai_cap=128,
            ),
            buckets=buckets,
            warnings=warnings,
            sample_query="",
        )
