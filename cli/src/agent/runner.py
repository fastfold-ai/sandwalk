"""
AgentRunner: query entry point for the deepagents (LangGraph) runtime.

A single agentic loop where the model directly orchestrates all domain tools.
Anthropic and OpenAI (including OpenAI-compatible endpoints) are supported.
"""

import asyncio
from contextlib import suppress
import json
import logging
import os
import random
import re
import select
import signal
import sys
import threading
import time
import traceback
from pathlib import Path
from typing import Any

from agent.types import ExecutionResult, Plan, Step

logger = logging.getLogger("runner")


def _classify_llm_error(exc: Exception) -> tuple[str, str] | None:
    """Map a known model-provider exception to ``(title, friendly_body)``.

    Returns ``None`` for unrecognized errors so the caller can fall back to the
    generic error path (full traceback in logs). Recognized errors get a short,
    actionable message instead of a multi-frame traceback dumped to the console.
    """
    text = str(exc)
    low = text.lower()
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    exc_mod = str(getattr(exc.__class__, "__module__", "") or "").lower()

    is_auth = (
        status == 401
        or "authentication_error" in low
        or "invalid x-api-key" in low
        or "invalid api key" in low
        or "incorrect api key" in low
        or ("unauthorized" in low and "401" in low)
    )
    if is_auth:
        return (
            "Authentication failed",
            "Your model provider rejected the API key (401 — invalid or missing).\n"
            "Set a valid key, then re-run your query:\n"
            "  • fastfold config set llm.anthropic_api_key sk-ant-...\n"
            "  • or run: fastfold setup",
        )

    is_rate = (
        status == 429
        or "rate_limit" in low
        or "rate limit" in low
        or "overloaded" in low
    )
    if is_rate:
        return (
            "Rate limited",
            "The model provider is rate-limiting or overloaded (429).\n"
            "Wait a few seconds and try again.",
        )

    is_not_found = (
        status == 404
        or ("model" in low and "not found" in low)
        or "not_found_error" in low
    )
    if is_not_found:
        return (
            "Model or endpoint not found",
            "The configured provider returned 404 (model or endpoint not found).\n"
            "Verify `llm.model` and `llm.openai_base_url` for your selected profile,\n"
            "then retry (you can update via `/model` or `fastfold setup`).",
        )

    is_conn = (
        isinstance(exc, (ConnectionError, TimeoutError))
        or "connection error" in low
        or "timed out" in low
        or "timeout" in low
        or "connection refused" in low
        or "failed to establish a new connection" in low
        or "max retries exceeded" in low
        or "temporary failure in name resolution" in low
        or "name or service not known" in low
    )
    if is_conn:
        return (
            "Connection problem",
            "Could not reach the model provider.\n"
            "Check your network connection and try again.",
        )

    is_server_unavailable = status in {500, 502, 503, 504} or "service unavailable" in low
    if is_server_unavailable:
        return (
            "Provider unavailable",
            "The model provider is temporarily unavailable.\n"
            "Try again shortly, or switch models/providers with `/model`.",
        )

    # Keep OpenAI-compatible failures concise (including custom providers like
    # Ollama/LM Studio/proxy gateways) instead of printing deep tracebacks.
    if (
        exc_mod.startswith("openai")
        or exc_mod.startswith("httpx")
        or "langchain_openai" in exc_mod
    ):
        return (
            "Model provider request failed",
            "The configured OpenAI-compatible provider rejected or failed the request.\n"
            "Check provider health, `llm.model`, and `llm.openai_base_url`, then retry.",
        )

    return None


def _looks_like_unverified_execution_claim(summary: str, tool_calls: list[dict]) -> bool:
    """Detect likely fabricated execution claims when no tool was actually called."""
    if tool_calls:
        return False
    text = str(summary or "").strip().lower()
    if not text:
        return False

    # Strong signal: model invented concrete identifiers.
    if re.search(r"\b(?:fold|job|workflow|wf)_[a-z0-9]{6,}\b", text):
        return True

    has_submit_claim = any(
        phrase in text for phrase in (
            "successfully submitted",
            "i submitted",
            "i successfully submitted",
            "created the job",
            "created a job",
            "job id:",
            "workflow id:",
        )
    )
    if has_submit_claim:
        return True

    if ("is running" in text or "running with" in text) and any(
        key in text for key in ("job", "workflow", "fold")
    ):
        return True

    return False


