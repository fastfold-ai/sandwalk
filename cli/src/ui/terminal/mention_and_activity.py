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
        include_files: bool = True,
        max_file_candidates: int = 500,
    ) -> list[tuple[str, str, str, str]]:
        """Build the candidate list for @ mention completion.

        Returns (name, category, description, kind) tuples.
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
        # Add file candidates from configured data directory
        if include_files:
            try:
                data_base = self.session.config.get("data.base", "")
                if data_base:
                    data_path = Path(data_base)
                    if data_path.is_dir():
                        file_count = 0
                        for f in data_path.rglob("*"):
                            if not f.is_file() or f.name.startswith("."):
                                continue
                            candidates.append(
                                (f.name, "file", str(f.relative_to(data_path)), "file")
                            )
                            file_count += 1
                            if file_count >= max(0, int(max_file_candidates)):
                                break
            except Exception:
                pass  # Best-effort file scanning
        return candidates

    def _has_active_query(self) -> bool:
        with self._run_lock:
            worker = self._worker_thread
            return bool(worker and worker.is_alive())

    def _queued_query_count(self) -> int:
        with self._run_lock:
            return len(self._queued_queries)

    def _request_interrupt(self, force: bool = False) -> bool:
        runner = getattr(getattr(self, "agent", None), "_runner", None)
        if runner is None or not hasattr(runner, "request_interrupt"):
            self.console.print("  [dim]No active runner to interrupt.[/dim]")
            return False
        ok = bool(runner.request_interrupt(force=force))
        if ok:
            if force:
                self.console.print("  [yellow]Force stop requested.[/yellow]")
            else:
                self.console.print("  [dim]Interrupt requested…[/dim]")
        else:
            self.console.print("  [dim]No active generation to interrupt.[/dim]")
        return ok

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
        while True:
            try:
                if self._has_active_query():
                    app = self._prompt_session.app
                    if app and app.is_running:
                        app.invalidate()
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
