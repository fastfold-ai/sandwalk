"""Mixin: _bottom_toolbar."""

from __future__ import annotations

import random
import re
import time
from pathlib import Path
from shutil import get_terminal_size

from prompt_toolkit.formatted_text import HTML


def _html_plain_len(fragment: str) -> int:
    return len(re.sub(r"<[^>]+>", "", fragment))


def _short_cwd_label() -> str:
    cwd = Path.cwd().resolve()
    home = Path.home().resolve()
    try:
        return f"~/{cwd.relative_to(home).as_posix()}"
    except ValueError:
        return cwd.as_posix()


def _format_context_tokens(n: int) -> str:
    if n >= 1_000_000:
        millions = n / 1_000_000
        if millions >= 10 or float(millions).is_integer():
            return f"{int(round(millions))}M"
        return f"{millions:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k".replace(".0k", "k")
    return str(n)


class _BottomToolbarMixin:
    def _toolbar_context_used_tokens(self) -> int:
        """Best-effort current context size (last turn input, else session input).

        Must not call ``_has_active_query()`` while holding ``_run_lock`` —
        that helper also takes the lock and would deadlock (non-reentrant).
        """
        with self._run_lock:
            active = bool(getattr(self, "_active_query", None))
            active_in = int(getattr(self, "_active_input_tokens", 0) or 0)
            rows = list(getattr(self, "_session_sdk_turn_rows", []) or [])
            session_in = int(getattr(self, "_session_sdk_input_tokens", 0) or 0)
        if active and active_in > 0:
            return active_in
        for row in reversed(rows):
            if not isinstance(row, dict):
                continue
            try:
                value = int(row.get("input_tokens") or 0)
            except (TypeError, ValueError):
                continue
            if value > 0:
                return value
        return max(0, session_in)

    def _toolbar_context_window(self) -> int | None:
        model_id = str(getattr(self.session, "current_model", "") or "").strip()
        if not model_id:
            return None
        try:
            from agent.model_catalog import context_window_for_model

            window = context_window_for_model(model_id)
        except Exception:  # noqa: BLE001
            return None
        if isinstance(window, int) and window > 0:
            return window
        return None

    def _toolbar_context_label(self) -> str | None:
        try:
            window = self._toolbar_context_window()
            if window is None:
                return None
            used = self._toolbar_context_used_tokens()
            pct = min(100, int(round(100 * used / window))) if window else 0
            return (
                f"context: {pct}% "
                f"({_format_context_tokens(used)}/{_format_context_tokens(window)})"
            )
        except Exception:  # noqa: BLE001 — never break the prompt toolbar
            return None

    def _toolbar_effort_label(self) -> str | None:
        """Current Effort/Fast for the active model, if the model supports it."""
        try:
            from agent.model_catalog import config_selected_effort_label

            cfg = getattr(self.session, "config", None)
            if cfg is None:
                return None
            provider = str(
                getattr(self.session, "current_provider", None)
                or cfg.get("llm.provider")
                or "openai"
            ).strip().lower()
            model_id = str(
                getattr(self.session, "current_model", None) or cfg.get("llm.model") or ""
            ).strip()
            return config_selected_effort_label(
                cfg, provider=provider, model_id=model_id
            )
        except Exception:  # noqa: BLE001 — never break the prompt toolbar
            return None

    def _bottom_toolbar(self):
        try:
            return self._render_bottom_toolbar()
        except Exception:  # noqa: BLE001
            return HTML(
                '<style fg="#555555" bg="default">sandwalk</style>'
            )

    def _render_bottom_toolbar(self):
        if self._show_exit_hint:
            return HTML('<style fg="#888888" bg="default">Press Ctrl+C again to exit</style>')
        if self._show_interrupt_hint:
            return HTML('<style fg="#ffb86c" bg="default">Interrupt requested · press Ctrl+C again to force stop</style>')
        # Show tab bar when @ mention completions are active
        if self._mention_completing():
            mc = self._merged_completer.mention_completer
            tabs = []
            for i, label in enumerate(mc.TABS):
                if i == mc._active_tab:
                    tabs.append(f'<style fg="#50fa7b" bg="default"><b>[{label}]</b></style>')
                else:
                    tabs.append(f'<style fg="#555555" bg="default"> {label} </style>')
            tab_bar = "  ".join(tabs)
            return HTML(f'{tab_bar}  <style fg="#555555" bg="default">·  ←/→ switch tab</style>')

        model = self._model_display_name()
        effort_label = self._toolbar_effort_label()
        if effort_label:
            model = f"{model} · {effort_label}"
        compat_backend = self._current_compatible_backend_label()
        if compat_backend:
            model = f"{model} · {compat_backend}"
        # Prefer turn-busy (clears as soon as the agent returns) over worker
        # thread liveness, which stays true during post-run bookkeeping.
        toolbar_busy = (
            self._toolbar_is_busy()
            if hasattr(self, "_toolbar_is_busy")
            else self._has_active_query()
        )
        if toolbar_busy:
            with self._run_lock:
                queued = len(self._queued_queries)
            spinner = self._toolbar_spinner_markup()
            queued_label = (
                f'<style fg="#555555" bg="default"> · queued {queued}</style>'
                if queued
                else ""
            )
            return HTML(
                f"{spinner}"
                f"{queued_label}"
                '<style fg="#555555" bg="default">  ctrl+c interrupt</style>'
            )
        # Mustard — matches local-web Plan mode composer accent (#9a7429).
        plan = (
            ' <style fg="#555555" bg="default">·</style> '
            '<style fg="#9a7429" bg="default">plan mode</style>'
            if self.session.config.get("agent.plan_preview", False)
            else ""
        )
        specialist = ""
        label = getattr(self, "_cli_specialist_label", None)
        if label:
            from html import escape as _html_escape

            specialist = (
                f' <style fg="#555555" bg="default">·</style> '
                f'<style fg="#bd93f9" bg="default">{_html_escape(label)}</style>'
            )
        from html import escape as _html_escape

        sandbox_label = getattr(self, "_cli_sandbox_label", None) or "Local Sandbox"
        is_modal = "modal" in sandbox_label.lower()
        # Modal brand lime (#7fee64); Local Sandbox stays muted gray.
        sandbox_fg = "#7fee64" if is_modal else "#8a8f98"
        sandbox = (
            f' <style fg="#555555" bg="default">·</style> '
            f'<style fg="{sandbox_fg}" bg="default">{_html_escape(sandbox_label)}</style>'
        )
        folder = (
            f' <style fg="#555555" bg="default">·</style> '
            f'<style fg="#555555" bg="default">{_html_escape(_short_cwd_label())}</style>'
        )
        left = (
            f'<style fg="#8be9fd" bg="default">{model}</style>'
            f"{specialist}{sandbox}{folder}{plan}"
        )
        context = self._toolbar_context_label()
        if not context:
            return HTML(left)
        right = f'<style fg="#7f8790" bg="default">{_html_escape(context)}</style>'
        cols = max(40, int(get_terminal_size().columns or 80))
        pad = max(1, cols - _html_plain_len(left) - _html_plain_len(right))
        return HTML(f"{left}{' ' * pad}{right}")

    def _init_toolbar_animation_profile(self) -> None:
        """Load spinner/word profile for prompt-owned live animation."""
        try:
            from ui.status import SPINNERS, THINKING_WORDS
            style = str(self.session.config.get("ui.spinner", "benzene_breathing"))
            spinner_conf = SPINNERS.get(style, SPINNERS["benzene_breathing"])
            frames = [str(f) for f in spinner_conf.get("frames", []) if str(f)]
            if frames:
                self._toolbar_frames = frames
            interval_ms = int(spinner_conf.get("interval_ms", 125))
            self._toolbar_frame_interval_s = max(0.12, min(interval_ms / 1000.0, 0.6))
            words = list(THINKING_WORDS.get("planning", []))
            random.shuffle(words)
            if words:
                self._toolbar_words = words
        except Exception:
            pass