def _extract_task_output_paths_from_text(full_text: list[str]) -> dict[str, str]:
    """Best-effort extraction of task output file paths from assistant text."""
    joined = "\n".join(full_text or [])
    pattern = re.compile(r"(?P<path>/\S*/tasks/(?P<task_id>[A-Za-z0-9_-]+)\.output)")
    mapping: dict[str, str] = {}
    for match in pattern.finditer(joined):
        path = str(match.group("path") or "").strip().rstrip(".,;)")
        task_id = str(match.group("task_id") or "").strip()
        if path and task_id:
            mapping[task_id] = path
    return mapping


def _default_local_task_output_path(task_id: str) -> str:
    """Best-guess Claude local task output path for current working dir."""
    try:
        uid = os.getuid()
    except Exception:
        uid = None
    if uid is None:
        return ""
    cwd = Path.cwd().resolve().as_posix()
    sanitized = "-" + cwd.lstrip("/").replace("/", "-")
    return f"/private/tmp/claude-{uid}/{sanitized}/tasks/{task_id}.output"


def _discover_local_task_output_file(task_id: str) -> str:
    """Try to locate a local Claude task output file by task id."""
    if not task_id:
        return ""

    direct = _default_local_task_output_path(task_id)
    if direct and Path(direct).exists():
        return direct

    try:
        uid = os.getuid()
    except Exception:
        return ""

    for root in (Path(f"/private/tmp/claude-{uid}"), Path(f"/tmp/claude-{uid}")):
        if not root.exists():
            continue
        # Common layout: /private/tmp/claude-<uid>/<sanitized-cwd>/tasks/<task_id>.output
        matches = list(root.glob(f"*/tasks/{task_id}.output"))
        if matches:
            return str(matches[0])
    return ""


def _parse_task_probe_json(raw_text: str) -> dict[str, str]:
    """Parse strict JSON map from TaskOutput probe response text."""
    text = str(raw_text or "").strip()
    if not text:
        return {}
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    # Try full text first, then first {...} object slice.
    candidates = [text]
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        candidates.append(m.group(0))

    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        out: dict[str, str] = {}
        for k, v in payload.items():
            key = str(k or "").strip()
            val = str(v or "").strip().lower()
            if not key:
                continue
            if val not in {"running", "completed", "failed", "stopped", "unknown"}:
                val = "unknown"
            out[key] = val
        if out:
            return out
    return {}


def _is_warp_terminal_env(env: dict[str, str] | None = None) -> bool:
    """Detect whether current terminal is Warp."""
    source = env if env is not None else os.environ
    term_program = str(source.get("TERM_PROGRAM") or "").lower()
    if "warp" in term_program:
        return True
    if str(source.get("WARP_IS_LOCAL_SHELL_SESSION") or "") == "1":
        return True
    if str(source.get("WARP_SESSION_ID") or "").strip():
        return True
    return False


def _sanitize_notification_text(text: str, max_len: int = 220) -> str:
    """Sanitize text for OSC notification payloads."""
    cleaned = str(text or "").replace("\r", " ").replace("\n", " ").replace(";", ",").strip()
    if len(cleaned) > max_len:
        cleaned = cleaned[: max_len - 3] + "..."
    return cleaned


