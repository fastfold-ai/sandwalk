"""Mixin: /themes — pick Sandwalk UI palette + light/dark/auto for the transcript TUI.

Host interactive UIs (/model, /settings, …) are intentionally unthemed —
this only updates the owned fullscreen transcript canvas/compose panel.
``/theme`` is accepted as a short alias.
"""

from __future__ import annotations


class _ThemeCommandMixin:
    def _refresh_ui_theme(self) -> None:
        """Ask the fullscreen transcript app to rebuild styles (if running)."""
        refresh = getattr(self, "_ui_theme_refresh", None)
        if callable(refresh):
            try:
                refresh()
                return
            except Exception:  # noqa: BLE001
                pass
        try:
            inv = getattr(self, "_invalidate_prompt_toolbar", None)
            if callable(inv):
                inv()
        except Exception:  # noqa: BLE001
            pass

    def _apply_theme_mode(self, cfg, token: str) -> None:
        from ui.terminal.theme import resolve_ui_theme

        cfg.set("ui.theme", token)
        cfg.save()
        self.session.config = cfg
        resolved = resolve_ui_theme(cfg)
        self.console.print(
            f"  [green]Theme mode:[/green] {token} "
            f"[dim](resolved {resolved})[/dim]"
        )
        self._refresh_ui_theme()

    def _apply_theme_palette(self, cfg, chosen_id: str) -> None:
        from ui.terminal.theme import get_palette, resolve_ui_theme

        cfg.set("ui.palette", chosen_id)
        cfg.save()
        self.session.config = cfg
        meta = get_palette(chosen_id)
        mode = resolve_ui_theme(cfg)
        colors = meta[mode]
        self.console.print(
            f"  [green]Palette:[/green] {meta['name']} "
            f"[dim]({chosen_id} · {mode})[/dim]"
        )
        self.console.print(
            f"  [{colors['canvas_bg']}]██[/] canvas  "
            f"[{colors['panel_bg']}]██[/] panel  "
            f"[{colors['accent']}]██[/] accent"
        )
        self._refresh_ui_theme()

    def _prompt_theme_interactive(self, cfg) -> None:
        """In-app modal (search + live preview); numbered list fallback."""
        # Prefer in-app overlay while the transcript Application owns the TTY.
        host = getattr(self, "_themes_modal_host", None)
        app = getattr(self, "_transcript_app", None)
        if host is not None and getattr(app, "is_running", False):
            host.open()
            return
        try:
            from ui.terminal.themes_modal import run_themes_modal

            if run_themes_modal(self):
                return
        except Exception:  # noqa: BLE001
            pass

        from ui.terminal.theme import (
            list_palettes,
            resolve_ui_palette,
            resolve_ui_theme,
        )
        from ui.terminal.theme_palettes import palette_swatch_markup

        palettes = list_palettes()
        active_pal = resolve_ui_palette(cfg)
        mode = str(cfg.get("ui.theme") or "auto").strip().lower() or "auto"
        active_mode = resolve_ui_theme(cfg)

        self.console.print()
        self.console.print("  [cyan]Themes[/cyan]")
        self.console.print(
            f"  [dim]Mode:[/dim] {mode} [dim](resolved {active_mode})[/dim]"
        )
        self.console.print()
        self.console.print("  [cyan]Mode[/cyan]")
        for i, (label, value) in enumerate(
            [("light", "light"), ("dark", "dark"), ("auto", "auto")], 1
        ):
            mark = " [green]*[/green]" if mode == value else "  "
            self.console.print(f"  {mark} [m{i}] {label}")
        self.console.print()
        self.console.print("  [cyan]Palettes[/cyan]")
        for i, pal in enumerate(palettes, 1):
            mark = " [green]*[/green]" if pal["id"] == active_pal else "  "
            sw = palette_swatch_markup(pal)
            self.console.print(f"  {mark} [{i}] {sw}  {pal['name']}")
        self.console.print()
        try:
            prompt = getattr(self, "_prompt_session", None)
            if prompt is not None:
                choice = prompt.prompt(
                    [("class:prompt", "  Select theme (number or light/dark/auto): ")],
                ).strip()
            else:
                choice = input("  Select theme (number or light/dark/auto): ").strip()
        except (EOFError, KeyboardInterrupt):
            self.console.print("  [dim]Cancelled.[/dim]")
            return

        self._resolve_theme_choice(cfg, choice, palettes)

    def _resolve_theme_choice(self, cfg, choice: str, palettes) -> None:
        from ui.terminal.theme import normalize_palette_id

        token = (choice or "").strip().lower()
        if not token or token in {"__exit__", "exit", "quit", "q", "cancel"}:
            self.console.print("  [dim]Cancelled.[/dim]")
            return
        if token in {"light", "dark", "auto"}:
            self._apply_theme_mode(cfg, token)
            return
        if token in {"m1", "m2", "m3"}:
            self._apply_theme_mode(cfg, {"m1": "light", "m2": "dark", "m3": "auto"}[token])
            return
        if token.isdigit():
            idx = int(token)
            if 1 <= idx <= len(palettes):
                self._apply_theme_palette(cfg, palettes[idx - 1]["id"])
                return
        chosen = normalize_palette_id(token) or normalize_palette_id(
            token.replace(" ", "")
        )
        if chosen:
            self._apply_theme_palette(cfg, chosen)
            return
        self.console.print(
            f"  [yellow]Unknown theme[/yellow] [bold]{choice}[/bold]."
        )

    def _handle_theme_command(self, query: str) -> None:
        """Interactive picker, or direct ``/themes <palette|light|dark|auto>``."""
        from agent.config import Config
        from ui.terminal.theme import list_palettes, normalize_palette_id

        parts = (query or "").strip().split(maxsplit=1)
        arg = parts[1].strip() if len(parts) > 1 else ""

        cfg = Config.load()
        self.session.config = cfg

        if not arg or arg.lower() in {"list", "ls", "?", "pick", "select"}:
            self._prompt_theme_interactive(cfg)
            return

        token = arg.strip().lower()
        if token in {"light", "dark", "auto"}:
            self._apply_theme_mode(cfg, token)
            return

        palettes = list_palettes()
        chosen_id = None
        if token.isdigit():
            idx = int(token)
            if 1 <= idx <= len(palettes):
                chosen_id = palettes[idx - 1]["id"]
        if chosen_id is None:
            chosen_id = normalize_palette_id(token)
        if chosen_id is None:
            chosen_id = normalize_palette_id(arg.replace(" ", ""))
        if chosen_id is None:
            self.console.print(
                f"  [yellow]Unknown theme[/yellow] [bold]{arg}[/bold]. "
                "Use /themes to pick a preset."
            )
            return
        self._apply_theme_palette(cfg, chosen_id)
