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
        # Add file candidates from session uploads/ + workspace, then data.base
        if include_files:
            file_count = 0
            limit = max(0, int(max_file_candidates))
            seen: set[str] = set()

            def _add_file(name: str, description: str) -> bool:
                nonlocal file_count
                if name in seen:
                    return file_count >= limit
                seen.add(name)
                candidates.append((name, "file", description, "file"))
                file_count += 1
                return file_count >= limit

            try:
                from ui.terminal.attachments import session_workspace_path

                workspace = session_workspace_path(self)
                if workspace and workspace.is_dir():
                    uploads = workspace / "uploads"
                    if uploads.is_dir():
                        for f in sorted(uploads.iterdir(), key=lambda p: p.name, reverse=True):
                            if not f.is_file() or f.name.startswith("."):
                                continue
                            rel = f"uploads/{f.name}"
                            if _add_file(rel, rel):
                                break
                    if file_count < limit:
                        for f in workspace.rglob("*"):
                            if not f.is_file() or f.name.startswith("."):
                                continue
                            try:
                                rel = f.relative_to(workspace).as_posix()
                            except ValueError:
                                continue
                            if rel.startswith("uploads/"):
                                continue
                            if _add_file(rel, rel):
                                break
            except Exception:
                pass  # Best-effort workspace scan

            try:
                data_base = self.session.config.get("data.base", "")
                if data_base and file_count < limit:
                    data_path = Path(data_base)
                    if data_path.is_dir():
                        for f in data_path.rglob("*"):
                            if not f.is_file() or f.name.startswith("."):
                                continue
                            if _add_file(f.name, str(f.relative_to(data_path))):
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
        """Animate the busy toolbar without fighting Rich stdout writes.

        prompt_toolkit's ``patch_stdout`` erases/redraws the prompt around each
        print. Concurrent ``invalidate()`` calls cause the post-generation
        flicker; suspend while ``console.print`` runs and only redraw when the
        scanner frame actually changes.
        """
        last_frame = -1
        was_active = False
        while True:
            try:
                active = self._has_active_query()
                if active:
                    was_active = True
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
                        app = self._prompt_session.app
                        if app and app.is_running:
                            app.invalidate()
                    time.sleep(0.03)
                    continue

                # Busy → idle: let the final print settle, then one clean redraw.
                if was_active:
                    was_active = False
                    last_frame = -1
                    time.sleep(0.06)
                    if int(getattr(self, "_toolbar_refresh_suspend", 0) or 0) == 0:
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
