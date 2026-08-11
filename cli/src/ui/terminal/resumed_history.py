"""Mixin: _render_resumed_history, _configure_openai_compatible_model."""

from __future__ import annotations

from rich.markdown import Markdown as RichMarkdown
from ui.markdown import print_markdown_with_mermaid


class _ResumedHistoryMixin:
    def _append_resumed_user(self, query: str) -> None:
        """User turns use the compose-style soft box (same as live input)."""
        transcript = getattr(self, "transcript", None)
        if transcript is not None:
            transcript.append_text(query, kind="user")
            return
        # Legacy / non-TUI fallback — never prefix with ❯.
        self.console.print(query, markup=False)

    def _append_resumed_assistant(self, answer: str) -> None:
        """Assistant body — markdown in the transcript when available."""
        transcript = getattr(self, "transcript", None)
        if transcript is not None:
            transcript.append_text(answer, kind="assistant")
            return
        print_markdown_with_mermaid(
            self.console,
            answer,
            config=getattr(self.session, "config", None),
            markdown_factory=RichMarkdown,
        )

    def _render_resumed_history(self, term_width: int, turns: list) -> None:
        """Render saved turns so resumed sessions reopen with full context."""
        if not turns:
            return

        trace_blocks = self._load_trace_blocks()
        self.console.print()
        self.console.print("  [cyan]Session History[/cyan]")
        self.console.print()  # breath below the heading before the first turn
        for idx, turn in enumerate(turns):
            query = str(getattr(turn, "query", "") or "").strip()
            answer = str(getattr(turn, "answer", "") or "").strip()
            if query:
                self._append_resumed_user(query)
            rendered_from_trace = False
            duration_s = None
            input_tokens = None
            output_tokens = None
            if idx < len(trace_blocks):
                end = trace_blocks[idx].get("end", {})
                if isinstance(end, dict):
                    raw_duration = end.get("duration_s")
                    if isinstance(raw_duration, (int, float)):
                        duration_s = float(raw_duration)
                events = trace_blocks[idx].get("events", [])
                if isinstance(events, list) and events:
                    rendered_from_trace = self._replay_trace_events(events)
            rows_snapshot = list(getattr(self, "_session_sdk_turn_rows", []))
            run_lock = getattr(self, "_run_lock", None)
            if run_lock is not None and hasattr(run_lock, "__enter__"):
                with run_lock:
                    rows_snapshot = list(getattr(self, "_session_sdk_turn_rows", []))
            if idx < len(rows_snapshot):
                row = rows_snapshot[idx]
                if isinstance(row, dict):
                    # Show fresh (non-cached) input only, matching the live footer.
                    input_tokens = max(
                        0,
                        self._coerce_int(row.get("input_tokens"))
                        - self._coerce_int(row.get("cache_read_tokens")),
                    )
                    output_tokens = self._coerce_int(row.get("output_tokens"))
            if answer and not rendered_from_trace:
                self._append_resumed_assistant(answer)
            if duration_s is not None or input_tokens is not None or output_tokens is not None:
                self._render_turn_usage_footer(
                    term_width=term_width,
                    duration_s=duration_s,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    verb="Generated",
                )

    def _configure_openai_compatible_model(self) -> None:
        """Manage compatible profiles and switch model using selected profile."""
        from agent.config import Config

        if not isinstance(self.session.config, Config):
            self._configure_openai_compatible_model_legacy()
            return

        cfg = self.session.config
        self.console.print("\n  [cyan]OpenAI-compatible profile setup[/cyan]")
        self.console.print("  [dim]Switch, add, or edit Ollama/Unsloth/oMLX/custom profiles.[/dim]")

        profiles = cfg.openai_profiles(include_cloud=False)
        has_profiles = bool(profiles)
        default_choice = "1" if has_profiles else "2"
        self.console.print("    [1] Use existing profile")
        self.console.print("    [2] Add new profile")
        self.console.print("    [3] Edit existing profile")
        self.console.print("    [4] Cancel")
        try:
            raw_choice = self._plain_prompt_session.prompt(
                [("class:prompt", f"  Select action [{default_choice}]: ")]
            ).strip().lower()
        except (EOFError, KeyboardInterrupt):
            self.console.print("  [dim]Cancelled.[/dim]")
            return
        selected_action = raw_choice or default_choice
        if selected_action in {"4", "cancel", "c", "q"}:
            self.console.print("  [dim]Cancelled.[/dim]")
            return
        if selected_action in {"2", "new", "add", "a"}:
            profile_id = self._create_or_edit_compatible_profile()
            if not profile_id:
                self.console.print("  [dim]Cancelled.[/dim]")
                return
            self._activate_compatible_profile(profile_id)
            return
        if selected_action in {"3", "edit", "e"}:
            profile_id = self._prompt_select_compatible_profile_id(cfg=cfg, allow_create=False)
            if not profile_id:
                self.console.print("  [dim]Cancelled.[/dim]")
                return
            updated_profile_id = self._create_or_edit_compatible_profile(profile_id=profile_id)
            if not updated_profile_id:
                self.console.print("  [dim]Cancelled.[/dim]")
                return
            self._activate_compatible_profile(updated_profile_id)
            return

        profile_id = self._prompt_select_compatible_profile_id(
            cfg=cfg,
            allow_create=True,
            create_label="Add new profile",
        )
        if profile_id == "__create__":
            created_profile_id = self._create_or_edit_compatible_profile()
            if not created_profile_id:
                self.console.print("  [dim]Cancelled.[/dim]")
                return
            self._activate_compatible_profile(created_profile_id)
            return
        if not profile_id:
            self.console.print("  [dim]Cancelled.[/dim]")
            return
        self._activate_compatible_profile(profile_id)
