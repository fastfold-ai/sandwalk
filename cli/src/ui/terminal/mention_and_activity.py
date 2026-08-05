"""Mixin: _build_mention_candidates, _has_active_query, _queued_query_count, _request_interrupt, _ensure_live_refresh_thread, _live_refresh_loop, _set_active_activity, _coerce_token_count."""

from __future__ import annotations

from pathlib import Path
import threading
import time
from ui.terminal.dataset_catalog import DATASET_CANDIDATES


class _MentionAndActivityMixin:
    def _build_mention_candidates(
        self,
        *,
        include_tools: bool = True,
        include_workflows: bool = True,
        include_files: bool = False,
        max_file_candidates: int = 500,
    ) -> list[tuple[str, str, str, str]]:
        """Build the candidate list for ``#`` tool/dataset/workflow completion.

        Returns (name, category, description, kind) tuples.
        Files are handled separately by ``_build_file_candidates`` (``@``).
        """
        candidates = []
        # Add datasets
        for name, category, description in DATASET_CANDIDATES:
            candidates.append((name, category, description, "dataset"))
        # Add tools from registry (lazy load)
        if include_tools:
            try:
                from tools import ensure_loaded, registry

                ensure_loaded()
                for tool in registry.list_tools():
                    candidates.append(
                        (tool.name, tool.category, tool.description[:80], "tool")
                    )
            except Exception:
                pass  # Registry not available — datasets still work
        # Add workflow candidates
        if include_workflows:
            try:
                from agent.workflows import WORKFLOWS

                for wf_name, wf in WORKFLOWS.items():
                    n_steps = len(wf.get("steps", []))
                    candidates.append(
                        (wf_name, "workflow", f"{wf['description']} ({n_steps} steps)", "workflow")
                    )
            except Exception:
                pass  # Workflows not available
        # Legacy: optional files on # completer (normally False).
        if include_files:
            candidates.extend(
                self._build_file_candidates(max_file_candidates=max_file_candidates)
            )
        return candidates

    def _build_file_candidates(
        self,
        *,
        max_file_candidates: int = 500,
    ) -> list[tuple[str, str, str, str]]:
        """Build ``@`` file candidates from session workspace + cwd (+ data.base).

        Each candidate name is the agent path token: ``@rel`` under the session
        workspace, otherwise an absolute filesystem path.
        """
        from ui.terminal.attachments import _SKIP_DIR_NAMES, session_workspace_path

        candidates: list[tuple[str, str, str, str]] = []
        limit = max(0, int(max_file_candidates))
        seen: set[str] = set()

        def _add(agent_path: str, description: str) -> bool:
            if agent_path in seen:
                return len(candidates) >= limit
            seen.add(agent_path)
            candidates.append((agent_path, "file", description, "file"))
            return len(candidates) >= limit

        def _scan_root(root: Path, *, label: str, as_workspace: bool) -> None:
            if not root.is_dir() or len(candidates) >= limit:
                return
            try:
                for f in root.rglob("*"):
                    if len(candidates) >= limit:
                        return
                    if not f.is_file() or f.name.startswith("."):
                        continue
                    try:
                        parts = f.relative_to(root).parts
                    except ValueError:
                        continue
                    if any(
                        part in _SKIP_DIR_NAMES or part.startswith(".")
                        for part in parts[:-1]
                    ):
                        continue
                    rel = "/".join(parts)
                    if as_workspace:
                        agent_path = f"@{rel}"
                        desc = f"workspace · {rel}"
                    else:
                        agent_path = str(f.resolve())
                        desc = f"{label} · {rel}"
                    if _add(agent_path, desc):
                        return
            except Exception:
                pass

        try:
            workspace = session_workspace_path(self)
            ws_resolved = (
                workspace.resolve() if workspace and workspace.is_dir() else None
            )
            if ws_resolved is not None:
                _scan_root(ws_resolved, label="workspace", as_workspace=True)
            cwd = Path.cwd().resolve()
            if cwd.is_dir() and cwd != ws_resolved:
                _scan_root(cwd, label="cwd", as_workspace=False)
        except Exception:
            pass

        try:
            data_base = self.session.config.get("data.base", "")
            if data_base and len(candidates) < limit:
                data_path = Path(data_base).expanduser().resolve()
                if data_path.is_dir():
                    _scan_root(data_path, label="data", as_workspace=False)
        except Exception:
            pass

        return candidates

    def _has_active_query(self) -> bool:
        """True while a worker is alive (queueing / interrupt / slash guards)."""
        with self._run_lock:
            worker = self._worker_thread
            return bool(worker and worker.is_alive())

    def _toolbar_is_busy(self) -> bool:
        """True only while a turn is in-flight (not during post-run cleanup)."""
        with self._run_lock:
            return bool(getattr(self, "_active_query", None))

    def _clear_toolbar_busy(self) -> None:
        """Mark the toolbar idle and force a redraw (call as soon as the run returns)."""
        with self._run_lock:
            self._active_query = None
            self._active_query_started_at = 0.0
            self._active_activity = ""
            self._active_activity_updated_at = 0.0
            self._active_input_tokens = 0
            self._active_output_tokens = 0
            self._active_streamed_chars = 0
        self._invalidate_prompt_toolbar(retries=8)

    def _invalidate_prompt_toolbar(self, *, retries: int = 1) -> None:
        """Invalidate the prompt UI, retrying if a console.print suspend is held."""
        for _ in range(max(1, retries)):
            if int(getattr(self, "_toolbar_refresh_suspend", 0) or 0) > 0:
                time.sleep(0.02)
                continue
            try:
                app = getattr(self, "_transcript_app", None) or self._prompt_session.app
                if app and app.is_running:
                    app.invalidate()
                    return
            except Exception:
                return
            time.sleep(0.02)

    def _queued_query_count(self) -> int:
        with self._run_lock:
            return len(self._queued_queries)

    def _request_interrupt(self, force: bool = False) -> bool:
        runner = getattr(getattr(self, "agent", None), "_runner", None)
        if runner is None or not hasattr(runner, "request_interrupt"):
            self._print_interrupt_notice("  [dim]No active runner to interrupt.[/dim]")
            return False
        ok = bool(runner.request_interrupt(force=force))
        if ok:
            if force:
                self._print_interrupt_notice("  [yellow]Force stop requested.[/yellow]")
            else:
                self._print_interrupt_notice("  [dim]Interrupt requested…[/dim]")
        else:
            self._print_interrupt_notice("  [dim]No active generation to interrupt.[/dim]")
        return ok

    def _print_interrupt_notice(self, message: str) -> None:
        """Avoid flooding the transcript when Ctrl+C is held/spammed."""
        now = time.time()
        last = float(getattr(self, "_last_interrupt_notice_at", 0.0) or 0.0)
        prev = getattr(self, "_last_interrupt_notice", None)
        if message == prev and (now - last) < 0.8:
            return
        self._last_interrupt_notice = message
        self._last_interrupt_notice_at = now
        self.console.print(message)

    def _ensure_live_refresh_thread(self) -> None:
        """Keep toolbar status live while generation runs."""
        with self._run_lock:
            t = self._live_refresh_thread
            if t and t.is_alive():
                return
            t = threading.Thread(
                target=self._live_refresh_loop,
                daemon=True,
                name="ct-live-toolbar-refresh",
            )
            self._live_refresh_thread = t
            t.start()

    def _live_refresh_loop(self) -> None:
        """Animate the busy toolbar without fighting Rich stdout writes.

        Uses ``_toolbar_is_busy`` (active turn), not worker-thread liveness, so
        the scanner clears as soon as the agent returns — even while usage
        bookkeeping still runs on the worker.
        """
        last_frame = -1
        was_busy = False
        idle_retries = 0
        while True:
            try:
                busy = self._toolbar_is_busy()
                if busy:
                    was_busy = True
                    idle_retries = 0
                    if int(getattr(self, "_toolbar_refresh_suspend", 0) or 0) > 0:
                        time.sleep(0.03)
                        continue
                    from ui.status.scanner import scanner_frame_count

                    interval = float(
                        getattr(self, "_toolbar_frame_interval_s", 0.04) or 0.04
                    )
                    width = int(getattr(self, "_toolbar_scanner_width", 10) or 10)
                    n = max(1, scanner_frame_count(width=width))
                    frame = int(time.time() / max(0.02, interval)) % n
                    if frame != last_frame:
                        last_frame = frame
                        self._invalidate_prompt_toolbar(retries=1)
                    time.sleep(0.03)
                    continue

                # Busy → idle: keep retrying until redraw lands (suspend may hold).
                if was_busy or idle_retries > 0:
                    if was_busy:
                        was_busy = False
                        last_frame = -1
                        idle_retries = 6
                    if int(getattr(self, "_toolbar_refresh_suspend", 0) or 0) == 0:
                        self._invalidate_prompt_toolbar(retries=1)
                        idle_retries = 0
                    else:
                        idle_retries = max(0, idle_retries - 1)
                        time.sleep(0.03)
                        continue
            except Exception:
                pass
            time.sleep(0.25)

    def _set_active_activity(self, text: str) -> None:
        clean = str(text or "").replace("\n", " ").strip()
        if len(clean) > 80:
            clean = clean[:77] + "..."
        with self._run_lock:
            self._active_activity = clean
            self._active_activity_updated_at = time.time()

    @staticmethod
    def _coerce_token_count(value) -> int:
        try:
            if value is None:
                return 0
            if isinstance(value, bool):
                return int(value)
            if isinstance(value, int):
                return max(0, value)
            if isinstance(value, float):
                return max(0, int(value))
            text = str(value).strip()
            if not text:
                return 0
            return max(0, int(float(text)))
        except Exception:
            return 0
