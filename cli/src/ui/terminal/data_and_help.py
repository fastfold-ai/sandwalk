"""Mixin: _handle_data_command, _show_help, _run_doctor."""

from __future__ import annotations

from prompt_toolkit.formatted_text import HTML
from rich.panel import Panel

from ui.markdown import LeftMarkdown
from ui.terminal.slash_commands import SLASH_COMMANDS


class _DataAndHelpMixin:
    def _run_doctor(self) -> None:
        """Run readiness checks without suspending the fullscreen TUI.

        Probes are network-heavy; running them on the enter handler freezes the
        app, and ``run_in_terminal`` blanks the alternate screen for the whole
        wait. Background the work and stream the table into the transcript.
        """
        import threading

        if bool(getattr(self, "_doctor_running", False)):
            self.console.print("  [dim]Doctor already running…[/dim]")
            return

        from agent.doctor import has_errors, has_warnings, run_checks, to_table
        from ui.status.spinners import SPINNERS

        self._doctor_running = True
        cfg = self.session.config
        session = self.session
        style = str(cfg.get("ui.spinner") or "benzene_breathing")
        spinner_conf = SPINNERS.get(style) or SPINNERS["benzene_breathing"]
        frames = [str(f) for f in spinner_conf.get("frames", []) if str(f)] or ["·"]
        interval_s = max(0.05, int(spinner_conf.get("interval_ms", 125)) / 1000.0)
        stop_spin = threading.Event()
        status_entry = self._doctor_status_entry(frames[0])

        def _spin() -> None:
            i = 0
            while not stop_spin.wait(interval_s):
                frame = frames[i % len(frames)]
                self._doctor_set_status(status_entry, f"  {frame} Running diagnostics…")
                i += 1

        def _worker() -> None:
            try:
                checks = run_checks(cfg, session=session)
            except Exception as exc:  # noqa: BLE001
                stop_spin.set()
                self._doctor_set_status(status_entry, f"  Doctor failed: {exc}")
                self.console.print(f"  [red]Doctor failed:[/red] {exc}")
                self._doctor_running = False
                self._invalidate_after_doctor()
                return
            try:
                stop_spin.set()
                self._doctor_set_status(status_entry, "  Diagnostics complete")
                self.console.print(to_table(checks))
                if has_errors(checks):
                    self.console.print("  [red]Blocking issues found.[/red]")
                elif has_warnings(checks):
                    self.console.print(
                        "  [yellow]No blocking errors; warnings remain.[/yellow]"
                    )
                else:
                    self.console.print("  [green]No blocking issues found.[/green]")
            finally:
                stop_spin.set()
                self._doctor_running = False
                self._invalidate_after_doctor()

        threading.Thread(target=_spin, daemon=True, name="sandwalk-doctor-spin").start()
        threading.Thread(target=_worker, daemon=True, name="sandwalk-doctor").start()

    def _doctor_status_entry(self, frame: str):
        """Seed the animated diagnostics line in the owned transcript."""
        transcript = getattr(self, "transcript", None)
        line = f"  {frame} Running diagnostics…"
        if transcript is not None:
            return transcript.append_text(line, kind="system")
        self.console.print(f"  [cyan]{frame}[/cyan] Running diagnostics…")
        return None

    def _doctor_set_status(self, entry, text: str) -> None:
        transcript = getattr(self, "transcript", None)
        if entry is not None and transcript is not None:
            transcript.update_text(entry, text)
            return
        # Fallback when no owned transcript (rare / tests).
        if entry is None:
            self.console.print(text)

    def _invalidate_after_doctor(self) -> None:
        try:
            self._invalidate_prompt_toolbar(retries=2)
        except Exception:  # noqa: BLE001
            pass
        app = getattr(self, "_transcript_app", None)
        try:
            if app is not None and getattr(app, "is_running", False):
                app.invalidate()
        except Exception:  # noqa: BLE001
            pass

    def _handle_data_command(self, query: str) -> None:
        """Interactive dataset management: /data [list | status | pull <name> | pull-all]."""
        try:
            from data.downloader import (
                DATASETS,
                dataset_catalog,
                dataset_status,
                download_all,
                download_dataset,
            )
        except Exception as e:  # noqa: BLE001
            self.console.print(f"  [red]Data module unavailable:[/red] {e}")
            return

        parts = query.strip().split()
        sub = parts[1].lower() if len(parts) > 1 else "status"
        args = parts[2:]

        if sub in ("list", "ls", "catalog"):
            self.console.print(dataset_catalog())
            return
        if sub in ("status", "st"):
            self.console.print(dataset_status())
            return
        if sub in ("pull-all", "pullall", "all"):
            auto = [n for n, ds in DATASETS.items() if ds.get("auto_download")]
            self.console.print(
                f"  [cyan]Downloading all auto-downloadable datasets:[/cyan] {', '.join(auto)}"
            )
            self.console.print("  [dim]This can be large (depmap alone is ~580MB). Ctrl+C to stop.[/dim]")
            try:
                download_all()
            except KeyboardInterrupt:
                self.console.print("\n  [yellow]Download interrupted.[/yellow]")
            return
        if sub == "pull":
            if not args:
                self.console.print("  [yellow]Usage:[/yellow] /data pull <name|all>")
                self.console.print(f"  [dim]Available:[/dim] {', '.join(DATASETS.keys())}")
                return
            name = args[0].lower()
            if name not in DATASETS and name not in ("all",):
                self.console.print(f"  [red]Unknown dataset:[/red] {name}")
                self.console.print(f"  [dim]Available:[/dim] {', '.join(DATASETS.keys())} (or 'all')")
                return
            try:
                download_dataset(name)
            except KeyboardInterrupt:
                self.console.print("\n  [yellow]Download interrupted.[/yellow]")
            return

        self.console.print(f"  [yellow]Unknown /data subcommand:[/yellow] {sub}")
        self.console.print(r"  [dim]Usage:[/dim] /data \[list | status | pull <name> | pull-all]")

    def _show_help(self):
        # Plain command names (no backticks) — Rich's default markdown.code is
        # ``bold cyan on black`` chips that look harsh in light themes.
        command_lines = ["**Slash Commands:**"]
        for command in sorted(SLASH_COMMANDS.keys()):
            command_lines.append(f"- **{command}** — {SLASH_COMMANDS[command]}")

        help_text = (
            "**Usage:**\n"
            "- Type any research question to investigate.\n"
            "- **!command** — run one shell command safely (no pipes/chaining; e.g., !ls .).\n"
            + "\n".join(command_lines)
            + "\n\n"
            "**Shortcuts:**\n"
            "- **Enter** — submit · **Ctrl+J** / **Alt+Enter** — newline\n"
            "- Click a ✓ Ran … ▸ tool line — expand/collapse details in place\n"
            "- Drag to select transcript text (copies on release; Ctrl+C / Esc)\n"
            "- Mouse wheel / PgUp PgDn — scroll the session transcript\n"
            "- **Ctrl+E** — toggle the latest tool card\n"
            "- Paste image / image path — orange [Image N] chip (uploads/)\n"
            "- **@** — search files (workspace + cwd); Enter inserts orange @[file] chip (does not send)\n"
            "- **#** — tools / datasets / workflows (←/→ tabs)\n"
            "- **Tab** — open slash / # / @ completions\n"
            "- **Ctrl+C** — interrupt active generation (double-tap forces stop)\n"
            "- **Ctrl+C** × 2 at idle prompt — exit\n"
            "\n"
            "**Tips:**\n"
            "- **/sandbox** — pick Local or Modal CPU/GPU (same presets as the Web UI); "
            "edit base image after Modal.\n"
            "- **/plan** — toggle Plan mode (CLI sessions start in Agent mode).\n"
            "- Status bar shows model · specialist · sandbox · cwd · context % when known.\n"
            "\n"
            "**Examples:**\n"
            "- find top genetically supported Parkinson targets\n"
            "- /agents 3 find repurposing hypotheses for ulcerative colitis\n"
            "- /case-study list then /case-study revlimid\n"
            "- sandwalk report publish (from shell) to convert latest markdown report to HTML."
        )
        self.console.print(Panel(
            LeftMarkdown(help_text),
            title="sandwalk Help",
            border_style="cyan",
        ))
