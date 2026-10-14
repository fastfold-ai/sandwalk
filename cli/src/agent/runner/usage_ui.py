"""UsageUIMixin: per-turn usage footer, friendly error rendering, and the
shared error-``ExecutionResult`` builder for AgentRunner.

Split out of ``agent/runner.py`` (package conversion) to keep files under the
project line-count limit.
"""

from __future__ import annotations

import random

from agent.types import ExecutionResult, Plan

_FILE_ACCESS_ERROR_MARKERS = (
    "outside root directory",
    "sandbox file reads are restricted",
    "sandbox file writes are restricted",
    "file redirection is only allowed under",
    "is only allowed on paths under",
)
_FILE_ACCESS_MESSAGE = (
    "Sandwalk couldn't access that file because it is outside the folders "
    "currently allowed for this agent. "
    "[Configure agent access in Agent → Security]"
    "(/dashboard/agent/security), select **Full filesystem access**, save, "
    "and try again."
)


class UsageUIMixin:
    """Console-facing usage summary and error rendering helpers."""

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
        transcript = getattr(self.session, "transcript", None)
        if transcript is not None:
            # Owned TUI: layout against the live Window width (not console.width).
            transcript.append_text(f"{left}\t{right}", kind="usage")
            return
        term_width = max(40, int(getattr(self.session.console, "width", 100) or 100))
        # Leave a right margin — full-width pad clips trailing token digits.
        inner_width = max(10, term_width - 4)
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
        """Render a concise, actionable error (no traceback).

        Owned transcript sessions get plain padded lines — Rich ``Panel`` box
        drawing + any stray stderr dumps used to corrupt the fullscreen
        prompt_toolkit compose box. Non-transcript CLIs keep the Panel.
        """
        if getattr(self, "_headless", False):
            return
        session = getattr(self, "session", None)
        transcript = getattr(session, "transcript", None) if session is not None else None
        console = getattr(session, "console", None) if session is not None else None

        lines = [str(title or "").strip() or "Error"]
        for raw in str(body or "").splitlines():
            # LangGraph attaches these via Exception.add_note; never surface them.
            if raw.startswith("During task with name ") or raw.startswith(
                "Before task with name "
            ):
                continue
            lines.append(raw)
        plain = "\n".join(f"  {line}" if line else "" for line in lines)

        if transcript is not None:
            try:
                # Use kind=error (red) — dim system chrome made fatal failures
                # easy to miss after a long tool trace.
                transcript.append_text("", kind="error")
                transcript.append_text(plain, kind="error")
            except Exception:  # noqa: BLE001
                if console is not None:
                    console.print(f"\n[red]{plain}[/red]")
            return

        if console is None:
            return
        try:
            from rich.panel import Panel

            console.print()
            console.print(
                Panel(
                    "\n".join(lines[1:]) if len(lines) > 1 else str(body or ""),
                    title=f"[bold red]{lines[0]}[/bold red]",
                    border_style="red",
                    expand=False,
                    padding=(0, 1),
                )
            )
        except Exception:  # noqa: BLE001
            console.print(f"\n  [red]{lines[0]}:[/red] {body}")

    @staticmethod
    def _friendly_agent_error(error: str) -> str:
        """Rewrite provider jargon into actionable Sandwalk guidance."""
        text = str(error or "").strip()
        lower = text.lower()
        if (
            "reasoning is mandatory" in lower
            and "cannot be disabled" in lower
        ):
            return (
                "Reasoning is mandatory for this model — disable Fast mode "
                "(thinking must stay on)."
            )
        if "patched_format" in lower and "unexpected keyword argument" in lower:
            return (
                "No model is set up yet. Add a provider and API key in "
                "[Models](/dashboard/models)."
            )
        return text

    @staticmethod
    def _make_error_result(
        query: str, error: str, duration: float, *, prefix_sdk: bool = True
    ) -> ExecutionResult:
        """Build an ExecutionResult representing a failed query."""
        plan = Plan(query=query, steps=[])
        normalized = str(error).lower()
        friendly = UsageUIMixin._friendly_agent_error(error)
        summary = (
            _FILE_ACCESS_MESSAGE
            if any(marker in normalized for marker in _FILE_ACCESS_ERROR_MARKERS)
            else (
                f"Agent SDK error: {friendly}"
                if prefix_sdk
                else friendly
            )
        )
        return ExecutionResult(
            plan=plan,
            summary=summary,
            raw_results={"error": error},
            duration_s=duration,
            iterations=1,
        )
