"""In-app /tools modal: searchable catalog over the live transcript."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ui.terminal.themes_modal import (
    dim_transcript_styles_for_backdrop,
    themes_modal_style_extras,
)

DIALOG_WIDTH = 72
PAD_X = 3
LIST_HEIGHT = 32
DIALOG_HEIGHT = 8 + LIST_HEIGHT


@dataclass
class _ToolRow:
    kind: str  # "header" | "tool"
    title: str
    tool: Any | None = None
    search: str = ""
    description: str = ""
    meta: str = ""  # status · category


@dataclass
class _ToolsModalState:
    tools: list[Any] = field(default_factory=list)
    rows: list[_ToolRow] = field(default_factory=list)
    filtered: list[_ToolRow] = field(default_factory=list)
    index: int = 0
    query: str = ""
    open: bool = False
    scroll: int = 0


def lean_description(text: str, *, max_len: int = 48) -> str:
    one = " ".join((text or "").split())
    if len(one) <= max_len:
        return one
    return one[: max_len - 1] + "…"


def tool_status_label(tool: Any) -> str:
    from tools.registry import EXPERIMENTAL_CATEGORIES

    name = str(getattr(tool, "name", "") or "")
    category = str(getattr(tool, "category", "") or "")
    if name == "claude.code":
        return "guarded"
    if category in EXPERIMENTAL_CATEGORIES:
        return "experimental"
    return "stable"


def tool_meta_label(tool: Any) -> str:
    status = tool_status_label(tool)
    category = str(getattr(tool, "category", "") or "").strip()
    bits = [status]
    if category:
        bits.append(category)
    return " · ".join(bits)


def collect_tools_for_modal() -> list[Any]:
    from tools import ensure_loaded, registry

    ensure_loaded()
    return list(registry.list_tools())


def build_tool_rows(tools: list[Any], *, query: str = "") -> list[_ToolRow]:
    q = (query or "").strip().lower()

    def matches(tool: Any) -> bool:
        if not q:
            return True
        blob = " ".join(
            [
                str(getattr(tool, "name", "") or ""),
                str(getattr(tool, "description", "") or ""),
                str(getattr(tool, "category", "") or ""),
                tool_meta_label(tool),
                " ".join(getattr(tool, "requires_data", None) or []),
            ]
        ).lower()
        return q in blob

    matched = [t for t in tools if matches(t)]
    stable = [t for t in matched if tool_status_label(t) == "stable"]
    experimental = [t for t in matched if tool_status_label(t) == "experimental"]
    guarded = [t for t in matched if tool_status_label(t) == "guarded"]

    rows: list[_ToolRow] = []

    def add_section(title: str, items: list[Any]) -> None:
        if not items:
            return
        rows.append(_ToolRow(kind="header", title=title, search=title.lower()))
        for tool in items:
            name = str(getattr(tool, "name", "") or "")
            desc = lean_description(str(getattr(tool, "description", "") or ""))
            meta = tool_meta_label(tool)
            search = " ".join(
                [
                    name,
                    str(getattr(tool, "description", "") or ""),
                    str(getattr(tool, "category", "") or ""),
                    meta,
                ]
            )
            rows.append(
                _ToolRow(
                    kind="tool",
                    title=name,
                    tool=tool,
                    search=search,
                    description=desc,
                    meta=meta,
                )
            )

    add_section("Stable", stable)
    add_section("Experimental", experimental)
    add_section("Guarded", guarded)
    return rows


def first_selectable_index(rows: list[_ToolRow], start: int = 0) -> int:
    if not rows:
        return 0
    n = len(rows)
    i = max(0, min(start, n - 1))
    for _ in range(n):
        if rows[i].kind == "tool":
            return i
        i = (i + 1) % n
    return 0


def tools_modal_style_extras(colors: dict[str, str]) -> dict[str, str]:
    base = themes_modal_style_extras(colors)
    out = {k.replace("themes-", "tools-", 1): v for k, v in base.items()}
    muted = colors["muted_fg"]
    panel = colors["panel_bg"]
    accent = colors["accent"]
    out["tools-section"] = f"bg:{panel} {accent} bold"
    out["tools-meta"] = f"bg:{panel} {muted}"
    out["tools-meta-selected"] = out.get("tools-row-selected", f"bg:{accent} bold")
    out["tools-desc"] = f"bg:{panel} {muted}"
    out["tools-desc-selected"] = out.get("tools-row-selected", f"bg:{accent} bold")
    return out


class ToolsModalHost:
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
        self.state = _ToolsModalState()
        self._list_viewport_h = LIST_HEIGHT
        self.search_buf = Buffer(name="tools-search", multiline=False)
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
                host._list_viewport_h = max(1, height)
                if st.index >= st.scroll + height:
                    st.scroll = st.index - height + 1
                elif st.index < st.scroll:
                    st.scroll = st.index
                st.scroll = max(0, st.scroll)

                def get_line(i: int):
                    abs_i = i + st.scroll
                    if abs_i >= len(rows):
                        return [("class:tools-row", " " * width)]
                    row = rows[abs_i]
                    inset = " " * PAD_X
                    if row.kind == "header":
                        label = f"{inset}{row.title}"
                        pad = " " * max(0, width - len(label))
                        return [("class:tools-section", f"{label}{pad}")]
                    selected = abs_i == st.index
                    style = (
                        "class:tools-row-selected" if selected else "class:tools-row"
                    )
                    right_style = (
                        "class:tools-meta-selected" if selected else "class:tools-meta"
                    )
                    desc_style = (
                        "class:tools-desc-selected" if selected else "class:tools-desc"
                    )
                    right = f"{row.meta}{inset}" if row.meta else inset
                    prefix = f"{inset}"
                    room = max(1, width - len(prefix) - len(right))
                    title = row.title
                    title_budget = min(len(title), max(10, room // 3))
                    if len(title) > title_budget:
                        title = title[: title_budget - 1] + "…"
                    rest = room - len(title)
                    desc = ""
                    if row.description and rest > 4:
                        desc = f" {row.description}"
                        if len(desc) > rest:
                            desc = desc[: rest - 1] + "…"
                    pad = " " * max(
                        0, width - len(prefix) - len(title) - len(desc) - len(right)
                    )
                    return [
                        (style, prefix + title),
                        (desc_style, desc),
                        (style, pad),
                        (right_style, right),
                    ]

                return UIContent(
                    get_line=get_line,
                    line_count=max(1, min(height, len(rows) or 1)),
                    show_cursor=False,
                )

            def mouse_handler(self, mouse_event):
                etype = mouse_event.event_type
                if etype == MouseEventType.SCROLL_UP:
                    host._scroll_by(-3)
                    return None
                if etype == MouseEventType.SCROLL_DOWN:
                    host._scroll_by(3)
                    return None
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
                width=PAD_X, char=" ", style="class:tools-dialog", dont_extend_width=True
            )

        list_window = Window(
            content=_ListControl(),
            height=Dimension.exact(LIST_HEIGHT),
            style="class:tools-dialog",
        )
        header = VSplit(
            [
                _side_pad(),
                Window(
                    content=FormattedTextControl(
                        lambda: [("class:tools-title", "Tools")]
                    ),
                    dont_extend_width=True,
                    style="class:tools-dialog",
                ),
                Window(char=" ", style="class:tools-dialog"),
                Window(
                    content=FormattedTextControl(
                        lambda: [("class:tools-hint", "esc")]
                    ),
                    width=3,
                    style="class:tools-dialog",
                ),
                _side_pad(),
            ],
            height=1,
            style="class:tools-dialog",
        )
        search = VSplit(
            [
                _side_pad(),
                Window(
                    width=7,
                    content=FormattedTextControl(
                        lambda: [("class:tools-search.prompt", "Search ")]
                    ),
                    style="class:tools-search",
                ),
                Window(
                    content=BufferControl(buffer=self.search_buf, focusable=True),
                    height=1,
                    style="class:tools-search",
                ),
                _side_pad(),
            ],
            height=1,
            style="class:tools-search",
        )
        status = VSplit(
            [
                _side_pad(),
                Window(
                    content=FormattedTextControl(self._status_strip),
                    height=1,
                    style="class:tools-preview",
                ),
                _side_pad(),
            ],
            height=1,
            style="class:tools-preview",
        )
        hints = VSplit(
            [
                _side_pad(),
                Window(
                    content=FormattedTextControl(
                        lambda: [
                            ("class:tools-hint", "↑/↓ · enter close · esc")
                        ]
                    ),
                    height=1,
                    style="class:tools-dialog",
                ),
                _side_pad(),
            ],
            height=1,
            style="class:tools-dialog",
        )
        dialog = HSplit(
            [
                Window(height=1, char=" ", style="class:tools-dialog"),
                header,
                search,
                Window(height=1, char=" ", style="class:tools-dialog"),
                list_window,
                Window(height=1, char=" ", style="class:tools-dialog"),
                status,
                hints,
                Window(height=1, char=" ", style="class:tools-dialog"),
            ],
            width=Dimension.exact(DIALOG_WIDTH),
            height=Dimension.exact(DIALOG_HEIGHT),
            style="class:tools-dialog",
        )
        with_shadow = HSplit(
            [
                VSplit(
                    [
                        dialog,
                        Window(width=1, char=" ", style="class:tools-shadow"),
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
                            style="class:tools-shadow",
                        ),
                    ],
                    height=1,
                ),
            ],
            width=Dimension.exact(DIALOG_WIDTH + 1),
            height=Dimension.exact(DIALOG_HEIGHT + 1),
            style="class:tools-dialog",
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
            host._move(-10)

        @self.key_bindings.add("pagedown", filter=self.is_open, eager=True)
        def _pgdn(_e):
            host._move(10)

        @self.key_bindings.add("enter", filter=self.is_open, eager=True)
        def _enter(_e):
            host.confirm()

        @self.key_bindings.add("escape", filter=self.is_open, eager=True)
        @self.key_bindings.add("c-c", filter=self.is_open, eager=True)
        def _esc(_e):
            host.cancel()

    def _status_strip(self):
        row = None
        if self.state.filtered and 0 <= self.state.index < len(self.state.filtered):
            cand = self.state.filtered[self.state.index]
            if cand.kind == "tool":
                row = cand
        n = len(self.state.tools)
        shown = len([r for r in self.state.filtered if r.kind == "tool"])
        bits = [f"{shown}/{n} tools"]
        if row is not None:
            desc = lean_description(
                str(getattr(row.tool, "description", "") or ""), max_len=40
            )
            if desc:
                bits.append(desc)
        text = " · ".join(bits)
        max_len = max(12, DIALOG_WIDTH - PAD_X * 2 - 4)
        if len(text) > max_len:
            text = text[: max_len - 1] + "…"
        return [
            ("class:tools-preview-accent", "┃"),
            ("class:tools-preview-panel", f" {text}"),
        ]

    def _rebuild_rows(self, *, keep_name: str | None = None) -> None:
        self.state.rows = build_tool_rows(self.state.tools, query=self.state.query)
        self.state.filtered = list(self.state.rows)
        if keep_name:
            key = keep_name.strip().lower()
            for i, row in enumerate(self.state.filtered):
                if (
                    row.kind == "tool"
                    and str(getattr(row.tool, "name", "")).strip().lower() == key
                ):
                    self.state.index = i
                    break
            else:
                self.state.index = first_selectable_index(self.state.filtered)
        else:
            self.state.index = first_selectable_index(self.state.filtered)
        self.state.scroll = 0

    def _on_search_text(self, _buf) -> None:
        if not self.state.open:
            return
        self.state.query = self.search_buf.text
        cur = self._current()
        keep = str(getattr(cur, "name", "") or "") if cur else None
        self._rebuild_rows(keep_name=keep)
        self._invalidate()

    def _current(self) -> Any | None:
        rows = self.state.filtered
        if not rows:
            return None
        row = rows[max(0, min(self.state.index, len(rows) - 1))]
        return row.tool if row.kind == "tool" else None

    def _move(self, delta: int) -> None:
        rows = self.state.filtered
        if not rows:
            return
        n = len(rows)
        i = self.state.index
        for _ in range(n):
            i = (i + delta) % n
            if rows[i].kind == "tool":
                self.state.index = i
                self._invalidate()
                return

    def _scroll_by(self, delta: int) -> None:
        rows = self.state.filtered
        if not rows:
            return
        vh = max(1, int(getattr(self, "_list_viewport_h", LIST_HEIGHT) or LIST_HEIGHT))
        max_scroll = max(0, len(rows) - vh)
        nxt = max(0, min(max_scroll, self.state.scroll + delta))
        if nxt == self.state.scroll:
            return
        self.state.scroll = nxt
        if self.state.index < self.state.scroll:
            self.state.index = first_selectable_index(rows, self.state.scroll)
        elif self.state.index >= self.state.scroll + vh:
            self.state.index = first_selectable_index(rows, self.state.scroll + vh - 1)
        self._invalidate()

    def _move_to(self, idx: int) -> None:
        rows = self.state.filtered
        if not rows or idx < 0 or idx >= len(rows) or rows[idx].kind != "tool":
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
        self.state = _ToolsModalState(tools=collect_tools_for_modal(), open=True)
        self.search_buf.reset()
        self._rebuild_rows()
        try:
            self.app.layout.focus(self.search_buf)
        except Exception:  # noqa: BLE001
            pass
        self._invalidate()

    def confirm(self) -> None:
        self.cancel()

    def cancel(self) -> None:
        if not self.state.open:
            return
        self.state.open = False
        self._on_style_refresh()
        self._focus_compose()
        self._invalidate()


def run_tools_modal(terminal: Any) -> bool:
    import os
    import sys

    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    host = getattr(terminal, "_tools_modal_host", None)
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
        styles.update(tools_modal_style_extras(colors))
        styles = dim_transcript_styles_for_backdrop(styles)
        nested.style = Style.from_dict(styles)
        try:
            nested.invalidate()
        except Exception:  # noqa: BLE001
            pass

    canvas = Window(char=" ", style="class:tools-dialog")
    root = FloatContainer(content=canvas, floats=[])
    nested_app = Application(
        layout=Layout(root),
        key_bindings=KeyBindings(),
        full_screen=True,
        mouse_support=True,
        color_depth=ColorDepth.TRUE_COLOR,
    )
    held["app"] = nested_app
    host = ToolsModalHost(
        terminal, app=nested_app, on_style_refresh=_refresh, focus_compose=lambda: None
    )
    root.floats.extend(host.floats)
    nested_app.key_bindings = merge_key_bindings([host.key_bindings])
    _refresh()
    original_cancel = host.cancel

    def _cancel_and_exit():
        original_cancel()
        if nested_app.is_running:
            nested_app.exit(result=False)

    host.cancel = _cancel_and_exit  # type: ignore[method-assign]
    host.confirm = _cancel_and_exit  # type: ignore[method-assign]
    host.open()
    try:
        return bool(nested_app.run())
    except Exception:  # noqa: BLE001
        return False
