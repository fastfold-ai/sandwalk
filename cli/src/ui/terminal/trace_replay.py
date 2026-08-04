"""Mixin: _replay_trace_events, _format_duration_label, _coerce_int, _render_turn_usage_footer."""

from __future__ import annotations

class _TraceReplayMixin:
    def _replay_trace_events(self, events: list[dict]) -> bool:
        """Replay persisted trace events using the same renderer as live runs.

        Returns True when at least one assistant text block was rendered.
        """
        if not events:
            return False

        from ui.traces import TraceRenderer

        transcript = getattr(self, "transcript", None) or getattr(
            self.session, "transcript", None
        )
        sink = None
        if transcript is not None:
            from ui.terminal.transcript.sink import TranscriptSink

            sink = TranscriptSink(transcript)
        trace_renderer = TraceRenderer(
            self.console,
            config=getattr(self.session, "config", None),
            expand_store=getattr(self.session, "tool_expand_store", None),
            sink=sink,
        )
        tool_inputs: dict[str, dict] = {}
        tool_names: dict[str, str] = {}
        rendered_text = False

        for event in events:
            etype = str(event.get("type") or "")
            if etype == "text":
                content = str(event.get("content") or "")
                if content.strip():
                    trace_renderer.render_reasoning(content)
                    rendered_text = True
                continue

            if etype == "tool_start":
                tool = str(event.get("tool") or "unknown_tool")
                tool_use_id = str(event.get("tool_use_id") or "")
                tool_input = event.get("input") if isinstance(event.get("input"), dict) else {}
                if tool_use_id:
                    tool_inputs[tool_use_id] = tool_input
                    tool_names[tool_use_id] = tool
                trace_renderer.render_tool_start(tool, tool_input)
                continue

            if etype == "tool_result":
                tool_use_id = str(event.get("tool_use_id") or "")
                tool = str(event.get("tool") or "")
                if not tool and tool_use_id:
                    tool = str(tool_names.get(tool_use_id) or "")
                if not tool:
                    tool = "unknown_tool"
                tool_input = tool_inputs.get(tool_use_id, {})
                result_text = str(event.get("result_text") or "")
                is_error = bool(event.get("is_error"))
                duration_s = float(event.get("duration_s") or 0.0)
                if is_error:
                    trace_renderer.render_tool_error(tool, result_text)
                else:
                    trace_renderer.render_tool_complete(tool, tool_input, result_text, duration_s)
                continue

            if etype == "task_started":
                trace_renderer.render_task_started(
                    str(event.get("task_id") or ""),
                    str(event.get("description") or ""),
                    str(event.get("task_type") or "") or None,
                )
                continue

            if etype == "task_progress":
                usage = event.get("usage") if isinstance(event.get("usage"), dict) else None
                trace_renderer.render_task_progress(
                    str(event.get("task_id") or ""),
                    str(event.get("description") or ""),
                    usage,
                    str(event.get("last_tool_name") or "") or None,
                )
                continue

            if etype == "task_notification":
                trace_renderer.render_task_notification(
                    str(event.get("task_id") or ""),
                    str(event.get("status") or ""),
                    str(event.get("summary") or ""),
                    str(event.get("output_file") or ""),
                )

        return rendered_text

    @staticmethod
    def _format_duration_label(duration_s: float) -> str:
        """Format generation duration like live footer (e.g., 24s, 1m 05s)."""
        duration = max(0.0, float(duration_s))
        if duration >= 60:
            mins = int(duration // 60)
            secs = int(duration % 60)
            return f"{mins}m {secs}s"
        return f"{int(round(duration))}s"

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

    def _render_turn_usage_footer(
        self,
        *,
        term_width: int,
        duration_s: float | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        verb: str = "Generated",
    ) -> None:
        """Render one-line turn footer with duration and per-turn token arrows."""
        left = f"✻ {verb}"
        if duration_s is not None:
            left = f"{left} for {self._format_duration_label(duration_s)}"

        in_tokens = self._coerce_int(input_tokens)
        out_tokens = self._coerce_int(output_tokens)
        right = f"↑ {in_tokens:,} ↓ {out_tokens:,}"

        width = max(40, int(term_width or self.console.width or 100))
        inner_width = max(10, width - 2)
        if len(left) + len(right) + 1 <= inner_width:
            spaces = max(1, inner_width - len(left) - len(right))
            self.console.print(
                f"  [#7f8790]{left}{' ' * spaces}[/][dim #7f8790]{right}[/]"
            )
        else:
            self.console.print(
                f"  [#7f8790]{left} · [/][dim #7f8790]{right}[/]"
            )
