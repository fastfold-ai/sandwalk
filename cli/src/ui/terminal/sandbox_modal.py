"""In-app /sandbox modal: Local / Modal CPU/GPU presets."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ui.terminal.themes_modal import (
    dim_transcript_styles_for_backdrop,
    themes_modal_style_extras,
)

DIALOG_WIDTH = 68
PAD_X = 3
LIST_HEIGHT = 22
DIALOG_HEIGHT = 8 + LIST_HEIGHT


@dataclass
class _SandboxRow:
    kind: str  # "header" | "option"
    title: str
    detail: str = ""
    option: Any | None = None
    search: str = ""
    current: bool = False


@dataclass
class _SandboxModalState:
    rows: list[_SandboxRow] = field(default_factory=list)
    filtered: list[_SandboxRow] = field(default_factory=list)
    index: int = 0
    query: str = ""
    open: bool = False
    scroll: int = 0
    status: str = ""


def sandbox_modal_style_extras(colors: dict[str, str]) -> dict[str, str]:
    base = themes_modal_style_extras(colors)
    out = {k.replace("themes-", "sandbox-", 1): v for k, v in base.items()}
    muted = colors["muted_fg"]
    panel = colors["panel_bg"]
    accent = colors["accent"]
    out["sandbox-section"] = f"bg:{panel} {accent} bold"
    out["sandbox-meta"] = f"bg:{panel} {muted}"
    out["sandbox-meta-selected"] = out.get(
        "sandbox-row-selected", f"bg:{accent} bold"
    )
    out["sandbox-desc"] = f"bg:{panel} {muted}"
    out["sandbox-desc-selected"] = out.get(
        "sandbox-row-selected", f"bg:{accent} bold"
    )
    return out


def build_sandbox_rows(cfg: Any, *, query: str = "") -> list[_SandboxRow]:
    from agent.sandbox_presets import (
        current_sandbox_pick_index,
        format_current_sandbox_summary,
        sandbox_pick_options,
    )

    options = sandbox_pick_options()
    current_idx = current_sandbox_pick_index(cfg, options)
    summary = format_current_sandbox_summary(cfg)
    rows: list[_SandboxRow] = [
        _SandboxRow(
            kind="header",
            title=f"Current · {summary}",
            search="current sandbox",
        )
    ]
    for i, option in enumerate(options):
        rows.append(
            _SandboxRow(
                kind="option",
                title=option.label,
                detail=option.detail,
                option=option,
                search=f"{option.label} {option.detail} {option.kind}".lower(),
                current=current_idx == i,
            )
        )
    q = (query or "").strip().lower()
    if not q:
        return rows
    out: list[_SandboxRow] = []
    header = rows[0]
    for row in rows[1:]:
        if q in row.search or q in row.title.lower() or q in row.detail.lower():
            if not out:
                out.append(header)
            out.append(row)
    return out


def first_selectable_index(rows: list[_SandboxRow], start: int = 0) -> int:
    if not rows:
        return 0
    n = len(rows)
    i = max(0, min(start, n - 1))
    for _ in range(n):
        if rows[i].kind == "option":
            return i
        i = (i + 1) % n
    return 0


class SandboxModalHost:
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
        self.state = _SandboxModalState()
        self.search_buf = Buffer(name="sandbox-search", multiline=False)
        self.search_buf.on_text_changed += self._on_search_text
        host = self
        self.is_open = Condition(lambda: host.state.open)

        class _ListControl(UIControl):
            def preferred_width(self, max_available_width: int) -> int:
                return max_available_width

            def preferred_height(
                self, width, max_available_height, wrap_lines, get_line_prefix
            ) -> int:
                return max(1, min(max_available_height, max(1, len(host.state.filtered))))

            def create_content(self, width: int, height: int) -> UIContent:
                st = host.state
                rows = st.filtered
                if st.index >= st.scroll + height:
                    st.scroll = st.index - height + 1
                elif st.index < st.scroll:
                    st.scroll = st.index
                st.scroll = max(0, st.scroll)

                def get_line(i: int):
                    abs_i = i + st.scroll
                    if abs_i >= len(rows):
                        return [("class:sandbox-row", " " * width)]
                    row = rows[abs_i]
                    inset = " " * PAD_X
                    if row.kind == "header":
                        label = f"{inset}{row.title}"
                        pad = " " * max(0, width - len(label))
                        return [("class:sandbox-section", f"{label}{pad}")]
                    selected = abs_i == st.index
                    style = (
                        "class:sandbox-row-selected"
                        if selected
                        else "class:sandbox-row"
                    )
                    desc_style = (
                        "class:sandbox-desc-selected"
                        if selected
                        else "class:sandbox-desc"
                    )
                    mark = "●" if row.current else " "
                    prefix = f"{inset}{mark} "
                    room = max(1, width - len(prefix) - len(inset))
                    title = row.title
                    if len(title) > room // 2:
                        title = title[: room // 2 - 1] + "…"
                    rest = room - len(title)
                    desc = ""
                    if row.detail and rest > 4:
                        desc = f"  {row.detail}"
                        if len(desc) > rest:
                            desc = desc[: rest - 1] + "…"
                    pad = " " * max(
                        0, width - len(prefix) - len(title) - len(desc) - len(inset)
                    )
                    return [
                        (style, prefix + title),
                        (desc_style, desc),
                        (style, pad + inset),
                    ]

                return UIContent(
                    get_line=get_line,
                    line_count=max(1, min(height, len(rows) or 1)),
                    show_cursor=False,
                )

            def mouse_handler(self, mouse_event):
                etype = mouse_event.event_type
                y = mouse_event.position.y + host.state.scroll
                if etype in (
                    MouseEventType.MOUSE_MOVE,
                    MouseEventType.MOUSE_DOWN,
                ):
                    host._move_to(y)
                    return None
                if etype == MouseEventType.MOUSE_UP:
                    host._move_to(y)
                    host.confirm()
                    return None
                return NotImplemented

        def _side_pad():
            return Window(
                width=PAD_X,
                char=" ",
                style="class:sandbox-dialog",
                dont_extend_width=True,
            )

        list_window = Window(
            content=_ListControl(),
            height=Dimension.exact(LIST_HEIGHT),
            style="class:sandbox-dialog",
        )
        header = VSplit(
            [
                _side_pad(),
                Window(
                    content=FormattedTextControl(
                        lambda: [("class:sandbox-title", "Sandbox")]
                    ),
                    dont_extend_width=True,
                    style="class:sandbox-dialog",
                ),
                Window(char=" ", style="class:sandbox-dialog"),
                Window(
                    content=FormattedTextControl(
                        lambda: [("class:sandbox-hint", "esc")]
                    ),
                    width=3,
                    style="class:sandbox-dialog",
                ),
                _side_pad(),
            ],
            height=1,
            style="class:sandbox-dialog",
        )
        search = VSplit(
            [
                _side_pad(),
                Window(
                    width=7,
                    content=FormattedTextControl(
                        lambda: [("class:sandbox-search.prompt", "Search ")]
                    ),
                    style="class:sandbox-search",
                ),
                Window(
                    content=BufferControl(buffer=self.search_buf, focusable=True),
                    height=1,
                    style="class:sandbox-search",
                ),
                _side_pad(),
            ],
            height=1,
            style="class:sandbox-search",
        )
        status = VSplit(
            [
                _side_pad(),
                Window(
                    content=FormattedTextControl(
                        lambda: [
                            ("class:sandbox-preview-accent", "┃"),
                            (
                                "class:sandbox-preview-panel",
                                f" {host.state.status or 'Enter applies · Modal prompts for base image'}",
                            ),
                        ]
                    ),
                    height=1,
                    style="class:sandbox-preview",
                ),
                _side_pad(),
            ],
            height=1,
            style="class:sandbox-preview",
        )
        hints = VSplit(
            [
                _side_pad(),
                Window(
                    content=FormattedTextControl(
                        lambda: [
                            ("class:sandbox-hint", "↑/↓ · enter apply · esc")
                        ]
                    ),
                    height=1,
                    style="class:sandbox-dialog",
                ),
                _side_pad(),
            ],
            height=1,
            style="class:sandbox-dialog",
        )
        dialog = HSplit(
            [
                Window(height=1, char=" ", style="class:sandbox-dialog"),
                header,
                search,
                Window(height=1, char=" ", style="class:sandbox-dialog"),
                list_window,
                Window(height=1, char=" ", style="class:sandbox-dialog"),
                status,
                hints,
                Window(height=1, char=" ", style="class:sandbox-dialog"),
            ],
            width=Dimension.exact(DIALOG_WIDTH),
            height=Dimension.exact(DIALOG_HEIGHT),
            style="class:sandbox-dialog",
        )
        with_shadow = HSplit(
            [
                VSplit(
                    [
                        dialog,
                        Window(width=1, char=" ", style="class:sandbox-shadow"),
                    ],
                    height=Dimension.exact(DIALOG_HEIGHT),
                ),
                VSplit(
                    [
                        Window(width=1, char=" "),
                        Window(
                            width=DIALOG_WIDTH,
                            height=1,
                            char=" ",
                            style="class:sandbox-shadow",
                        ),
                    ],
                    height=1,
                ),
            ],
            width=Dimension.exact(DIALOG_WIDTH + 1),
            height=Dimension.exact(DIALOG_HEIGHT + 1),
            style="class:sandbox-dialog",
        )
        self.floats = [
            Float(
                content=ConditionalContainer(content=with_shadow, filter=self.is_open),
                z_index=10**8,
            )
        ]
        self.key_bindings = KeyBindings()

        @self.key_bindings.add("up", filter=self.is_open, eager=True)
        @self.key_bindings.add("c-p", filter=self.is_open, eager=True)
        def _up(_e):
            host._move(-1)

        @self.key_bindings.add("down", filter=self.is_open, eager=True)
        @self.key_bindings.add("c-n", filter=self.is_open, eager=True)
        def _down(_e):
            host._move(1)

        @self.key_bindings.add("pageup", filter=self.is_open, eager=True)
        def _pgup(_e):
            host._move(-8)

        @self.key_bindings.add("pagedown", filter=self.is_open, eager=True)
        def _pgdn(_e):
            host._move(8)

        @self.key_bindings.add("enter", filter=self.is_open, eager=True)
        def _enter(_e):
            host.confirm()

        @self.key_bindings.add("escape", filter=self.is_open, eager=True)
        @self.key_bindings.add("c-c", filter=self.is_open, eager=True)
        def _esc(_e):
            host.cancel()

    def _cfg(self):
        from agent.config import Config

        return getattr(getattr(self.terminal, "session", None), "config", None) or Config.load()

    def _rebuild_rows(self) -> None:
        self.state.rows = build_sandbox_rows(self._cfg(), query=self.state.query)
        self.state.filtered = list(self.state.rows)
        # Prefer current option
        for i, row in enumerate(self.state.filtered):
            if row.kind == "option" and row.current:
                self.state.index = i
                break
        else:
            self.state.index = first_selectable_index(self.state.filtered)
        self.state.scroll = 0

    def _on_search_text(self, _buf) -> None:
        if not self.state.open:
            return
        self.state.query = self.search_buf.text
        self._rebuild_rows()
        self._invalidate()

    def _current(self) -> _SandboxRow | None:
        rows = self.state.filtered
        if not rows:
            return None
        row = rows[max(0, min(self.state.index, len(rows) - 1))]
        return row if row.kind == "option" else None

    def _move(self, delta: int) -> None:
        rows = self.state.filtered
        if not rows:
            return
        n = len(rows)
        i = self.state.index
        for _ in range(n):
            i = (i + delta) % n
            if rows[i].kind == "option":
                self.state.index = i
                self._invalidate()
                return

    def _move_to(self, idx: int) -> None:
        rows = self.state.filtered
        if not rows or idx < 0 or idx >= len(rows) or rows[idx].kind != "option":
            return
        self.state.index = idx
        self._invalidate()

    def _invalidate(self) -> None:
        self._on_style_refresh()
        try:
            if self.app.is_running:
                self.app.invalidate()
        except Exception:  # noqa: BLE001
            pass

    def open(self) -> None:
        self.state = _SandboxModalState(open=True)
        self.search_buf.reset()
        self._rebuild_rows()
        try:
            self.app.layout.focus(self.search_buf)
        except Exception:  # noqa: BLE001
            pass
        self._invalidate()

    def confirm(self) -> None:
        from agent.sandbox_presets import apply_sandbox_pick, current_sandbox_pick_index

        row = self._current()
        if not self.state.open or row is None or row.option is None:
            return
        cfg = self._cfg()
        options = [r.option for r in self.state.rows if r.kind == "option" and r.option]
        # Find index among full options list
        from agent.sandbox_presets import sandbox_pick_options

        all_opts = sandbox_pick_options()
        try:
            choice_idx = all_opts.index(row.option)
        except ValueError:
            choice_idx = -1
        current_idx = current_sandbox_pick_index(cfg, all_opts)
        already = choice_idx == current_idx
        selected = row.option
        self.state.open = False
        self._on_style_refresh()
        self._focus_compose()
        self._invalidate()

        console = getattr(self.terminal, "console", None)
        if already and selected.kind == "builtin":
            if console is not None:
                console.print(f"  [dim]Already using {selected.label}.[/dim]")
            return
        if not already:
            try:
                label = apply_sandbox_pick(selected, cfg)
            except RuntimeError as exc:
                if console is not None:
                    console.print(f"  [red]{exc}[/red]")
                return
            sess = getattr(self.terminal, "session", None)
            if sess is not None:
                sess.config = cfg
            refresh = getattr(self.terminal, "_refresh_cli_sandbox_label", None)
            if callable(refresh):
                refresh()
            if console is not None:
                console.print(f"  [green]Sandbox → {label}[/green] — {selected.label}")
        elif console is not None:
            console.print(f"  [dim]Already using {selected.label}.[/dim]")

        if selected.kind != "builtin":
            prompt_img = getattr(self.terminal, "_prompt_sandbox_base_image", None)
            schedule = getattr(self.terminal, "_schedule_host_terminal", None)
            if callable(prompt_img) and callable(schedule):
                schedule(
                    prompt_img,
                    cfg,
                    compute_type="gpu" if selected.kind == "modal_gpu" else "cpu",
                )
            elif callable(prompt_img):
                prompt_img(
                    cfg,
                    compute_type="gpu" if selected.kind == "modal_gpu" else "cpu",
                )

    def cancel(self) -> None:
        if not self.state.open:
            return
        self.state.open = False
        self._on_style_refresh()
        self._focus_compose()
        self._invalidate()


def run_sandbox_modal(terminal: Any) -> bool:
    import os
    import sys

    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    host = getattr(terminal, "_sandbox_modal_host", None)
    app = getattr(terminal, "_transcript_app", None)
    if host is not None and getattr(app, "is_running", False):
        host.open()
        return True
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return False

    from prompt_toolkit.application import Application
    from prompt_toolkit.key_binding import KeyBindings, merge_key_bindings
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
        styles.update(sandbox_modal_style_extras(colors))
        styles = dim_transcript_styles_for_backdrop(styles)
        nested.style = Style.from_dict(styles)
        try:
            nested.invalidate()
        except Exception:  # noqa: BLE001
            pass

    canvas = Window(char=" ", style="class:sandbox-dialog")
    root = FloatContainer(content=canvas, floats=[])
    nested_app = Application(
        layout=Layout(root),
        key_bindings=KeyBindings(),
        full_screen=True,
        mouse_support=True,
        color_depth=ColorDepth.TRUE_COLOR,
    )
    held["app"] = nested_app
    host = SandboxModalHost(
        terminal, app=nested_app, on_style_refresh=_refresh, focus_compose=lambda: None
    )
    root.floats.extend(host.floats)
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
        return False
