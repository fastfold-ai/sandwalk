"""Mixin: _copy_last_response, _truncate_for_export, _format_tool_args_for_export, _load_trace_blocks, _render_trace_timeline_markdown."""

from __future__ import annotations

import subprocess
from pathlib import Path


class _ExportHelpersMixin:
    def _copy_last_response(self):
        """Copy the last synthesis response to the system clipboard."""
        if not self._last_response:
            self.console.print("  [dim]No response to copy yet.[/dim]")
            return

        try:
            proc = subprocess.run(
                ["pbcopy"], input=self._last_response.encode(),
                capture_output=True, timeout=5,
            )
            if proc.returncode == 0:
                preview = self._last_response[:80].replace("\n", " ")
                self.console.print(f"  [green]Copied to clipboard.[/green] [dim]{preview}...[/dim]")
            else:
                # Fallback for non-macOS
                self.console.print("  [yellow]Clipboard not available. Use /export instead.[/yellow]")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            self.console.print("  [yellow]Clipboard not available. Use /export instead.[/yellow]")

    def _truncate_for_export(self, text: str, max_chars: int = 800) -> str:
        """Trim long text fields for readable markdown export."""
        if not text:
            return ""
        value = text.strip()
        if len(value) <= max_chars:
            return value
        return value[:max_chars] + f"... [{len(value)} chars total]"

    def _format_tool_args_for_export(self, args: dict | None) -> str:
        """Compactly render tool args in export timeline."""
        if not isinstance(args, dict) or not args:
            return ""
        parts = []
        for key, value in args.items():
            if str(key).startswith("_"):
                continue
            raw = str(value).replace("\n", " ")
            if len(raw) > 120:
                raw = raw[:120] + "..."
            parts.append(f"{key}={raw}")
        return ", ".join(parts)

    def _load_trace_blocks(self) -> list[dict]:
        """Load and group trace events into query blocks."""
        if not hasattr(self, "agent") or not hasattr(self.agent, "trace_store"):
            return []
        trace_path = getattr(self.agent.trace_store, "path", None)
        if trace_path is None or not Path(trace_path).exists():
            return []

        try:
            from agent.trace_store import TraceStore
            events = TraceStore.load(trace_path)
        except Exception:
            return []

        blocks: list[dict] = []
        current: dict | None = None
        for event in events:
            etype = event.get("type")
            if etype == "query_start":
                if current is not None:
                    blocks.append(current)
                current = {"start": event, "events": [], "end": None}
                continue
            if etype == "query_end":
                if current is None:
                    current = {"start": None, "events": [], "end": event}
                else:
                    current["end"] = event
                blocks.append(current)
                current = None
                continue

            if current is None:
                current = {"start": None, "events": [], "end": None}
            current["events"].append(event)

        if current is not None:
            blocks.append(current)

        return blocks

    def _render_trace_timeline_markdown(self, block: dict) -> list[str]:
        """Render detailed chronological timeline for one query block."""
        events = block.get("events", [])
        if not isinstance(events, list) or not events:
            return ["### Timeline", "", "_No detailed trace events captured for this query._", ""]

        lines: list[str] = ["### Timeline", ""]
        attempts_by_tool: dict[str, int] = {}
        attempts_by_tool_use_id: dict[str, int] = {}

        for event in events:
            etype = str(event.get("type") or "")

            if etype == "text":
                snippet = self._truncate_for_export(str(event.get("content") or ""), max_chars=260)
                if snippet:
                    lines.append(f"- assistant: {snippet}")
                continue

            if etype == "tool_start":
                tool = str(event.get("tool") or "unknown_tool")
                tool_use_id = str(event.get("tool_use_id") or "")
                attempts_by_tool[tool] = attempts_by_tool.get(tool, 0) + 1
                attempt = attempts_by_tool[tool]
                if tool_use_id:
                    attempts_by_tool_use_id[tool_use_id] = attempt
                arg_text = self._format_tool_args_for_export(event.get("input"))
                if arg_text:
                    lines.append(
                        f"- tool start: `{tool}` (attempt {attempt})"
                        f" — args: `{arg_text}`"
                    )
                else:
                    lines.append(f"- tool start: `{tool}` (attempt {attempt})")
                continue

            if etype == "tool_result":
                tool = str(event.get("tool") or "unknown_tool")
                tool_use_id = str(event.get("tool_use_id") or "")
                attempt = attempts_by_tool_use_id.get(tool_use_id, attempts_by_tool.get(tool, 1))
                status = "error" if bool(event.get("is_error")) else "ok"
                duration = event.get("duration_s")
                duration_text = ""
                if isinstance(duration, (int, float)):
                    duration_text = f", duration={duration:.2f}s"
                lines.append(
                    f"- tool result: `{tool}` (attempt {attempt})"
                    f" — status={status}{duration_text}"
                )
                output = self._truncate_for_export(str(event.get("result_text") or ""), max_chars=400)
                if output:
                    lines.append(f"  - output: `{output}`")
                continue

            # Keep unknown event types visible for debugging.
            lines.append(f"- event: `{etype or 'unknown'}`")

        lines.append("")
        return lines
