"""OpenCode-style /themes modal: search, arrows, hover preview, Esc restores.

When the transcript Application is running, the modal is an in-app centered
Float over the live session (content stays visible around it). Live preview
restyles the whole TUI; Esc restores.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class _ThemeOption:
    kind: str  # "palette" | "mode"
    value: str
    title: str
    search: str = ""


@dataclass
class _ThemesModalState:
    options: list[_ThemeOption]
    filtered: list[_ThemeOption] = field(default_factory=list)
    index: int = 0
    query: str = ""
    open: bool = False
    confirmed: bool = False
    initial_palette: str = "default"
    initial_mode: str = "auto"
    preview_palette: str = "default"
    preview_mode: str = "auto"
    scroll: int = 0


DIALOG_WIDTH = 56
DIALOG_HEIGHT = 20  # title + search + list(~12) + preview + hints
LIST_HEIGHT = 12


def build_theme_options(palettes: list[dict], mode: str) -> list[_ThemeOption]:
    del mode  # reserved for future "current mode" annotations
    opts: list[_ThemeOption] = []
    for token, label in (("light", "light"), ("dark", "dark"), ("auto", "auto")):
        opts.append(
            _ThemeOption(
                kind="mode",
                value=token,
                title=f"Mode · {label}",
                search=f"mode {label} {token}",
            )
        )
    for pal in palettes:
        name = str(pal.get("name") or pal.get("id") or "")
        pid = str(pal.get("id") or "")
        opts.append(
            _ThemeOption(
                kind="palette",
                value=pid,
                title=name,
                search=f"{name} {pid} {pal.get('description') or ''}",
            )
        )
    return opts


def filter_theme_options(
    options: list[_ThemeOption], query: str
) -> list[_ThemeOption]:
    q = (query or "").strip().lower()
    if not q:
        return list(options)
    return [
        opt
        for opt in options
        if q in opt.search.lower() or q in opt.title.lower() or q in opt.value.lower()
    ]


def _swatch_frags(pal: dict, *, panel_bg: str) -> list[tuple[str, str]]:
    swatches = list(pal.get("swatches") or [])
    top = str(swatches[0] if swatches else "#888888")
    bottom = str(swatches[-1] if len(swatches) > 1 else top)
    return [(f"fg:{top} bg:{bottom}", "▄"), (f"bg:{panel_bg}", " ")]


class ThemesModalHost:
    """In-app themes overlay hosted by the transcript FloatContainer."""

    def __init__(
        self,
        terminal: Any,
        *,
        app: Any,
        on_style_refresh: Callable[[], None],
        focus_compose: Callable[[], None],
    ) -> None:
        from prompt_toolkit.buffer import Buffer
        from prompt_toolkit.filters import Condition
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout.containers import (
            ConditionalContainer,
            Float,
            HSplit,
            VSplit,
            Window,
        )
        from prompt_toolkit.layout.controls import (
            BufferControl,
            FormattedTextControl,
            UIContent,
            UIControl,
        )
        from prompt_toolkit.layout.dimension import Dimension
        from prompt_toolkit.mouse_events import MouseEventType

        self.terminal = terminal
        self.app = app
        self._on_style_refresh = on_style_refresh
        self._focus_compose = focus_compose
        self.state = _ThemesModalState(options=[])
        self.search_buf = Buffer(name="themes-search", multiline=False)
        self.search_buf.on_text_changed += self._on_search_text

        host = self
        self.is_open = Condition(lambda: host.state.open)

        class _ThemeListControl(UIControl):
            def preferred_width(self, max_available_width: int) -> int:
                return max_available_width

            def preferred_height(
                self,
                width: int,
                max_available_height: int,
                wrap_lines: bool,
                get_line_prefix,
            ) -> int:
                return max(1, min(max_available_height, max(1, len(host.state.filtered))))

            def create_content(self, width: int, height: int) -> UIContent:
                from ui.terminal.theme import get_palette, panel_palette

                st = host.state
                colors = panel_palette(
                    host._resolved_mode(), palette=st.preview_palette
                )
                panel_bg = colors["panel_bg"]
                rows = st.filtered
                if st.index >= st.scroll + height:
                    st.scroll = st.index - height + 1
                elif st.index < st.scroll:
                    st.scroll = st.index
                st.scroll = max(0, st.scroll)

                def get_line(i: int):
                    abs_i = i + st.scroll
                    if abs_i >= len(rows):
                        return [("class:themes-row", " " * width)]
                    opt = rows[abs_i]
                    selected = abs_i == st.index
                    is_current = (
                        opt.kind == "palette" and opt.value == st.initial_palette
                    ) or (opt.kind == "mode" and opt.value == st.initial_mode)
                    style = (
                        "class:themes-row-selected" if selected else "class:themes-row"
                    )
                    gutter = "●" if is_current else " "
                    gutter_style = (
                        "class:themes-row-selected"
                        if selected
                        else "class:themes-row-current"
                    )
                    frags: list[tuple[str, str]] = [(gutter_style, f" {gutter} ")]
                    if opt.kind == "palette":
                        frags.extend(
                            _swatch_frags(get_palette(opt.value), panel_bg=panel_bg)
                        )
                    else:
                        frags.append((f"bg:{panel_bg}", "  "))
                    label = opt.title
                    used = 6
                    max_label = max(1, width - used)
                    if len(label) > max_label:
                        label = label[: max_label - 1] + "…"
                    pad = " " * max(0, width - used - len(label))
                    frags.append((style, f"{label}{pad}"))
                    return frags

                return UIContent(
                    get_line=get_line,
                    line_count=max(1, min(height, len(rows) or 1)),
                    show_cursor=False,
                )

            def mouse_handler(self, mouse_event):
                y = mouse_event.position.y + host.state.scroll
                if mouse_event.event_type == MouseEventType.MOUSE_MOVE:
                    host._move_to(y)
                    return None
                if mouse_event.event_type == MouseEventType.MOUSE_DOWN:
                    host._move_to(y)
                    return None
                if mouse_event.event_type == MouseEventType.MOUSE_UP:
                    host._move_to(y)
                    host.confirm()
                    return None
                return NotImplemented

        list_window = Window(
            content=_ThemeListControl(),
            height=Dimension.exact(LIST_HEIGHT),
            dont_extend_height=True,
            style="class:themes-dialog",
        )

        dialog = HSplit(
            [
                Window(
                    content=FormattedTextControl(self._header),
                    height=1,
                    style="class:themes-dialog",
                ),
                VSplit(
                    [
                        Window(
                            width=9,
                            content=FormattedTextControl(
                                lambda: [("class:themes-search.prompt", "  Search ")]
                            ),
                            style="class:themes-search",
                        ),
                        Window(
                            content=BufferControl(
                                buffer=self.search_buf, focusable=True
                            ),
                            height=1,
                            style="class:themes-search",
                        ),
                    ],
                    height=1,
                    style="class:themes-search",
                ),
                Window(height=1, char=" ", style="class:themes-dialog"),
                list_window,
                Window(height=1, char=" ", style="class:themes-dialog"),
                Window(
                    content=FormattedTextControl(self._preview_strip),
                    height=1,
                    style="class:themes-preview",
                ),
                Window(
                    content=FormattedTextControl(
                        lambda: [
                            (
                                "class:themes-hint",
                                "  ↑/↓ or hover preview · enter confirm · esc cancel",
                            )
                        ]
                    ),
                    height=1,
                    style="class:themes-dialog",
                ),
            ],
            width=Dimension.exact(DIALOG_WIDTH),
            height=Dimension.exact(DIALOG_HEIGHT),
            style="class:themes-dialog",
        )

        # Frame the dialog so it reads as a modal over live transcript content.
        # (TTYs can't alpha-blend; a full-screen dim would erase the session.)
        framed = HSplit(
            [
                Window(
                    height=1,
                    char="─",
                    style="class:themes-frame",
                ),
                dialog,
                Window(
                    height=1,
                    char="─",
                    style="class:themes-frame",
                ),
            ],
            width=Dimension.exact(DIALOG_WIDTH),
            height=Dimension.exact(DIALOG_HEIGHT + 2),
            style="class:themes-dialog",
        )
        dialog_layer = ConditionalContainer(content=framed, filter=self.is_open)

        # Centered float only — transcript stays visible around the panel.
        self.floats = [
            Float(
                content=dialog_layer,
                z_index=10**8,
            ),
        ]

        self.key_bindings = KeyBindings()

        @self.key_bindings.add("up", filter=self.is_open, eager=True)
        @self.key_bindings.add("c-p", filter=self.is_open, eager=True)
        def _up(_event):
            host._move(-1)

        @self.key_bindings.add("down", filter=self.is_open, eager=True)
        @self.key_bindings.add("c-n", filter=self.is_open, eager=True)
        def _down(_event):
            host._move(1)

        @self.key_bindings.add("pageup", filter=self.is_open, eager=True)
        def _pgup(_event):
            host._move(-10)

        @self.key_bindings.add("pagedown", filter=self.is_open, eager=True)
        def _pgdn(_event):
            host._move(10)

        @self.key_bindings.add("enter", filter=self.is_open, eager=True)
        def _enter(_event):
            host.confirm()

        @self.key_bindings.add("escape", filter=self.is_open, eager=True)
        @self.key_bindings.add("c-c", filter=self.is_open, eager=True)
        def _esc(_event):
            host.cancel()

    def _header(self):
        return [
            ("class:themes-title", "  Themes"),
            ("class:themes-hint", "                              esc  "),
        ]

    def _preview_strip(self):
        from ui.terminal.theme import get_palette

        name = get_palette(self.state.preview_palette)["name"]
        return [
            ("class:themes-preview-accent", "┃"),
            ("class:themes-preview-panel", f" {name} · {self.state.preview_mode}  "),
            ("class:themes-hint", "preview"),
        ]

    def _resolved_mode(self) -> str:
        from ui.terminal.theme import resolve_ui_theme

        if self.state.preview_mode in {"light", "dark"}:
            return self.state.preview_mode
        cfg = getattr(getattr(self.terminal, "session", None), "config", None)
        return resolve_ui_theme(cfg)

    def _cfg(self):
        return self.terminal.session.config

    def _apply_preview(self, opt: _ThemeOption | None) -> None:
        if opt is None:
            return
        if opt.kind == "mode":
            self.state.preview_mode = opt.value
        else:
            self.state.preview_palette = opt.value
        cfg = self._cfg()
        cfg.set("ui.theme", self.state.preview_mode)
        cfg.set("ui.palette", self.state.preview_palette)
        self._on_style_refresh()
        try:
            if self.app.is_running:
                self.app.invalidate()
        except Exception:  # noqa: BLE001
            pass

    def _move(self, delta: int) -> None:
        if not self.state.filtered:
            return
        self.state.index = (self.state.index + delta) % len(self.state.filtered)
        self._apply_preview(self.state.filtered[self.state.index])

    def _move_to(self, idx: int) -> None:
        if not self.state.filtered or idx < 0 or idx >= len(self.state.filtered):
            return
        if idx == self.state.index:
            return
        self.state.index = idx
        self._apply_preview(self.state.filtered[self.state.index])

    def _on_search_text(self, _buf) -> None:
        if not self.state.open:
            return
        self.state.query = self.search_buf.text
        self.state.filtered = filter_theme_options(self.state.options, self.state.query)
        self.state.index = 0
        self.state.scroll = 0
        if not self.state.query.strip():
            self.state.preview_palette = self.state.initial_palette
            self.state.preview_mode = self.state.initial_mode
            cfg = self._cfg()
            cfg.set("ui.theme", self.state.initial_mode)
            cfg.set("ui.palette", self.state.initial_palette)
            self._on_style_refresh()
            try:
                if self.app.is_running:
                    self.app.invalidate()
            except Exception:  # noqa: BLE001
                pass
            return
        if self.state.filtered:
            self._apply_preview(self.state.filtered[0])

    def open(self) -> None:
        from ui.terminal.theme import list_palettes, resolve_ui_palette

        cfg = self._cfg()
        mode = str(cfg.get("ui.theme") or "auto").strip().lower() or "auto"
        active_pal = resolve_ui_palette(cfg)
        self.state = _ThemesModalState(
            options=build_theme_options(list_palettes(), mode),
            initial_palette=active_pal,
            initial_mode=mode,
            preview_palette=active_pal,
            preview_mode=mode,
            open=True,
        )
        self.state.filtered = filter_theme_options(self.state.options, "")
        self.search_buf.reset()
        for i, opt in enumerate(self.state.filtered):
            if opt.kind == "palette" and opt.value == active_pal:
                self.state.index = i
                break
        if self.state.filtered:
            self._apply_preview(self.state.filtered[self.state.index])
        try:
            self.app.layout.focus(self.search_buf)
        except Exception:  # noqa: BLE001
            pass
        try:
            if self.app.is_running:
                self.app.invalidate()
        except Exception:  # noqa: BLE001
            pass

    def confirm(self) -> None:
        if not self.state.open or not self.state.filtered:
            return
        opt = self.state.filtered[self.state.index]
        self.state.confirmed = True
        cfg = self._cfg()
        if opt.kind == "mode":
            cfg.set("ui.theme", opt.value)
        else:
            cfg.set("ui.palette", opt.value)
        cfg.save()
        self.terminal.session.config = cfg
        self.state.open = False
        self._on_style_refresh()
        self._focus_compose()
        console = getattr(self.terminal, "console", None)
        if console is not None:
            from ui.terminal.theme import (
                get_palette,
                resolve_ui_palette,
                resolve_ui_theme,
            )

            resolved = resolve_ui_theme(cfg)
            pal = get_palette(resolve_ui_palette(cfg))
            colors = pal[resolved]
            console.print(
                f"  [green]Palette:[/green] {pal['name']} "
                f"[dim]({pal['id']} · {resolved})[/dim]"
            )
            console.print(
                f"  [{colors['canvas_bg']}]██[/] canvas  "
                f"[{colors['panel_bg']}]██[/] panel  "
                f"[{colors['accent']}]██[/] accent"
            )
        try:
            if self.app.is_running:
                self.app.invalidate()
        except Exception:  # noqa: BLE001
            pass

    def cancel(self) -> None:
        if not self.state.open:
            return
        cfg = self._cfg()
        cfg.set("ui.theme", self.state.initial_mode)
        cfg.set("ui.palette", self.state.initial_palette)
        self.terminal.session.config = cfg
        self.state.open = False
        self.state.confirmed = False
        self._on_style_refresh()
        self._focus_compose()
        try:
            if self.app.is_running:
                self.app.invalidate()
        except Exception:  # noqa: BLE001
            pass


def themes_modal_style_extras(colors: dict[str, str]) -> dict[str, str]:
    """Extra style keys for the themes overlay (merged into transcript styles)."""
    from ui.terminal.theme import _contrast_on

    accent = colors["accent"]
    panel = colors["panel_bg"]
    panel_fg = colors["panel_fg"]
    muted = colors["muted_fg"]
    canvas = colors["canvas_bg"]
    on_accent = _contrast_on(accent)
    return {
        "themes-dialog": f"bg:{panel} {panel_fg}",
        "themes-title": f"bg:{panel} {panel_fg} bold",
        "themes-hint": f"bg:{panel} {muted}",
        "themes-search": f"bg:{panel} {panel_fg}",
        "themes-search.prompt": f"bg:{panel} {muted}",
        "themes-row": f"bg:{panel} {panel_fg}",
        "themes-row-current": f"bg:{panel} {accent}",
        "themes-row-selected": f"bg:{accent} {on_accent} bold",
        "themes-preview": f"bg:{canvas} {colors['canvas_fg']}",
        "themes-preview-panel": f"bg:{panel} {panel_fg}",
        "themes-preview-accent": f"bg:{canvas} {accent}",
        "themes-frame": f"bg:{panel} {muted}",
        "themes-dim": f"fg:{muted}",
    }


def run_themes_modal(terminal: Any) -> bool:
    """Open the themes UI. Prefers in-app overlay; nested fullscreen is fallback."""
    import os
    import sys

    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False

    host = getattr(terminal, "_themes_modal_host", None)
    app = getattr(terminal, "_transcript_app", None)
    if host is not None and getattr(app, "is_running", False):
        host.open()
        return True

    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return False

    from prompt_toolkit.application import Application
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import Layout
    from prompt_toolkit.layout.containers import FloatContainer, Window
    from prompt_toolkit.output.color_depth import ColorDepth
    from prompt_toolkit.styles import Style

    from ui.terminal.theme import (
        panel_palette,
        resolve_ui_palette,
        resolve_ui_theme,
        transcript_style_dict,
    )

    held: dict[str, Any] = {}

    def _refresh():
        nested = held.get("app")
        cfg = getattr(getattr(terminal, "session", None), "config", None)
        if nested is None or cfg is None:
            return
        mode = resolve_ui_theme(cfg)
        pal = resolve_ui_palette(cfg)
        colors = panel_palette(mode, palette=pal)
        styles = transcript_style_dict(mode, palette=pal, config=cfg)
        styles.update(themes_modal_style_extras(colors))
        nested.style = Style.from_dict(styles)
        try:
            nested.invalidate()
        except Exception:  # noqa: BLE001
            pass

    # Shell Application: dim canvas + host floats (fixed dialog size → no strip).
    canvas = Window(char="░", style="class:themes-dim")
    root = FloatContainer(content=canvas, floats=[])
    nested_app = Application(
        layout=Layout(root),
        key_bindings=KeyBindings(),
        full_screen=True,
        mouse_support=True,
        color_depth=ColorDepth.TRUE_COLOR,
    )
    held["app"] = nested_app

    host = ThemesModalHost(
        terminal,
        app=nested_app,
        on_style_refresh=_refresh,
        focus_compose=lambda: None,
    )
    root.floats.extend(host.floats)
    from prompt_toolkit.key_binding import merge_key_bindings

    nested_app.key_bindings = merge_key_bindings([host.key_bindings])
    _refresh()

    original_confirm = host.confirm
    original_cancel = host.cancel

    def _confirm_and_exit():
        original_confirm()
        if nested_app.is_running:
            nested_app.exit(result=True)

    def _cancel_and_exit():
        original_cancel()
        if nested_app.is_running:
            nested_app.exit(result=False)

    host.confirm = _confirm_and_exit  # type: ignore[method-assign]
    host.cancel = _cancel_and_exit  # type: ignore[method-assign]
    host.open()

    try:
        return bool(nested_app.run())
    except Exception:  # noqa: BLE001
        try:
            original_cancel()
        except Exception:  # noqa: BLE001
            pass
        return False