class AgentRunner:
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

    def _notify_terminal_task_completion(
        self,
        task_id: str,
        status: str,
        summary: str = "",
        output_file: str = "",
    ) -> None:
        """Emit a desktop notification in Warp on task completion."""
        if self._headless:
            return
        status_norm = str(status or "").strip().lower()
        if status_norm not in {"completed", "failed", "stopped"}:
            return
        if not _is_warp_terminal_env():
            return

        title = _sanitize_notification_text(f"Fastfold task {status_norm}")
        body_parts = []
        if task_id:
            body_parts.append(task_id)
        if summary:
            body_parts.append(summary)
        if output_file:
            body_parts.append(output_file)
        body = _sanitize_notification_text(" - ".join(body_parts) if body_parts else status_norm)
        if not body:
            return

        # Warp desktop notification via OSC 777.
        sys.stdout.write(f"\033]777;notify;{title};{body}\007")
        sys.stdout.flush()

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
        return self._run_coro_sync(
            self._run_async(query, context, progress_callback)
        )

    @staticmethod
    def _extract_plan_preview_steps(proposed_plan: str, *, max_steps: int = 12) -> list[str]:
        """Extract step-like lines from freeform plan text."""
        if not proposed_plan:
            return []
        steps: list[str] = []
        in_code_block = False
        for raw_line in str(proposed_plan).splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue
            if line.startswith("#"):
                continue
            normalized = line
            # Numbered list: "1. ...", "2) ..."
            numbered = re.match(r"^\d+\s*[\.\)]\s+(.*)$", line)
            if numbered:
                normalized = numbered.group(1).strip()
            else:
                # Bulleted list: "- ...", "* ..."
                bulleted = re.match(r"^[-*]\s+(.*)$", line)
                if bulleted:
                    normalized = bulleted.group(1).strip()
                else:
                    # Prefix form: "Step 1: ..."
                    step_prefix = re.match(r"^step\s*\d+\s*[:\-]\s*(.*)$", line, flags=re.IGNORECASE)
                    if step_prefix:
                        normalized = step_prefix.group(1).strip()
            if not normalized:
                continue
            if normalized.lower() in {"proposed plan", "plan", "execution plan"}:
                continue
            steps.append(normalized)
            if len(steps) >= max_steps:
                break
        if not steps:
            compact = " ".join(str(proposed_plan or "").split())
            if compact:
                steps.append(compact[:140])
        return steps

    @staticmethod
    def _sanitize_mermaid_label(text: str, *, max_len: int = 72) -> str:
        """Escape text for Mermaid node labels."""
        label = " ".join(str(text or "").split())
        if len(label) > max_len:
            label = label[: max_len - 3] + "..."
        label = label.replace("\\", "\\\\").replace('"', '\\"')
        label = label.replace("[", "(").replace("]", ")")
        return label

    def _plan_preview_mermaid_markdown(self, proposed_plan: str) -> str:
        """Build a Mermaid flowchart markdown block for plan preview."""
        steps = self._extract_plan_preview_steps(proposed_plan)
        if not steps:
            return ""
        lines = [
            "```mermaid",
            "flowchart TD",
            '    start([User Query])',
        ]
        for idx, step in enumerate(steps, start=1):
            lines.append(f'    s{idx}["{self._sanitize_mermaid_label(step)}"]')
        lines.append("    start --> s1")
        for idx in range(2, len(steps) + 1):
            lines.append(f"    s{idx - 1} --> s{idx}")
        lines.append("    done([Execute Plan])")
        lines.append(f"    s{len(steps)} --> done")
        lines.append("```")
        return "\n".join(lines)

    def _run_coro_sync(self, coro):
        """Run async coroutine with SDK interrupt before force cancel."""
        loop = asyncio.new_event_loop()
        task = loop.create_task(coro)
        with self._active_client_lock:
            self._active_loop = loop
            self._active_task = task
        is_main_thread = threading.current_thread() is threading.main_thread()
        interrupt_deadline_at: float | None = None
        last_interrupt_at = 0.0
        sent_soft_interrupt = False
        tty_state = self._ensure_sigint_tty_mode() if is_main_thread else None
        stdin_watch_stop = threading.Event()
        stdin_watch_thread: threading.Thread | None = None
        previous_sigint_handler = None
        sigint_handler_overridden = False

        def _watch_stdin_for_ctrl_c() -> None:
            """Fallback: convert raw ^C bytes into SIGINT while query runs.

            Some terminal/input modes can deliver Ctrl+C as a byte (0x03)
            instead of raising KeyboardInterrupt. This watcher ensures we still
            trigger the normal SIGINT path in those cases.
            """
            if self._headless or os.name != "posix":
                return
            try:
                fd = sys.stdin.fileno()
            except Exception:
                return
            while not stdin_watch_stop.is_set():
                try:
                    ready, _, _ = select.select([fd], [], [], 0.15)
                except Exception:
                    return
                if fd not in ready:
                    continue
                try:
                    chunk = os.read(fd, 1)
                except Exception:
                    return
                if chunk == b"\x03":
                    with suppress(Exception):
                        os.kill(os.getpid(), signal.SIGINT)

        if not self._headless and is_main_thread:
            stdin_watch_thread = threading.Thread(
                target=_watch_stdin_for_ctrl_c,
                daemon=True,
                name="ct-stdin-ctrlc-watch",
            )
            stdin_watch_thread.start()
        try:
            if threading.current_thread() is threading.main_thread():
                with suppress(Exception):
                    previous_sigint_handler = signal.getsignal(signal.SIGINT)
                    signal.signal(signal.SIGINT, signal.default_int_handler)
                    sigint_handler_overridden = True
            asyncio.set_event_loop(loop)
            while True:
                try:
                    if interrupt_deadline_at is None:
                        return loop.run_until_complete(task)
                    remaining_s = interrupt_deadline_at - time.time()
                    if remaining_s <= 0:
                        raise asyncio.TimeoutError
                    return loop.run_until_complete(
                        asyncio.wait_for(asyncio.shield(task), timeout=remaining_s)
                    )
                except KeyboardInterrupt:
                    now = time.time()
                    second_tap = (now - last_interrupt_at) < 1.0
                    last_interrupt_at = now

                    # First Ctrl+C while a foreground SDK query is active:
                    # request graceful SDK interrupt and let the stream settle.
                    if not second_tap and not sent_soft_interrupt and not task.done():
                        interrupted = loop.run_until_complete(self._interrupt_active_query())
                        if interrupted:
                            sent_soft_interrupt = True
                            interrupt_deadline_at = now + self._interrupt_drain_timeout_s
                            if not self._headless:
                                self.session.console.print(
                                    "  [dim]Interrupt requested. Press Ctrl+C again to force stop.[/dim]"
                                )
                            continue

                    self._cancel_loop_tasks(loop)
                    raise
                except asyncio.TimeoutError:
                    # SDK interrupt was requested, but stream did not settle in time.
                    self._cancel_loop_tasks(loop)
                    raise KeyboardInterrupt
                except asyncio.CancelledError:
                    self._cancel_loop_tasks(loop)
                    raise KeyboardInterrupt
        finally:
            stdin_watch_stop.set()
            if stdin_watch_thread is not None:
                stdin_watch_thread.join(timeout=0.25)
            if sigint_handler_overridden:
                with suppress(Exception):
                    signal.signal(signal.SIGINT, previous_sigint_handler)
            with self._active_client_lock:
                if self._active_loop is loop:
                    self._active_loop = None
                if self._active_task is task:
                    self._active_task = None
            self._cancel_loop_tasks(loop)
            self._restore_tty_mode(tty_state)
            asyncio.set_event_loop(None)
            with suppress(Exception):
                loop.close()

    def request_interrupt(self, force: bool = False) -> bool:
        """Request interrupt from another thread (interactive prompt while running)."""
        with self._active_client_lock:
            loop = self._active_loop
            task = self._active_task
            client = self._active_client

        if loop is None or not loop.is_running():
            return False

        if force:
            if task is None or task.done():
                return False
            with suppress(Exception):
                loop.call_soon_threadsafe(task.cancel)
                return True
            return False

        if client is None:
            if task is not None and not task.done():
                with suppress(Exception):
                    loop.call_soon_threadsafe(task.cancel)
                    return True
            return False

        try:
            future = asyncio.run_coroutine_threadsafe(client.interrupt(), loop)
            future.result(timeout=2.0)
            return True
        except Exception:
            logger.debug("Cross-thread interrupt request failed", exc_info=True)
            if task is not None and not task.done():
                with suppress(Exception):
                    loop.call_soon_threadsafe(task.cancel)
                    return True
            return False

    def _ensure_sigint_tty_mode(self):
        """Ensure Ctrl+C emits SIGINT while foreground query is running."""
        if os.name != "posix":
            return None
        import termios

        try:
            fd = sys.stdin.fileno()
            attrs = termios.tcgetattr(fd)
        except Exception:
            return None

        new_attrs = [x[:] if isinstance(x, list) else x for x in attrs]
        changed = False

        # Local flags: ensure ISIG enabled so VINTR produces SIGINT and
        # disable canonical mode so stdin watcher can observe control bytes
        # immediately on terminals that emit literal ^C instead of SIGINT.
        lflag = int(new_attrs[3])
        if not (lflag & termios.ISIG):
            new_attrs[3] = lflag | termios.ISIG
            changed = True
            lflag = int(new_attrs[3])
        if lflag & termios.ICANON:
            new_attrs[3] = lflag & ~termios.ICANON
            changed = True

        # Control chars: ensure VINTR maps to Ctrl+C.
        cc = list(new_attrs[6])
        vintr = cc[termios.VINTR]
        if isinstance(vintr, bytes):
            desired = b"\x03"
            if vintr != desired:
                cc[termios.VINTR] = desired
                changed = True
            if termios.VMIN < len(cc) and cc[termios.VMIN] != b"\x01":
                cc[termios.VMIN] = b"\x01"
                changed = True
            if termios.VTIME < len(cc) and cc[termios.VTIME] != b"\x00":
                cc[termios.VTIME] = b"\x00"
                changed = True
        else:
            desired = 3
            if int(vintr) != desired:
                cc[termios.VINTR] = desired
                changed = True
            if termios.VMIN < len(cc) and int(cc[termios.VMIN]) != 1:
                cc[termios.VMIN] = 1
                changed = True
            if termios.VTIME < len(cc) and int(cc[termios.VTIME]) != 0:
                cc[termios.VTIME] = 0
                changed = True
        new_attrs[6] = cc

        if changed:
            with suppress(Exception):
                termios.tcsetattr(fd, termios.TCSANOW, new_attrs)
        return (fd, attrs)

    def _restore_tty_mode(self, tty_state) -> None:
        """Restore tty mode changed by _ensure_sigint_tty_mode."""
        if not tty_state:
            return
        import termios

        fd, attrs = tty_state
        with suppress(Exception):
            termios.tcsetattr(fd, termios.TCSANOW, attrs)

    def _cancel_loop_tasks(self, loop: asyncio.AbstractEventLoop) -> None:
        """Best-effort shutdown for a loop after interruption/cancellation."""
        pending = [task for task in asyncio.all_tasks(loop) if not task.done()]
        for pending_task in pending:
            pending_task.cancel()
        if pending:
            with suppress(Exception):
                loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
        with suppress(Exception):
            loop.run_until_complete(loop.shutdown_asyncgens())
        with suppress(Exception):
            loop.run_until_complete(loop.shutdown_default_executor())

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
            from deepagents.backends import FilesystemBackend
            from agent.deepagents_runtime import (
                build_chat_model,
                create_external_mcp_tools,
                create_ct_langchain_tools,
                process_events,
                skill_source_dirs,
            )
            from agent.system_prompt import build_system_prompt
            from ui.traces import TraceRenderer
            from models.llm import MODEL_PRICING
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
            # ----- Model -----
            try:
                model = build_chat_model(config)
            except ValueError as e:
                if thinking_status is not None:
                    thinking_status.stop()
                return self._make_error_result(query, str(e), time.time() - t0)

            # ----- Tools -----
            exclude_cats = set()
            if not config.get("agent.enable_experimental_tools", False):
                from tools import EXPERIMENTAL_CATEGORIES

                exclude_cats = set(EXPERIMENTAL_CATEGORIES)

            tool_mode = str(config.get("agent.tool_mode", "native") or "native").strip().lower()

            # User-disabled tools (Dashboard → Tools) are excluded from discovery.
            exclude_tool_names = set(config.hidden_tools())

            tools, sandbox, code_trace_buffer, display_name_map = create_ct_langchain_tools(
                self.session,
                exclude_categories=exclude_cats,
                exclude_tools=exclude_tool_names,
                provider=provider,
                tool_mode=tool_mode,
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

            # ----- System prompt (skills handled natively by deepagents) -----
            data_context = None
            data_dir = ctx.get("data_dir")
            if data_dir:
                data_context = f"Data directory: {data_dir}\n"
                config.set("sandbox.extra_read_dirs", str(data_dir))

            history = None
            if self.trajectory and self.trajectory.turns:
                history = self.trajectory.context_for_planner()

            tool_names = [getattr(t, "name", "") for t in tools]
            system_prompt = build_system_prompt(
                self.session,
                tool_names=tool_names,
                data_context=data_context,
                history=history,
                include_skills=False,
                runtime="deepagents",
                tool_mode=tool_mode,
                exclude_categories=exclude_cats,
                project_context=ctx.get("project_context"),
            )

            # ----- User prompt -----
            user_prompt = query
            context_parts = []
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

            # ----- Plan preview (optional) -----
            plan_preview = bool(config.get("agent.plan_preview", False))
            if plan_preview and not self._headless:
                if thinking_status is not None:
                    thinking_status.stop()
                    thinking_status = None
                    self._active_spinner = None
                approved = await self._deepagents_plan_preview(model, user_prompt)
                if not approved:
                    return self._make_error_result(
                        query, "User rejected plan preview.", time.time() - t0
                    )

            # ----- Build agent -----
            skills_sources = skill_source_dirs()
            workspace_root = str(ctx.get("workspace_path") or "/").strip() or "/"
            backend = FilesystemBackend(root_dir=workspace_root, virtual_mode=False)
            agent = create_deep_agent(
                model=model,
                tools=tools,
                system_prompt=system_prompt,
                skills=skills_sources or None,
                backend=backend,
            )

            trace_renderer = TraceRenderer(
                self.session.console,
                config=getattr(self.session, "config", None),
            )
            trace_events: list[dict] | None = [] if self.trace_store is not None else None

            max_turns = int(config.get("agent.max_sdk_turns", 30))
            recursion_limit = max(25, max_turns * 2 + 10)
            model_name = config.get("llm.model") or (
                "claude-sonnet-4-5-20250929" if provider == "anthropic" else "gpt-4o"
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
        except Exception as e:  # noqa: BLE001
            duration = time.time() - t0
            if thinking_status is not None:
                thinking_status.stop()
                thinking_status = None
            classified = _classify_llm_error(e)
            if classified is not None:
                title, body = classified
                # Expected/actionable error: keep the console clean and stash the
                # full traceback at debug level only (surfaces in verbose mode).
                logger.debug(
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

        pricing = MODEL_PRICING.get(model_name, {})
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

    async def _deepagents_plan_preview(self, model, user_prompt: str) -> bool:
        """Show a one-shot plan and ask for terminal approval (deepagents path)."""
        try:
            from langchain_core.messages import HumanMessage, SystemMessage

            response = await model.ainvoke(
                [
                    SystemMessage(content="Create a concise execution plan before running tools."),
                    HumanMessage(content=user_prompt),
                ]
            )
            from agent.deepagents_runtime import _text_from_content

            proposed_plan = _text_from_content(getattr(response, "content", "")).strip()
        except Exception:  # noqa: BLE001
            logger.debug("deepagents plan preview failed", exc_info=True)
            return True

        if proposed_plan:
            self.session.console.print("\n  [bold cyan]Proposed Plan[/bold cyan]")
            self.session.console.print(f"  {proposed_plan}\n")
            cfg = getattr(self.session, "config", None)
            mermaid_enabled = bool(cfg.get("ui.mermaid.enabled", True)) if cfg else True
            if mermaid_enabled:
                diagram_markdown = self._plan_preview_mermaid_markdown(proposed_plan)
                if diagram_markdown:
                    try:
                        from ui.markdown import print_markdown_with_mermaid

                        self.session.console.print("  [bold cyan]Plan Diagram[/bold cyan]")
                        print_markdown_with_mermaid(
                            self.session.console,
                            diagram_markdown,
                            config=cfg,
                        )
                        self.session.console.print()
                    except Exception:  # noqa: BLE001
                        logger.debug("plan-preview mermaid rendering failed", exc_info=True)
        try:
            answer = input("  Execute this plan? [Y/n] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = "n"
        return answer in {"", "y", "yes"}

    def refresh_background_watch_status(self, force: bool = False) -> None:
        """Reconcile pending tasks for the /tasks view via local output-file probe."""
        candidates: list[tuple[str, set[str]]] = []
        with self._bg_watch_lock:
            for session_id, state in self._bg_watch_state.items():
                pending = {
                    str(t).strip() for t in (state.get("pending_task_ids") or [])
                    if str(t).strip()
                }
                if not pending:
                    continue
                candidates.append((session_id, pending))

        if not candidates:
            return

        from ui.traces import TraceRenderer
        for session_id, pending in candidates:
            if not pending:
                continue
            trace_renderer = TraceRenderer(
                self.session.console,
                config=getattr(self.session, "config", None),
            )
            self._probe_local_task_outputs(session_id, pending, trace_renderer)

    def _probe_local_task_outputs(self, session_id: str, remaining: set[str], trace_renderer) -> None:
        """Fallback completion detector by reading known local task output files."""
        with self._bg_watch_lock:
            state = self._bg_watch_state.get(session_id, {})
            output_files = dict(state.get("output_files", {}))

        if not output_files:
            return

        completed_now: list[tuple[str, str, str]] = []
        for task_id in list(remaining):
            output_file = str(output_files.get(task_id) or "").strip()
            if not output_file:
                output_file = _discover_local_task_output_file(task_id)
                if output_file:
                    with self._bg_watch_lock:
                        state = self._bg_watch_state.get(session_id, {})
                        state_output_files = dict(state.get("output_files", {}))
                        state_output_files[task_id] = output_file
                        state["output_files"] = state_output_files
                        state["last_update_at"] = time.time()
                        self._bg_watch_state[session_id] = state
            if not output_file:
                continue
            path = Path(output_file)
            if not path.exists():
                discovered = _discover_local_task_output_file(task_id)
                if discovered and discovered != output_file:
                    path = Path(discovered)
                    output_file = discovered
                    with self._bg_watch_lock:
                        state = self._bg_watch_state.get(session_id, {})
                        state_output_files = dict(state.get("output_files", {}))
                        state_output_files[task_id] = output_file
                        state["output_files"] = state_output_files
                        state["last_update_at"] = time.time()
                        self._bg_watch_state[session_id] = state
            if not path.exists():
                continue
            try:
                text = path.read_text(errors="replace")
            except Exception:
                continue

            # SDK output files include terminal metadata/footer when completed.
            exit_code_match = re.search(r"exit_code:\s*(-?\d+)", text)
            if not exit_code_match:
                continue
            exit_code = exit_code_match.group(1)
            status = "completed" if exit_code == "0" else "failed"
            summary = (
                f"Detected via local output probe (exit_code={exit_code})."
            )
            completed_now.append((task_id, status, summary))

        if not completed_now:
            return

        with self._bg_watch_lock:
            state = self._bg_watch_state.get(session_id, {})
            pending = set(state.get("pending_task_ids", []))
            completed = list(state.get("completed_task_ids", []))
            for task_id, status, summary in completed_now:
                if task_id in remaining:
                    remaining.remove(task_id)
                pending.discard(task_id)
                if task_id not in completed:
                    completed.append(task_id)
                if not self._headless:
                    trace_renderer.render_task_notification(
                        task_id,
                        status,
                        summary,
                        str(output_files.get(task_id) or ""),
                    )
                self._notify_terminal_task_completion(
                    task_id,
                    status,
                    summary,
                    str(output_files.get(task_id) or ""),
                )
            state["pending_task_ids"] = sorted(pending)
            state["completed_task_ids"] = completed
            state["last_update_at"] = time.time()
            self._bg_watch_state[session_id] = state

    def get_background_watch_status(self, include_inactive: bool = True) -> list[dict]:
        """Return snapshot status for background task watchers."""
        with self._bg_watch_lock:
            rows: list[dict] = []
            for session_id, state in self._bg_watch_state.items():
                thread = self._bg_watchers.get(session_id)
                watcher_alive = bool(thread and thread.is_alive())
                if not include_inactive and not watcher_alive:
                    continue
                row = dict(state)
                row["session_id"] = session_id
                row["watcher_alive"] = watcher_alive
                rows.append(row)
        rows.sort(key=lambda r: float(r.get("last_update_at") or 0.0), reverse=True)
        return rows

    # ------------------------------------------------------------------
    # Plan mode
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Console output helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _random_usage_word() -> str:
        """Pick a past-tense footer verb from a dedicated dictionary."""
        try:
            from ui.status import FOOTER_PAST_TENSE_WORDS

            words = [
                str(word).strip()
                for bucket in FOOTER_PAST_TENSE_WORDS.values()
                for word in bucket
                if str(word).strip()
            ]
            if words:
                return random.choice(words)
        except Exception:
            pass
        return "Brewed"

    @staticmethod
    def _coerce_int(value) -> int:
        try:
            if value is None:
                return 0
            if isinstance(value, bool):
                return int(value)
            if isinstance(value, (int, float)):
                return max(0, int(value))
            return max(0, int(float(str(value).strip() or "0")))
        except Exception:
            return 0

    def _print_usage(self, result_msg, duration: float, input_tokens: int = 0,
                     output_tokens: int = 0, cache_read_tokens: int = 0):
        """Print per-turn usage summary footer.

        The ``↑`` figure shows fresh (non-cached) input only — i.e. total input
        minus prompt-cache reads — so long agentic turns that re-send a large
        cached prefix on every model call don't surface alarming totals.
        """
        verb = self._random_usage_word()
        if duration >= 60:
            mins = int(duration // 60)
            secs = int(duration % 60)
            duration_text = f"{mins}m {secs}s"
        else:
            duration_text = f"{int(max(0.0, round(duration)))}s"

        in_tokens = self._coerce_int(input_tokens)
        out_tokens = self._coerce_int(output_tokens)
        cache_read = self._coerce_int(cache_read_tokens)
        if result_msg is not None and (in_tokens <= 0 and out_tokens <= 0):
            usage = getattr(result_msg, "usage", None)
            in_tokens = self._coerce_int(getattr(usage, "input_tokens", 0))
            out_tokens = self._coerce_int(getattr(usage, "output_tokens", 0))
            if cache_read <= 0:
                cache_read = self._coerce_int(getattr(usage, "cache_read_input_tokens", 0))

        fresh_in = max(0, in_tokens - cache_read)
        left = f"✻ {verb} for {duration_text}"
        right = f"↑ {fresh_in:,} ↓ {out_tokens:,}"
        term_width = max(40, int(getattr(self.session.console, "width", 100) or 100))
        inner_width = max(10, term_width - 2)
        if len(left) + len(right) + 1 <= inner_width:
            spaces = max(1, inner_width - len(left) - len(right))
            self.session.console.print(
                f"\n  [#7f8790]{left}{' ' * spaces}[/][dim #7f8790]{right}[/]"
            )
        else:
            self.session.console.print(
                f"\n  [#7f8790]{left} · [/][dim #7f8790]{right}[/]"
            )

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    def _print_friendly_error(self, title: str, body: str) -> None:
        """Render a concise, actionable error to the console (no traceback)."""
        if getattr(self, "_headless", False):
            return
        console = getattr(getattr(self, "session", None), "console", None)
        if console is None:
            return
        try:
            from rich.panel import Panel

            console.print()
            console.print(
                Panel(
                    body,
                    title=f"[bold red]{title}[/bold red]",
                    border_style="red",
                    expand=False,
                    padding=(0, 1),
                )
            )
        except Exception:  # noqa: BLE001
            console.print(f"\n  [red]{title}:[/red] {body}")

    @staticmethod
    def _make_error_result(query: str, error: str, duration: float) -> ExecutionResult:
        """Build an ExecutionResult representing a failed query."""
        plan = Plan(query=query, steps=[])
        return ExecutionResult(
            plan=plan,
            summary=f"Agent SDK error: {error}",
            raw_results={"error": error},
            duration_s=duration,
            iterations=1,
        )
