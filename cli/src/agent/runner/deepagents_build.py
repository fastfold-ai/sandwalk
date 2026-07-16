"""DeepAgentsBuildMixin: tool/prompt/agent construction and result assembly for
the deepagents (LangGraph) runtime path.

Extracted from the (formerly monolithic) ``_run_async_deepagents`` method in
``agent/runner.py`` so both that method and this module stay under the
project line-count limit. Each helper here is called with already-resolved
runtime callables (imported once, up front, in
``DeepAgentsRunMixin._run_async_deepagents``) so a missing/broken deepagents
install still surfaces as a single, clear preflight error.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from agent.runner_helpers import _looks_like_unverified_execution_claim
from agent.types import ExecutionResult, Plan, Step

logger = logging.getLogger("runner")


class DeepAgentsBuildMixin:
    """Tool/prompt/agent construction and result assembly for deepagents runs."""

    async def _build_deepagents_tools(
        self,
        config,
        ctx: dict,
        provider: str,
        create_ct_langchain_tools,
        create_external_mcp_tools,
        finalize_tools_for_provider,
    ):
        """Resolve, merge, and cap the domain/external/sandbox-control tool list."""
        exclude_cats = set()
        if not config.get("agent.enable_experimental_tools", False):
            from tools import EXPERIMENTAL_CATEGORIES

            exclude_cats = set(EXPERIMENTAL_CATEGORIES)

        tool_mode = str(config.get("agent.tool_mode", "native") or "native").strip().lower()

        # User-disabled tools (Dashboard → Tools) are excluded from discovery.
        exclude_tool_names = set(config.hidden_tools())
        # Specialist allowlist: when present (including empty), only those
        # registry tools remain — empty means runtime pins only.
        allowed_tool_names = ctx.get("allowed_tool_names")
        if allowed_tool_names is not None:
            from tools import ensure_loaded, registry

            ensure_loaded()
            allow = {
                str(name).strip()
                for name in (allowed_tool_names or [])
                if str(name).strip()
            }
            for tool_obj in registry.list_tools():
                if tool_obj.name not in allow:
                    exclude_tool_names.add(tool_obj.name)

        session_id_for_tools = str(
            ctx.get("session_id")
            or getattr(self.trajectory, "session_id", "")
            or ""
        ).strip()
        tools, sandbox, code_trace_buffer, display_name_map = create_ct_langchain_tools(
            self.session,
            exclude_categories=exclude_cats,
            exclude_tools=exclude_tool_names,
            provider=provider,
            tool_mode=tool_mode,
            session_id=session_id_for_tools or None,
        )
        try:
            external_tools = await create_external_mcp_tools(ctx.get("mcp_servers"))
            existing_names = {getattr(tool, "name", "") for tool in tools}
            tools.extend(
                tool
                for tool in external_tools
                if getattr(tool, "name", "") not in existing_names
            )
        except Exception as mcp_error:  # noqa: BLE001
            logger.warning("Unable to load external MCP tools: %s", mcp_error)

        if session_id_for_tools:
            try:
                from agent.sandbox_control_tools import create_sandbox_control_tools

                existing_names = {getattr(tool, "name", "") for tool in tools}
                for tool in create_sandbox_control_tools(session_id_for_tools):
                    name = getattr(tool, "name", "")
                    if name and name not in existing_names:
                        tools.append(tool)
                        display_name_map[name] = name
                        existing_names.add(name)
            except Exception as sandbox_tools_error:  # noqa: BLE001
                logger.warning(
                    "Unable to load sandbox control tools: %s",
                    sandbox_tools_error,
                )

        # OpenAI rejects >128 tools. MCP servers (esp. Neurosnap) can push
        # the merged list well over that — cap after merge, before
        # create_deep_agent adds its own builtins.
        tools = finalize_tools_for_provider(tools, provider)
        kept_names = {getattr(t, "name", "") for t in tools}
        display_name_map = {
            name: label
            for name, label in display_name_map.items()
            if name in kept_names
        }

        return (
            tools,
            sandbox,
            code_trace_buffer,
            display_name_map,
            tool_mode,
            exclude_cats,
            exclude_tool_names,
        )

    def _build_deepagents_system_prompt(
        self,
        config,
        ctx: dict,
        tools,
        tool_mode: str,
        exclude_cats,
        exclude_tool_names,
        build_system_prompt,
    ) -> str:
        """Build the system prompt (skills handled natively by deepagents)."""
        data_context = None
        data_dir = ctx.get("data_dir")
        if data_dir:
            data_context = f"Data directory: {data_dir}\n"
            config.set("sandbox.extra_read_dirs", str(data_dir))

        history = None
        if self.trajectory and self.trajectory.turns:
            history = self.trajectory.context_for_planner()

        tool_names = [getattr(t, "name", "") for t in tools]
        sandbox_backend_hint = str(
            ctx.get("sandbox_backend") or ""
        ).strip().lower() or None
        if sandbox_backend_hint not in {"builtin", "modal"}:
            sandbox_backend_hint = None
        return build_system_prompt(
            self.session,
            tool_names=tool_names,
            data_context=data_context,
            history=history,
            include_skills=False,
            runtime="deepagents",
            tool_mode=tool_mode,
            exclude_categories=exclude_cats,
            exclude_tools=exclude_tool_names,
            project_context=ctx.get("project_context"),
            specialist_instructions=ctx.get("specialist_instructions"),
            workspace_path=ctx.get("workspace_path"),
            sandbox_backend=sandbox_backend_hint,
        )

    def _build_deepagents_user_prompt(self, query: str, ctx: dict) -> tuple[str, dict]:
        """Resolve the session workspace and append run context to the user prompt."""
        user_prompt = query
        context_parts = []
        workspace_path = str(ctx.get("workspace_path") or "").strip()
        if not workspace_path and self.trajectory is not None:
            session_id = str(
                getattr(self.trajectory, "session_id", "") or ""
            ).strip()
            if session_id:
                try:
                    from agent_server.service import resolve_session_workspace
                    from agent_server.store import AgentStore

                    workspace_path = str(
                        resolve_session_workspace(
                            session_id, store=AgentStore(), persist=True
                        )
                    )
                    ctx = {**ctx, "workspace_path": workspace_path}
                except Exception:
                    workspace_path = ""
        if workspace_path:
            # Align shell/skill subprocesses with the UI file tree.
            os.environ["SANDWALK_SESSION_WORKSPACE"] = workspace_path
            Path(workspace_path).joinpath("artifacts").mkdir(
                parents=True, exist_ok=True
            )
            Path(workspace_path).joinpath("outputs").mkdir(
                parents=True, exist_ok=True
            )
            Path(workspace_path).joinpath("plans").mkdir(
                parents=True, exist_ok=True
            )
            context_parts.append(
                "Internal session workspace path (do not recite in replies "
                "unless the user asks where files are; still use this absolute "
                f"path for all downloads/writes): {workspace_path}"
            )
            try:
                from agent.system_prompt.mode_section import list_recent_plan_files

                recent_plans = list_recent_plan_files(workspace_path)
            except Exception:
                recent_plans = []
            cfg = getattr(self.session, "config", None)
            plan_mode = bool(cfg.get("agent.plan_preview", False)) if cfg else False
            if recent_plans and not plan_mode:
                context_parts.append(
                    "Pending plan files (newest first): "
                    + ", ".join(recent_plans)
                )
        if ctx.get("compound_smiles"):
            context_parts.append(f"Compound SMILES: {ctx['compound_smiles']}")
        if ctx.get("target"):
            context_parts.append(f"Target: {ctx['target']}")
        if ctx.get("indication"):
            context_parts.append(f"Indication: {ctx['indication']}")
        if ctx.get("mention_context"):
            context_parts.append(ctx["mention_context"])
        if context_parts:
            user_prompt = query + "\n\nContext:\n" + "\n".join(context_parts)
        return user_prompt, ctx

    async def _build_deepagents_agent(
        self,
        config,
        ctx: dict,
        model,
        tools,
        system_prompt: str,
        create_deep_agent,
        resolve_skill_source_dirs,
    ):
        """Resolve the sandbox backend/skills and construct the deep agent graph."""
        # Deep Agents input context includes skills via progressive disclosure
        # (name+description at startup). Respect specialist allowlists and the
        # Skills UI enable/disable toggles — never pass raw on-disk roots.
        allowed_skill_names = ctx.get("allowed_skill_names")
        skills_sources = resolve_skill_source_dirs(
            None
            if allowed_skill_names is None
            else list(allowed_skill_names or [])
        )
        # Never root filesystem tools at "/" — relative paths like
        # ./artifacts/... would resolve to /artifacts/... and fail.
        workspace_root = str(ctx.get("workspace_path") or "").strip()
        if not workspace_root:
            workspace_root = str(Path.cwd().resolve())
        session_id = str(
            ctx.get("session_id")
            or getattr(self.trajectory, "session_id", "")
            or ""
        ).strip() or None
        backend_override = str(ctx.get("sandbox_backend") or "").strip().lower() or None
        if backend_override not in {"builtin", "modal"}:
            backend_override = None
        from agent.sandbox_backend import (
            resolve_deepagents_backend,
            sandbox_backend_from_config,
            wait_until_seeded,
        )

        effective_backend = backend_override or sandbox_backend_from_config(config)
        sandbox_handle = resolve_deepagents_backend(
            config,
            session_id=session_id,
            workspace_root=workspace_root,
            skill_source_dirs=skills_sources,
            backend_override=backend_override,
            # Workspace-only sync; never upload skills. Background so the
            # LLM turn is not blocked on Modal FS I/O during attach — we
            # await seed completion below before the agent can tool-call.
            sync_workspace=True,
            background_sync=effective_backend == "modal",
        )
        if sandbox_handle.kind == "modal" and not sandbox_handle.seeded:
            import asyncio

            seeded_ok = await asyncio.to_thread(
                wait_until_seeded,
                sandbox_handle,
                timeout=120.0,
            )
            if not seeded_ok:
                logger.warning(
                    "Proceeding with Modal agent turn before workspace seed "
                    "finished (session=%s)",
                    session_id,
                )
        backend = sandbox_handle.backend
        agent_skills = sandbox_handle.skills_sources or None
        agent = create_deep_agent(
            model=model,
            tools=tools,
            system_prompt=system_prompt,
            skills=agent_skills,
            backend=backend,
        )
        return agent, sandbox_handle

    def _build_deepagents_exec_result(
        self,
        query: str,
        result: dict,
        t0: float,
        model_name: str,
        sandbox,
        trace_events,
        model_pricing: dict,
    ) -> ExecutionResult:
        """Assemble the ``ExecutionResult`` for a completed deepagents run."""
        duration = time.time() - t0
        full_text = result["full_text"]
        tool_calls = result["tool_calls"]
        token_usage = dict(result.get("token_usage") or {})
        model_call_count = int(result.get("model_call_count", 0))

        summary = "\n".join(full_text).strip() or "(Agent produced no text output)"
        guardrail_unverified_execution = False
        if _looks_like_unverified_execution_claim(summary, tool_calls):
            guardrail_unverified_execution = True
            summary = (
                "I did not execute any tool calls in this turn, so I cannot confirm a submission, "
                "status, or generated job/workflow ID. Ask me to run the submission now and I will "
                "execute it and return the real ID from tool output."
            )

        answer = None
        if sandbox:
            result_var = sandbox.get_variable("result")
            if isinstance(result_var, dict):
                answer = result_var.get("answer")

        steps = []
        for i, tc in enumerate(tool_calls, 1):
            step = Step(
                id=i,
                tool=tc["name"],
                description=f"Called {tc['name']}",
                tool_args=tc.get("input", {}),
            )
            step.status = "completed"
            steps.append(step)
        plan = Plan(query=query, steps=steps)

        pricing = model_pricing.get(model_name, {})
        input_cost = (
            float(token_usage.get("input_tokens", 0)) / 1_000_000.0 * float(pricing.get("input", 0.0))
        )
        output_cost = (
            float(token_usage.get("output_tokens", 0)) / 1_000_000.0 * float(pricing.get("output", 0.0))
        )
        total_cost_usd = input_cost + output_cost

        exec_result = ExecutionResult(
            plan=plan,
            summary=summary,
            raw_results={
                "tool_calls": tool_calls,
                "answer": answer,
                "pending_background_tasks": [],
                "completed_background_tasks": [],
            },
            duration_s=duration,
            iterations=1,
            metadata={
                "sdk_cost_usd": total_cost_usd,
                "sdk_total_cost_usd": total_cost_usd,
                "sdk_model_usage_cost_usd": total_cost_usd,
                "sdk_server_tool_cost_usd": 0.0,
                "sdk_cost_split_known": bool(pricing),
                "sdk_turns": model_call_count or (len(tool_calls) + 1),
                "sdk_duration_ms": int(duration * 1000),
                "sdk_model": model_name,
                "sdk_models": [model_name] if model_name else [],
                "sdk_input_tokens": int(token_usage.get("input_tokens", 0)),
                "sdk_output_tokens": int(token_usage.get("output_tokens", 0)),
                "sdk_cache_creation_input_tokens": int(token_usage.get("cache_creation_input_tokens", 0)),
                "sdk_cache_read_input_tokens": int(token_usage.get("cache_read_input_tokens", 0)),
                "tool_call_count": len(tool_calls),
                "guardrail_unverified_execution": guardrail_unverified_execution,
                "pending_background_task_count": 0,
                "completed_background_task_count": 0,
                "runtime": "deepagents",
            },
        )

        if self.trace_store is not None and trace_events:
            try:
                self.trace_store.add_events(
                    trace_events,
                    query=query,
                    model=model_name,
                    duration_s=duration,
                    cost_usd=total_cost_usd,
                )
                self.trace_store.flush()
            except Exception as e:  # noqa: BLE001
                logger.warning("Failed to flush trace: %s", e)

        if not self._headless:
            self._print_usage(
                None,
                duration,
                input_tokens=int(token_usage.get("input_tokens", 0)),
                output_tokens=int(token_usage.get("output_tokens", 0)),
                cache_read_tokens=int(token_usage.get("cache_read_input_tokens", 0)),
            )

        return exec_result
