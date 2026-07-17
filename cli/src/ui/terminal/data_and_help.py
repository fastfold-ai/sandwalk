"""Mixin: _handle_data_command, _show_help."""

from __future__ import annotations

from prompt_toolkit.formatted_text import HTML
from rich.panel import Panel
from ui.markdown import LeftMarkdown
from ui.terminal.slash_commands import SLASH_COMMANDS


class _DataAndHelpMixin:
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
        command_lines = ["**Slash Commands:**"]
        for command in sorted(SLASH_COMMANDS.keys()):
            command_lines.append(f"- `{command}` — {SLASH_COMMANDS[command]}")

        help_text = (
            "**Usage:**\n"
            "- Type any research question to investigate.\n"
            "- `!command` — run one shell command safely (no pipes/chaining; e.g., `!ls .`).\n"
            + "\n".join(command_lines)
            + "\n\n"
            "**Shortcuts:**\n"
            "- `Ctrl+J` or `Alt+Enter` — insert newline (multi-line input)\n"
            "- `Tab` — accept ghost suggestion\n"
            "- `Ctrl+C` — interrupt active generation (double-tap forces stop)\n"
            "- `Ctrl+C` × 2 at idle prompt — exit\n"
            "\n"
            "**Tips:**\n"
            "- `/sandbox` — pick Local or Modal CPU/GPU (same presets as the Web UI); edit base image after Modal.\n"
            "- `/plan` — toggle Plan mode (CLI sessions start in Agent mode).\n"
            "- Status bar shows model · specialist · sandbox · cwd · context % when known.\n"
            "\n"
            "**Examples:**\n"
            '- `find top genetically supported Parkinson targets`\n'
            '- `/agents 3 find repurposing hypotheses for ulcerative colitis`\n'
            '- `/case-study list` then `/case-study revlimid`\n'
            '- `sandwalk report publish` (from shell) to convert latest markdown report to HTML.'
        )
        self.console.print(Panel(
            LeftMarkdown(help_text),
            title="sandwalk Help",
            border_style="cyan",
        ))
