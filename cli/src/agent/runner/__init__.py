"""
AgentRunner: query entry point for the deepagents (LangGraph) runtime.

A single agentic loop where the model directly orchestrates all domain tools.
Anthropic and OpenAI (including OpenAI-compatible endpoints) are supported.

This is a package (not a single module) so each concern stays under the
project line-count limit. ``AgentRunner`` itself is assembled from sibling
mixins, each covering one slice of behavior:

- ``sync_loop``: blocking event-loop bridge + Ctrl+C/interrupt handling
- ``deepagents_run`` / ``deepagents_build``: the deepagents (LangGraph) query
  path — dispatch/orchestration vs. tool/prompt/agent construction
- ``plan_preview``: freeform-plan parsing + Mermaid flowchart helpers for plan md
- ``background_watch``: background task notifications + output-file polling
- ``usage_ui``: usage footer, friendly error rendering, error results

``from agent.runner import AgentRunner`` keeps working unchanged, and helper
functions from ``agent.runner_helpers`` are re-imported here (as before) so
``agent.runner.<name>`` monkeypatches used across the test suite keep
resolving to the live implementation.
"""

import asyncio
import logging
import os
import select
import signal
import sys
import threading
from pathlib import Path
from typing import Any

# os/select/signal/sys/Path are stdlib singletons: unused here directly, but
# imported so ``agent.runner.<module>.<attr>`` monkeypatches used across the
# test suite (targeting code that now lives in sibling mixin files) keep
# resolving — patching the singleton's attribute affects every importer.
from agent.runner.background_watch import BackgroundWatchMixin
from agent.runner.deepagents_build import DeepAgentsBuildMixin
from agent.runner.deepagents_run import DeepAgentsRunMixin
from agent.runner.plan_preview import PlanMermaidMixin, PlanPreviewMixin
from agent.runner.sync_loop import SyncLoopMixin
from agent.runner.usage_ui import UsageUIMixin
from agent.runner_helpers import (
    _classify_llm_error,
    _default_local_task_output_path,
    _discover_local_task_output_file,
    _extract_task_output_paths_from_text,
    _is_warp_terminal_env,
    _looks_like_unverified_execution_claim,
    _parse_task_probe_json,
    _provider_error_detail,
    _sanitize_notification_text,
)
from agent.types import ExecutionResult

logger = logging.getLogger("runner")

# Re-imported so ``agent.runner._classify_llm_error`` etc. (extensively
# monkeypatched by tests) keep resolving to the live implementations in
# ``agent.runner_helpers``; see that module's docstring for the split rationale.
__all__ = [
    "AgentRunner",
    "_classify_llm_error",
    "_default_local_task_output_path",
    "_discover_local_task_output_file",
    "_extract_task_output_paths_from_text",
    "_is_warp_terminal_env",
    "_looks_like_unverified_execution_claim",
    "_parse_task_probe_json",
    "_provider_error_detail",
    "_sanitize_notification_text",
]


class AgentRunner(
    SyncLoopMixin,
    DeepAgentsRunMixin,
    DeepAgentsBuildMixin,
    PlanMermaidMixin,
    BackgroundWatchMixin,
    UsageUIMixin,
):
    """Run queries via the Claude Agent SDK agentic loop.

    All 192 domain tools are exposed as MCP tools.  Claude handles planning,
    execution, error recovery, and synthesis in one conversation.
    """

    def __init__(
        self,
        session,
        trajectory=None,
        headless: bool = False,
        trace_store=None,
    ):
        self.session = session
        self.trajectory = trajectory
        self._headless = headless
        self.trace_store = trace_store
        self._active_client_lock = threading.Lock()
        self._active_client: Any | None = None
        self._active_loop: asyncio.AbstractEventLoop | None = None
        self._active_task: asyncio.Task | None = None
        self._bg_watch_lock = threading.Lock()
        self._bg_watchers: dict[str, threading.Thread] = {}
        self._bg_watch_state: dict[str, dict[str, Any]] = {}
        cfg = getattr(self.session, "config", None)
        timeout_raw = cfg.get("agent.background_watch_timeout_s", 7200) if cfg else 7200
        try:
            timeout_s = int(timeout_raw)
        except (TypeError, ValueError):
            timeout_s = 7200
        # Guardrails: minimum 1 minute, maximum 24 hours.
        self._bg_watch_timeout_s = max(60, min(timeout_s, 24 * 60 * 60))
        interrupt_timeout_raw = cfg.get("agent.interrupt_drain_timeout_s", 10) if cfg else 10
        try:
            interrupt_timeout_s = int(interrupt_timeout_raw)
        except (TypeError, ValueError):
            interrupt_timeout_s = 10
        # Guardrails: minimum 1 second, maximum 2 minutes.
        self._interrupt_drain_timeout_s = max(1, min(interrupt_timeout_s, 120))
        self._active_spinner = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        query: str,
        context: dict | None = None,
        progress_callback=None,
    ) -> ExecutionResult:
        """Execute a query synchronously (blocking wrapper around async)."""
        from agent.mcp_server.tool_handler import tool_session_var

        token = tool_session_var.set(self.session)
        try:
            return self._run_coro_sync(
                self._run_async(query, context, progress_callback)
            )
        finally:
            tool_session_var.reset(token)
