"""DeepAgentsRunMixin: provider dispatch and the deepagents (LangGraph) query
orchestration for AgentRunner.

Split out of ``agent/runner.py`` (package conversion) to keep files under the
project line-count limit. Tool/prompt/agent construction and result assembly
are delegated to ``DeepAgentsBuildMixin`` (``deepagents_build.py``); this file
keeps the top-level dispatch, the runtime preflight import, and the
try/except/finally spinner lifecycle that ties those pieces together.
"""

from __future__ import annotations

import logging
import time
import traceback

from agent.runner_helpers import _classify_llm_error
from agent.types import ExecutionResult

logger = logging.getLogger("runner")


class DeepAgentsRunMixin:
    """Dispatches queries to the deepagents (LangGraph) runtime."""

    async def _run_async(
        self,
        query: str,
        context: dict | None = None,
        progress_callback=None,
    ) -> ExecutionResult:
        """Execute a query on the deepagents (LangGraph) runtime.

        deepagents is the only supported runtime. Anthropic and OpenAI
        (including OpenAI-compatible endpoints configured via
        ``llm.openai_base_url``) are dispatched to ``_run_async_deepagents``;
        any other provider returns a clear, actionable error.
        """
        provider = str(
            self.session.config.get("llm.provider", "anthropic") or "anthropic"
        ).strip().lower()

        if provider not in ("anthropic", "openai", "xai", "google", "nvidia", "opencode"):
            return self._make_error_result(
                query,
                f"Unsupported llm.provider '{provider}'. Use 'anthropic', 'openai', "
                "'xai', 'google', 'nvidia', or 'opencode' (OpenAI-compatible endpoints via "
                "llm.openai_base_url).",
                0.0,
            )

        # Preflight: surface missing/invalid API keys as a clear, actionable
        # message instead of a generic provider-rejected error mid-request.
        try:
            issue = self.session.config.llm_preflight_issue()
        except Exception:  # noqa: BLE001 - never block a run on preflight itself
            issue = None
        if issue:
            # Presentation layers render the summary as markdown; turn the
            # dashboard reference into a clickable in-app link.
            issue = issue.replace(
                "Dashboard → Models → API Keys",
                "[Dashboard → Models → API Keys](/dashboard/models)",
            )
            return self._make_error_result(query, issue, 0.0)

        return await self._run_async_deepagents(query, context, progress_callback)

    async def _run_async_deepagents(
        self,
        query: str,
        context: dict | None = None,
        progress_callback=None,
    ) -> ExecutionResult:
        """Execute a query on the deepagents (LangGraph) runtime.

        Builds a ``create_deep_agent`` graph with the ct domain tools wrapped as
        LangChain tools, native progressive-disclosure skills, and a model from
        ``init_chat_model``. Consumes ``astream_events`` via
        :func:`agent.deepagents_runtime.process_events`, which emits the same
        trace-event schema and progress callbacks as the SDK path.
        """
        t0 = time.time()
        config = self.session.config
        ctx = context or {}

        try:
            from deepagents import create_deep_agent

            from agent.deepagents_runtime import (
                build_chat_model,
                create_ct_langchain_tools,
                create_external_mcp_tools,
                finalize_tools_for_provider,
                process_events,
                resolve_skill_source_dirs,
            )
            from agent.system_prompt import build_system_prompt
            from models.llm import MODEL_PRICING
            from ui.traces import TraceRenderer
        except Exception as e:  # noqa: BLE001
            logger.error("deepagents runtime unavailable: %s\n%s", e, traceback.format_exc())
            return self._make_error_result(
                query,
                (
                    f"deepagents runtime is not available ({e}). Install the "
                    "deepagents/langchain stack (pip install -e .)."
                ),
                time.time() - t0,
            )

        provider = str(config.get("llm.provider", "anthropic") or "anthropic").strip().lower()

        allow_live_spinner = (not self._headless) and (progress_callback is None)
        thinking_status = None
        if allow_live_spinner:
            from ui.status import ThinkingStatus

            thinking_status = ThinkingStatus(self.session.console, phase="planning")
            thinking_status.__enter__()
            thinking_status.start_async_refresh()
            self._active_spinner = thinking_status

        try:
            sandbox_handle = None
            # ----- Model -----
            try:
                model = build_chat_model(config)
            except ValueError as e:
                if thinking_status is not None:
                    thinking_status.stop()
                return self._make_error_result(query, str(e), time.time() - t0)

            # ----- Tools -----
            (
                tools,
                sandbox,
                code_trace_buffer,
                display_name_map,
                tool_mode,
                exclude_cats,
                exclude_tool_names,
            ) = await self._build_deepagents_tools(
                config,
                ctx,
                provider,
                create_ct_langchain_tools,
                create_external_mcp_tools,
                finalize_tools_for_provider,
            )

            # ----- System prompt (skills handled natively by deepagents) -----
            system_prompt = self._build_deepagents_system_prompt(
                config,
                ctx,
                tools,
                tool_mode,
                exclude_cats,
                exclude_tool_names,
                build_system_prompt,
            )

            # ----- User prompt -----
            user_prompt, ctx = self._build_deepagents_user_prompt(query, ctx)

            # ----- Build agent -----
            agent, sandbox_handle = await self._build_deepagents_agent(
                config,
                ctx,
                model,
                tools,
                system_prompt,
                create_deep_agent,
                resolve_skill_source_dirs,
            )

            trace_renderer = TraceRenderer(
                self.session.console,
                config=getattr(self.session, "config", None),
            )
            trace_events: list[dict] | None = [] if self.trace_store is not None else None

            max_turns = int(config.get("agent.max_sdk_turns", 30) or 30)
            raw_recursion = config.get("agent.recursion_limit")
            if raw_recursion is None or str(raw_recursion).strip() == "":
                recursion_limit = max(25, max_turns * 2 + 10)
            else:
                try:
                    recursion_limit = max(25, int(raw_recursion))
                except (TypeError, ValueError):
                    recursion_limit = max(25, max_turns * 2 + 10)
            model_name = config.get("llm.model") or (
                "claude-sonnet-4-5-20250929" if provider == "anthropic" else "gpt-5.6-sol"
            )

            events = agent.astream_events(
                {"messages": [{"role": "user", "content": user_prompt}]},
                version="v2",
                config={"recursion_limit": recursion_limit},
            )
            result = await process_events(
                events,
                trace_renderer=trace_renderer,
                headless=self._headless,
                trace_events=trace_events,
                thinking_status=thinking_status,
                allow_live_spinner=allow_live_spinner,
                runner=self,
                on_activity=progress_callback,
                code_trace_buffer=code_trace_buffer,
                display_name_map=display_name_map,
                group_tools=bool(config.get("agent.group_tool_traces", True)),
                tool_detail_limit=int(config.get("agent.tool_trace_detail_limit", 8)),
            )
            thinking_status = None  # consumed by process_events
            if sandbox_handle is not None and sandbox_handle.kind == "modal":
                try:
                    sandbox_handle.pull()
                except Exception as pull_exc:  # noqa: BLE001
                    logger.warning("Modal workspace pull failed: %s", pull_exc)
        except Exception as e:  # noqa: BLE001
            duration = time.time() - t0
            if thinking_status is not None:
                thinking_status.stop()
                thinking_status = None
            classified = _classify_llm_error(e)
            if classified is not None:
                title, body = classified
                # Keep the console clean, but always record the provider detail +
                # traceback at WARNING so local serve logs are debuggable.
                logger.warning(
                    "deepagents query failed (%s): %s\n%s", title, e, traceback.format_exc()
                )
                self._print_friendly_error(title, body)
                return self._make_error_result(
                    query, f"{title}: {body.splitlines()[0]}", duration
                )
            logger.error("deepagents query failed: %s\n%s", e, traceback.format_exc())
            return self._make_error_result(query, str(e), duration)
        finally:
            if thinking_status is not None:
                thinking_status.stop()

        return self._build_deepagents_exec_result(
            query, result, t0, model_name, sandbox, trace_events, MODEL_PRICING
        )
