"""DeepAgentsRunMixin: provider dispatch and the deepagents (LangGraph) query
orchestration for AgentRunner.

Split out of ``agent/runner.py`` (package conversion) to keep files under the
project line-count limit. Tool/prompt/agent construction and result assembly
are delegated to ``DeepAgentsBuildMixin`` (``deepagents_build.py``); this file
keeps the top-level dispatch, the runtime preflight import, and the
try/except/finally spinner lifecycle that ties those pieces together.
"""

from __future__ import annotations

import asyncio
import logging
import time
import traceback

from agent.runner_helpers import _classify_llm_error
from agent.types import ExecutionResult

logger = logging.getLogger("runner")


def _merge_deepagents_chunks(acc: dict, chunk: dict) -> dict:
    """Merge successive ``process_events`` results across HITL resume loops."""
    usage = dict(acc.get("token_usage") or {})
    for key, value in dict(chunk.get("token_usage") or {}).items():
        try:
            usage[key] = int(usage.get(key, 0) or 0) + int(value or 0)
        except (TypeError, ValueError):
            usage[key] = value
    return {
        "full_text": list(acc.get("full_text") or [])
        + list(chunk.get("full_text") or []),
        "tool_calls": list(acc.get("tool_calls") or [])
        + list(chunk.get("tool_calls") or []),
        "token_usage": usage,
        "model_call_count": int(acc.get("model_call_count", 0) or 0)
        + int(chunk.get("model_call_count", 0) or 0),
    }


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

        if provider not in (
            "anthropic",
            "openai",
            "xai",
            "google",
            "moonshot",
            "nvidia",
            "opencode",
            "deepseek",
            "minimax",
            "mistral",
            "qwen",
            "together",
            "openrouter",
        ):
            return self._make_error_result(
                query,
                f"Unsupported llm.provider '{provider}'. Use 'anthropic', 'openai', "
                "'xai', 'google', 'moonshot', 'nvidia', 'opencode', 'deepseek', "
                "'minimax', 'mistral', 'qwen', 'together', or 'openrouter' "
                "(OpenAI-compatible endpoints via llm.openai_base_url).",
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

            transcript = getattr(self.session, "transcript", None)
            sink = None
            if transcript is not None:
                from ui.terminal.transcript.sink import TranscriptSink

                sink = TranscriptSink(transcript)
            trace_renderer = TraceRenderer(
                self.session.console,
                config=getattr(self.session, "config", None),
                expand_store=getattr(self.session, "tool_expand_store", None),
                sink=sink,
            )
            trace_events: list[dict] | None = [] if self.trace_store is not None else None

            # LangGraph requires a finite recursion_limit (no documented upper bound;
            # default in langgraph 1.2.x is ~10k). We always pass a very high cap so
            # long training/fold workflows are not cut off by a product setting.
            from agent_server.settings_service.limits import UNLIMITED_RECURSION_LIMIT

            recursion_limit = UNLIMITED_RECURSION_LIMIT
            model_name = config.get("llm.model") or (
                "claude-sonnet-4-5-20250929" if provider == "anthropic" else "gpt-5.6-sol"
            )

            # Expand @path multimodal attachments into standard content blocks
            # when the model supports that modality (LangChain/Deep Agents).
            # Raises MultimodalInjectionError if a vision model should see
            # pixels but injection failed (avoids silent text-only hallucinations).
            from agent.runner.multimodal_user_message import (
                MultimodalInjectionError,
                build_multimodal_user_content,
            )

            workspace_root = str(ctx.get("workspace_path") or "").strip()
            try:
                user_content = build_multimodal_user_content(
                    user_prompt,
                    workspace_root=workspace_root or None,
                    provider=provider,
                    model_id=str(model_name or ""),
                    profile=getattr(model, "profile", None),
                )
            except MultimodalInjectionError as inj_exc:
                duration = time.time() - t0
                logger.error("multimodal injection failed: %s", inj_exc)
                return self._make_error_result(query, str(inj_exc), duration)

            from langgraph.types import Command

            from agent.hitl import (
                apply_grants_from_decisions,
                clear_session_grants,
                collect_decisions_for_interrupt,
                extract_interrupt_payload,
                reset_hitl_context,
                set_hitl_context,
            )

            session_id = str(
                ctx.get("session_id")
                or getattr(self.trajectory, "session_id", "")
                or ""
            ).strip()
            thread_id = session_id or f"cli-{id(self)}"
            run_config = {
                "configurable": {"thread_id": thread_id},
                "recursion_limit": recursion_limit,
            }
            stream_input: object = {
                "messages": [{"role": "user", "content": user_content}]
            }
            result = {
                "full_text": [],
                "tool_calls": [],
                "token_usage": {},
                "model_call_count": 0,
            }
            # PTC tools.* callables bypass LangGraph interrupt_on; expose the
            # same approval broker / CLI collector via a per-run contextvar.
            hitl_token = set_hitl_context(
                session_id=session_id or None,
                headless=bool(self._headless),
                progress_callback=progress_callback,
                console=getattr(self.session, "console", None),
            )
            try:
                while True:
                    events = agent.astream_events(
                        stream_input,
                        version="v2",
                        config=run_config,
                    )
                    try:
                        chunk = await process_events(
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
                            group_tools=bool(
                                config.get("agent.group_tool_traces", True)
                            ),
                            tool_detail_limit=int(
                                config.get("agent.tool_trace_detail_limit", 0)
                            ),
                        )
                    except Exception as stream_exc:  # noqa: BLE001
                        # Some LangGraph versions surface interrupts as GraphInterrupt.
                        from langgraph.errors import GraphInterrupt

                        if not isinstance(stream_exc, GraphInterrupt):
                            raise
                        chunk = {
                            "full_text": [],
                            "tool_calls": [],
                            "token_usage": {},
                            "model_call_count": 0,
                        }
                    thinking_status = None  # consumed by process_events
                    t_stream_end = time.time()
                    result = _merge_deepagents_chunks(result, chunk)
                    interrupt_payload = await asyncio.to_thread(
                        extract_interrupt_payload, agent, run_config
                    )
                    logger.info(
                        "[perf] deepagents: interrupt-state check %.2fs after stream end",
                        time.time() - t_stream_end,
                    )
                    if interrupt_payload is None:
                        break
                    decisions = await asyncio.to_thread(
                        collect_decisions_for_interrupt,
                        session_id=session_id or None,
                        action_requests=interrupt_payload["action_requests"],
                        review_configs=interrupt_payload["review_configs"],
                        headless=bool(self._headless),
                        progress_callback=progress_callback,
                        console=getattr(self.session, "console", None),
                    )
                    apply_grants_from_decisions(
                        decisions,
                        interrupt_payload["action_requests"],
                        session_id=session_id or None,
                    )
                    if progress_callback is not None:
                        try:
                            progress_callback(
                                "approval_resolved",
                                decisions=decisions,
                            )
                        except Exception:  # noqa: BLE001
                            logger.debug(
                                "approval_resolved progress callback failed",
                                exc_info=True,
                            )
                    stream_input = Command(resume={"decisions": decisions})
            finally:
                clear_session_grants(session_id or None)
                reset_hitl_context(hitl_token)
            if sandbox_handle is not None and sandbox_handle.kind == "modal":
                t_pull = time.time()
                try:
                    sandbox_handle.pull()
                except Exception as pull_exc:  # noqa: BLE001
                    logger.warning("Modal workspace pull failed: %s", pull_exc)
                logger.info(
                    "[perf] deepagents: modal workspace pull %.2fs",
                    time.time() - t_pull,
                )
        except InterruptedError:
            if thinking_status is not None:
                thinking_status.stop()
                thinking_status = None
            raise
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

        t_build = time.time()
        exec_result = self._build_deepagents_exec_result(
            query, result, t0, model_name, sandbox, trace_events, MODEL_PRICING
        )
        logger.info(
            "[perf] deepagents: build result %.2fs (total run %.2fs)",
            time.time() - t_build,
            time.time() - t0,
        )
        return exec_result
