"""Mixin: _export_session, _send_export_to_slack."""

from __future__ import annotations

from pathlib import Path
import json
import os
import time
import urllib.error
import urllib.request


class _ExportSessionMixin:
    def _export_session(self, filename: str = None):
        """Export the session transcript to a markdown file and return the path."""
        if not hasattr(self, 'agent') or not self.agent.trajectory.turns:
            self.console.print("  [dim]No session data to export yet.[/dim]")
            return None

        output_dir = Path.cwd() / "exports"
        output_dir.mkdir(parents=True, exist_ok=True)

        if filename:
            path = output_dir / filename
        else:
            ts = time.strftime("%Y%m%d_%H%M%S")
            path = output_dir / f"session_{ts}.md"

        lines = ["# FastFold Agent CLI Session Export\n"]
        lines.append(f"*Model: {self._model_display_name()}*\n\n---\n")
        trace_blocks = self._load_trace_blocks()

        for i, turn in enumerate(self.agent.trajectory.turns, 1):
            lines.append(f"## Query {i}\n")
            lines.append(f"**Q:** {turn.query}\n")
            lines.append(f"**A:** {turn.answer}\n")
            if turn.entities:
                lines.append(f"*Entities: {', '.join(turn.entities)}*\n")
            if turn.tools_used:
                lines.append(f"*Tools: {', '.join(turn.tools_used)}*\n")
            if i <= len(trace_blocks):
                block = trace_blocks[i - 1]
                start = block.get("start") or {}
                end = block.get("end") or {}
                if start:
                    query_model = start.get("model")
                    if query_model:
                        lines.append(f"*Trace model: {query_model}*\n")
                if end:
                    duration = end.get("duration_s")
                    cost = end.get("cost_usd")
                    if isinstance(duration, (int, float)):
                        lines.append(f"*Trace duration: {duration:.2f}s*\n")
                    if isinstance(cost, (int, float)):
                        lines.append(f"*Trace cost (USD): {cost:.6f}*\n")
                lines.extend(self._render_trace_timeline_markdown(block))
            lines.append("\n---\n")

        if len(trace_blocks) > len(self.agent.trajectory.turns):
            lines.append("## Additional Trace Blocks\n")
            for j in range(len(self.agent.trajectory.turns), len(trace_blocks)):
                block_num = j + 1
                lines.append(f"### Trace Block {block_num}\n")
                start = trace_blocks[j].get("start") or {}
                if start:
                    raw_query = start.get("query")
                    if raw_query:
                        lines.append(f"**Q:** {raw_query}\n")
                lines.extend(self._render_trace_timeline_markdown(trace_blocks[j]))
                lines.append("\n---\n")

        path.write_text("\n".join(lines))
        # Bare absolute path on its own (underlined via transcript link styling);
        # prompt_toolkit strips OSC-8, so click-to-open handles open in-TUI.
        abs_path = str(path.resolve())
        self.console.print("  [green]Exported to[/green]")
        self.console.print(f"  {abs_path}")
        return path

    def _send_export_to_slack(self, markdown: str, report_name: str) -> dict:
        """Send markdown report to Fastfold Slack report endpoint."""
        from agent.config import Config

        cfg = Config.load()
        api_key = os.environ.get("FASTFOLD_API_KEY") or cfg.get("api.fastfold_cloud_key")
        if not api_key:
            return {
                "ok": False,
                "message": (
                    "Fastfold API key not configured. Run `sandwalk setup` or "
                    "`sandwalk config set api.fastfold_cloud_key <key>`."
                ),
            }

        base_url = os.environ.get("FASTFOLD_API_BASE_URL", "https://api.fastfold.ai").strip() or "https://api.fastfold.ai"
        url = f"{base_url.rstrip('/')}/v1/slack/messages/agent-cli-report"
        body = json.dumps(
            {
                "markdown": markdown,
                "report_name": report_name,
                "save_to_library": True,
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            url=url,
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with self.console.status("[green]Sending report to Slack...[/green]", spinner="dots"):
                with urllib.request.urlopen(req, timeout=30) as resp:
                    text = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            text = e.read().decode("utf-8", errors="replace")
            try:
                data = json.loads(text) if text else {}
            except Exception:
                data = {}
            return {"ok": False, "message": data.get("message") or f"API error ({e.code})"}
        except urllib.error.URLError as e:
            return {"ok": False, "message": f"Network error: {e.reason}"}

        try:
            data = json.loads(text) if text else {}
        except Exception:
            return {"ok": False, "message": "Invalid JSON response from Fastfold API."}
        if not isinstance(data, dict):
            return {"ok": False, "message": "Unexpected response from Fastfold API."}
        return data
