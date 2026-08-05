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

    def _picker_modal_open(self) -> bool:
        """True while an in-app /themes or /models overlay is open."""
        for attr in ("_themes_modal_host", "_models_modal_host"):
            host = getattr(self, attr, None)
            if host is not None and getattr(getattr(host, "state", None), "open", False):
                return True
        return False

    def _dim_hex_if_modal(self, color: str, *, alpha: float = 0.55) -> str:
        """Match backdrop wash for HTML toolbar colors while a picker is open."""
        raw = str(color or "").strip()
        if not self._picker_modal_open():
            return raw
        if not (raw.startswith("#") and len(raw) == 7):
            return raw
        from ui.terminal.themes_modal import _overlay_black

        return _overlay_black(raw, alpha)

    def _compose_palette(self) -> dict[str, str]:
        from ui.terminal.theme import panel_palette, resolve_ui_theme

        cfg = getattr(getattr(self, "session", None), "config", None)
        palette = panel_palette(resolve_ui_theme(cfg), config=cfg)
        if not self._picker_modal_open():
            return palette
        # Compose/status toolbars paint HTML with absolute hex; dim them so
        # they sit under the same veil as the style-dict transcript chrome.
        return {
            key: self._dim_hex_if_modal(val) if isinstance(val, str) else val
            for key, val in palette.items()
        }

    @property
    def _COMPOSE_BG(self) -> str:
        return self._compose_palette()["panel_bg"]

    @property
    def _COMPOSE_ACCENT(self) -> str:
        return self._compose_palette()["accent"]

    def _bottom_toolbar(self):
        try:
            return self._render_bottom_toolbar()
        except Exception:  # noqa: BLE001
            return HTML(
                '<style fg="#555555" bg="default">sandwalk</style>'
            )

    def _toolbar_html(self, fragment: str) -> HTML:
        return HTML(fragment)

    def _with_bg(self, fragment: str, bg: str) -> str:
        return fragment.replace('bg="default"', f'bg="{bg}"')

    def _toolbar_is_turn_busy(self) -> bool:
        if hasattr(self, "_toolbar_is_busy"):
            return bool(self._toolbar_is_busy())
        return bool(self._has_active_query())

    def _toolbar_special_markup(
        self, *, bg: str = "default", include_busy: bool = True
    ) -> str | None:
        """Exit / interrupt / mention / busy lines shared by both toolbars."""
        if self._show_exit_hint:
            return self._with_bg(
                '<style fg="#888888" bg="default">Press Ctrl+C again to exit</style>',
                bg,
            )
        if self._show_interrupt_hint:
            return self._with_bg(
                '<style fg="#ffb86c" bg="default">'
                "Interrupt requested · press Ctrl+C again to force stop"
                "</style>",
                bg,
            )
        if self._mention_completing():
            mc = self._merged_completer.mention_completer
            tabs = []
            for i, label in enumerate(mc.TABS):
                if i == mc._active_tab:
                    tabs.append(
                        f'<style fg="#50fa7b" bg="default"><b>[{label}]</b></style>'
                    )
                else:
                    tabs.append(
                        f'<style fg="#555555" bg="default"> {label} </style>'
                    )
            tab_bar = "  ".join(tabs)
            return self._with_bg(
                f'{tab_bar}  <style fg="#555555" bg="default">'
                "·  ←/→ switch tab"
                "</style>",
                bg,
            )
        if include_busy and self._toolbar_is_turn_busy():
            with self._run_lock:
                queued = len(self._queued_queries)
            spinner = self._toolbar_spinner_markup()
            queued_label = (
                f'<style fg="#555555" bg="default"> · queued {queued}</style>'
                if queued
                else ""
            )
            return self._with_bg(
                f"{spinner}{queued_label}"
                '<style fg="#555555" bg="default">  ctrl+c interrupt</style>',
                bg,
            )
        return None

    def _toolbar_model_label(self) -> str:
        model = self._model_display_name()
        effort_label = self._toolbar_effort_label()
        if effort_label:
            model = f"{model} · {effort_label}"
        compat_backend = self._current_compatible_backend_label()
        if compat_backend:
            model = f"{model} · {compat_backend}"
        return model

    def _compose_lead_label(self) -> str:
        label = getattr(self, "_cli_specialist_label", None)
        if label:
            return str(label)
        if self.session.config.get("agent.plan_preview", False):
            return "Plan"
        return "Agent"

    def _compose_provider_label(self) -> str | None:
        """Short provider label shown muted after the model name."""
        try:
            compat = self._current_compatible_backend_label()
            if compat:
                return str(compat)
            _pid, label, _endpoint = self._current_provider_status()
            text = str(label or "").strip()
            if not text:
                return None
            # Keep the compose line short for verbose compat profiles.
            if text.startswith("OpenAI-compatible"):
                return "Compatible"
            return text
        except Exception:  # noqa: BLE001
            return None

    def _compose_meta_toolbar(self):
        """Model / sandbox (idle) or gold scanner + interrupt (busy) inside panel."""
        try:
            palette = self._compose_palette()
            bg = palette["panel_bg"]
            accent = palette["accent"]
            muted = palette["muted_fg"]
            sep = palette["sep_fg"]
            model_fg = palette["model_fg"]
            # Exit / interrupt / mention still replace the in-panel line.
            special = self._toolbar_special_markup(bg=bg, include_busy=False)
            if special is not None:
                return self._toolbar_html(special)

            from html import escape as _html_escape

            # Busy: scanner + interrupt stay inside the soft panel.
            if self._toolbar_is_turn_busy():
                with self._run_lock:
                    queued = len(self._queued_queries)
                spinner = self._toolbar_spinner_markup(palette="gold")
                # Force compose bg on scanner cells so they don't punch holes.
                spinner = self._with_bg(spinner, bg)
                queued_label = (
                    f'<style fg="{muted}" bg="{bg}"> · queued {queued}</style>'
                    if queued
                    else ""
                )
                return self._toolbar_html(
                    f"{spinner}{queued_label}"
                    f'<style fg="{muted}" bg="{bg}">  ctrl+c interrupt</style>'
                )

            # Idle: lead · model provider · sandbox
            # Provider sits muted right after the model (no middle-dot).
            lead = self._compose_lead_label()
            model = _html_escape(self._model_display_name())
            effort = self._toolbar_effort_label()
            if effort:
                model = f"{model} · {_html_escape(effort)}"
            provider = self._compose_provider_label()
            provider_frag = (
                f'<style fg="{muted}" bg="{bg}"> {_html_escape(provider)}</style>'
                if provider
                else ""
            )
            sandbox_label = getattr(self, "_cli_sandbox_label", None) or "Local Sandbox"
            is_modal = "modal" in sandbox_label.lower()
            sandbox_fg = self._dim_hex_if_modal("#5a9e4a") if is_modal else muted
            plan_fg = self._dim_hex_if_modal("#9a7429")
            frag = (
                f'<style fg="{accent}" bg="{bg}">{_html_escape(lead)}</style>'
                f'<style fg="{sep}" bg="{bg}"> · </style>'
                f'<style fg="{model_fg}" bg="{bg}">{model}</style>'
                f"{provider_frag}"
                f'<style fg="{sep}" bg="{bg}"> · </style>'
                f'<style fg="{sandbox_fg}" bg="{bg}">'
                f"{_html_escape(sandbox_label)}</style>"
            )
            if self.session.config.get("agent.plan_preview", False) and lead != "Plan":
                frag += (
                    f'<style fg="{sep}" bg="{bg}"> · </style>'
                    f'<style fg="{plan_fg}" bg="{bg}">plan</style>'
                )
            return self._toolbar_html(frag)
        except Exception:  # noqa: BLE001
            return HTML(
                f'<style fg="#555555" bg="{self._COMPOSE_BG}">sandwalk</style>'
            )

    def _compose_status_toolbar(self):
        """Path + context under the soft compose panel."""
        try:
            from html import escape as _html_escape

            palette = self._compose_palette()
            canvas = palette["canvas_bg"]
            muted = palette["muted_fg"]

            # Exit/interrupt hints live only on the compose meta line so they
            # are not duplicated under the path/context row.

            left = (
                f'<style fg="{muted}" bg="{canvas}">'
                f"{_html_escape(_short_cwd_label())}</style>"
            )
            context = self._toolbar_context_label()
            if not context:
                return self._toolbar_html(left)
            right = (
                f'<style fg="{muted}" bg="{canvas}">'
                f"{_html_escape(context)}</style>"
            )
            # Outer margin (2+2) + gold bar (2) + inner pads for the transcript layout.
            cols = max(40, int(get_terminal_size().columns or 80) - 11)
            pad = max(1, cols - _html_plain_len(left) - _html_plain_len(right))
            return self._toolbar_html(f"{left}{' ' * pad}{right}")
        except Exception:  # noqa: BLE001
            return HTML('<style fg="#555555" bg="default">sandwalk</style>')

    def _render_bottom_toolbar(self):
        special = self._toolbar_special_markup(bg="default")
        if special is not None:
            return self._toolbar_html(special)

        from html import escape as _html_escape

        model = _html_escape(self._toolbar_model_label())
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
            specialist = (
                f' <style fg="#555555" bg="default">·</style> '
                f'<style fg="#bd93f9" bg="default">{_html_escape(label)}</style>'
            )
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
            return self._toolbar_html(left)
        right = f'<style fg="#7f8790" bg="default">{_html_escape(context)}</style>'
        cols = max(40, int(get_terminal_size().columns or 80))
        pad = max(1, cols - _html_plain_len(left) - _html_plain_len(right))
        return self._toolbar_html(f"{left}{' ' * pad}{right}")

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
