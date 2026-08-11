"""In-app /specialist modal: search, Enter/click select, None clears."""

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
LIST_HEIGHT = 24
DIALOG_HEIGHT = 8 + LIST_HEIGHT


@dataclass
class _SpecialistRow:
    kind: str  # "header" | "none" | "specialist"
    title: str
    slug: str = ""
    specialist: Any | None = None
    search: str = ""
    description: str = ""
    meta: str = ""
    active: bool = False


@dataclass
class _SpecialistModalState:
    specialists: list[Any] = field(default_factory=list)
    rows: list[_SpecialistRow] = field(default_factory=list)
    filtered: list[_SpecialistRow] = field(default_factory=list)
    index: int = 0
    query: str = ""
    open: bool = False
    scroll: int = 0
    active_id: str = ""
    status: str = ""


def lean_description(text: str, *, max_len: int = 48) -> str:
    one = " ".join((text or "").split())
    if len(one) <= max_len:
        return one
    return one[: max_len - 1] + "…"


def specialist_meta(item: Any) -> str:
    skills = len(getattr(item, "skill_names", None) or [])
    mcps = len(getattr(item, "mcp_server_ids", None) or []) + len(
        getattr(item, "mcp_catalog_ids", None) or []
    )
    return f"{skills} skills · {mcps} mcps"


def collect_specialists_for_modal() -> tuple[list[Any], str]:
    from agent.specialists_manage import get_active_specialist
    from agent_server.store import AgentStore

    store = AgentStore()
    items = list(store.list_specialists())
    items.sort(key=lambda s: str(getattr(s, "name", "") or "").lower())
    active = get_active_specialist(store=store)
    active_id = str(getattr(active, "id", "") or "") if active else ""
    return items, active_id


def build_specialist_rows(
    specialists: list[Any],
    *,
    active_id: str = "",
    query: str = "",
) -> list[_SpecialistRow]:
    q = (query or "").strip().lower()
    none_active = not active_id
    none_row = _SpecialistRow(
        kind="none",
        title="None (global skills / MCPs)",
        search="none clear no specialist global",
        description="No specialist selected",
        meta="clear",
        active=none_active,
    )
    rows: list[_SpecialistRow] = [
        _SpecialistRow(kind="header", title="Active specialist", search="active"),
    ]
    if not q or q in none_row.search:
        rows.append(none_row)

    matched: list[Any] = []
    for item in specialists:
        name = str(getattr(item, "name", "") or "")
        slug = str(getattr(item, "slug", "") or "")
        desc = str(getattr(item, "description", "") or "")
        blob = f"{name} {slug} {desc} {specialist_meta(item)}".lower()
        if q and q not in blob:
            continue
        matched.append(item)

    if matched:
        rows.append(
            _SpecialistRow(kind="header", title="Specialists", search="specialists")
        )
        for item in matched:
            sid = str(getattr(item, "id", "") or "")
            name = str(getattr(item, "name", "") or "")
            slug = str(getattr(item, "slug", "") or "")
            desc = lean_description(str(getattr(item, "description", "") or ""))
            meta = specialist_meta(item)
            rows.append(
                _SpecialistRow(
                    kind="specialist",
                    title=name,
                    slug=slug,
                    specialist=item,
                    search=f"{name} {slug} {desc} {meta}",
                    description=desc or slug,
                    meta=meta,
                    active=bool(active_id and sid == active_id),
                )
            )
    return rows


def first_selectable_index(rows: list[_SpecialistRow], start: int = 0) -> int:
    if not rows:
        return 0
    n = len(rows)
    i = max(0, min(start, n - 1))
    for _ in range(n):
        if rows[i].kind in {"none", "specialist"}:
            return i
        i = (i + 1) % n
    return 0


def specialist_modal_style_extras(colors: dict[str, str]) -> dict[str, str]:
    base = themes_modal_style_extras(colors)
    out = {k.replace("themes-", "specialist-", 1): v for k, v in base.items()}
    muted = colors["muted_fg"]
    panel = colors["panel_bg"]
    accent = colors["accent"]
    out["specialist-section"] = f"bg:{panel} {accent} bold"
    out["specialist-meta"] = f"bg:{panel} {muted}"
    out["specialist-meta-selected"] = out.get(
        "specialist-row-selected", f"bg:{accent} bold"
    )
    out["specialist-desc"] = f"bg:{panel} {muted}"
    out["specialist-desc-selected"] = out.get(
        "specialist-row-selected", f"bg:{accent} bold"
    )
    return out


def apply_specialist_selection(terminal: Any, row: _SpecialistRow) -> str:
    from agent.specialists_manage import set_active_specialist_ref

    if row.kind == "none":
        set_active_specialist_ref(None)
        refresh = getattr(terminal, "_refresh_cli_specialist_label", None)
        if callable(refresh):
            refresh()
        return "Cleared active specialist"
    if row.kind == "specialist" and row.specialist is not None:
        item = row.specialist
        if getattr(item, "enabled", True) is False:
            return f"Disabled: {item.name}"
        slug = str(getattr(item, "slug", "") or "").strip()
        if not slug:
            return "Missing slug"
        set_active_specialist_ref(slug)
        refresh = getattr(terminal, "_refresh_cli_specialist_label", None)
        if callable(refresh):
            refresh()
        return f"Active → {item.name}"
    return ""


class SpecialistModalHost:
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
        self.state = _SpecialistModalState()
        self._list_viewport_h = LIST_HEIGHT
        self.search_buf = Buffer(name="specialist-search", multiline=False)
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
                        return [("class:specialist-row", " " * width)]
                    row = rows[abs_i]
                    inset = " " * PAD_X
                    if row.kind == "header":
                        label = f"{inset}{row.title}"
                        pad = " " * max(0, width - len(label))
                        return [("class:specialist-section", f"{label}{pad}")]
                    selected = abs_i == st.index
                    style = (
                        "class:specialist-row-selected"
                        if selected
                        else "class:specialist-row"
                    )
                    gutter_style = (
                        "class:specialist-row-selected"
                        if selected
                        else "class:specialist-row-current"
                    )
                    desc_style = (
                        "class:specialist-desc-selected"
                        if selected
                        else "class:specialist-desc"
                    )
                    right_style = (
                        "class:specialist-meta-selected"
                        if selected
                        else "class:specialist-meta"
                    )
                    gutter = "●" if row.active else "○"
                    prefix = f"{inset}{gutter} "
                    right = f"{row.meta}{inset}" if row.meta else inset
                    room = max(1, width - len(prefix) - len(right))
                    title = row.title
                    title_budget = min(len(title), max(10, room // 2))
                    if len(title) > title_budget:
                        title = title[: title_budget - 1] + "…"
                    rest = room - len(title)
                    desc = ""
                    if row.description and rest > 4:
                        desc = f"  {row.description}"
                        if len(desc) > rest:
                            desc = desc[: rest - 1] + "…"
                    pad = " " * max(
                        0, width - len(prefix) - len(title) - len(desc) - len(right)
                    )
                    return [
                        (gutter_style, prefix),
                        (style, title),
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
                width=PAD_X,
                char=" ",
                style="class:specialist-dialog",
                dont_extend_width=True,
            )

        list_window = Window(
            content=_ListControl(),
            height=Dimension.exact(LIST_HEIGHT),
            style="class:specialist-dialog",
        )
        header = VSplit(
            [
                _side_pad(),
                Window(
                    content=FormattedTextControl(
                        lambda: [("class:specialist-title", "Specialists")]
                    ),
                    dont_extend_width=True,
                    style="class:specialist-dialog",
                ),
                Window(char=" ", style="class:specialist-dialog"),
                Window(
                    content=FormattedTextControl(
                        lambda: [("class:specialist-hint", "esc")]
                    ),
                    width=3,
                    style="class:specialist-dialog",
                ),
                _side_pad(),
            ],
            height=1,
            style="class:specialist-dialog",
        )
        search = VSplit(
            [
                _side_pad(),
                Window(
                    width=7,
                    content=FormattedTextControl(
                        lambda: [("class:specialist-search.prompt", "Search ")]
                    ),
                    style="class:specialist-search",
                ),
                Window(
                    content=BufferControl(buffer=self.search_buf, focusable=True),
                    height=1,
                    style="class:specialist-search",
                ),
                _side_pad(),
            ],
            height=1,
            style="class:specialist-search",
        )
        status = VSplit(
            [
                _side_pad(),
                Window(
                    content=FormattedTextControl(self._status_strip),
                    height=1,
                    style="class:specialist-preview",
                ),
                _side_pad(),
            ],
            height=1,
            style="class:specialist-preview",
        )
        hints = VSplit(
            [
                _side_pad(),
                Window(
                    content=FormattedTextControl(
                        lambda: [
                            (
                                "class:specialist-hint",
                                "↑/↓ · enter/click select · None clears · esc",
                            )
                        ]
                    ),
                    height=1,
                    style="class:specialist-dialog",
                ),
                _side_pad(),
            ],
            height=1,
            style="class:specialist-dialog",
        )
        dialog = HSplit(
            [
                Window(height=1, char=" ", style="class:specialist-dialog"),
                header,
                search,
                Window(height=1, char=" ", style="class:specialist-dialog"),
                list_window,
                Window(height=1, char=" ", style="class:specialist-dialog"),
                status,
                hints,
                Window(height=1, char=" ", style="class:specialist-dialog"),
            ],
            width=Dimension.exact(DIALOG_WIDTH),
            height=Dimension.exact(DIALOG_HEIGHT),
            style="class:specialist-dialog",
        )
        with_shadow = HSplit(
            [
                VSplit(
                    [
                        dialog,
                        Window(width=1, char=" ", style="class:specialist-shadow"),
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
                            style="class:specialist-shadow",
                        ),
                    ],
                    height=1,
                ),
            ],
            width=Dimension.exact(DIALOG_WIDTH + 1),
            height=Dimension.exact(DIALOG_HEIGHT + 1),
            style="class:specialist-dialog",
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

    def _status_strip(self):
        text = self.state.status
        if not text:
            n = len(self.state.specialists)
            text = f"{n} specialist{'s' if n != 1 else ''} · Enter selects"
        max_len = max(12, DIALOG_WIDTH - PAD_X * 2 - 4)
        if len(text) > max_len:
            text = text[: max_len - 1] + "…"
        return [
            ("class:specialist-preview-accent", "┃"),
            ("class:specialist-preview-panel", f" {text}"),
        ]

    def _rebuild_rows(self, *, prefer_active: bool = False) -> None:
        self.state.rows = build_specialist_rows(
            self.state.specialists,
            active_id=self.state.active_id,
            query=self.state.query,
        )
        self.state.filtered = list(self.state.rows)
        if prefer_active:
            for i, row in enumerate(self.state.filtered):
                if row.active and row.kind in {"none", "specialist"}:
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
        self._rebuild_rows()
        self._invalidate()

    def _current(self) -> _SpecialistRow | None:
        rows = self.state.filtered
        if not rows:
            return None
        row = rows[max(0, min(self.state.index, len(rows) - 1))]
        if row.kind in {"none", "specialist"}:
            return row
        return None

    def _move(self, delta: int) -> None:
        rows = self.state.filtered
        if not rows:
            return
        n = len(rows)
        i = self.state.index
        for _ in range(n):
            i = (i + delta) % n
            if rows[i].kind in {"none", "specialist"}:
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
        if not rows or idx < 0 or idx >= len(rows):
            return
        if rows[idx].kind not in {"none", "specialist"}:
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
        items, active_id = collect_specialists_for_modal()
        self.state = _SpecialistModalState(
            specialists=items, active_id=active_id, open=True
        )
        self.search_buf.reset()
        self._rebuild_rows(prefer_active=True)
        try:
            self.app.layout.focus(self.search_buf)
        except Exception:  # noqa: BLE001
            pass
        self._invalidate()

    def confirm(self) -> None:
        row = self._current()
        if not self.state.open or row is None:
            return
        msg = apply_specialist_selection(self.terminal, row)
        self.state.open = False
        self._on_style_refresh()
        self._focus_compose()
        self._invalidate()
        console = getattr(self.terminal, "console", None)
        if console is not None and msg:
            if msg.startswith("Cleared"):
                console.print("  [green]Cleared active specialist.[/green] Using global skills/MCPs.")
            elif msg.startswith("Active"):
                console.print(f"  [green]{msg}[/green]")
            elif msg.startswith("Disabled"):
                console.print(f"  [yellow]{msg}[/yellow]")
            else:
                console.print(f"  [dim]{msg}[/dim]")

    def cancel(self) -> None:
        if not self.state.open:
            return
        self.state.open = False
        self._on_style_refresh()
        self._focus_compose()
        self._invalidate()


def run_specialist_modal(terminal: Any) -> bool:
    import os
    import sys

    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    host = getattr(terminal, "_specialist_modal_host", None)
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
        styles.update(specialist_modal_style_extras(colors))
        styles = dim_transcript_styles_for_backdrop(styles)
        nested.style = Style.from_dict(styles)
        try:
            nested.invalidate()
        except Exception:  # noqa: BLE001
            pass

    canvas = Window(char=" ", style="class:specialist-dialog")
    root = FloatContainer(content=canvas, floats=[])
    nested_app = Application(
        layout=Layout(root),
        key_bindings=KeyBindings(),
        full_screen=True,
        mouse_support=True,
        color_depth=ColorDepth.TRUE_COLOR,
    )
    held["app"] = nested_app
    host = SpecialistModalHost(
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
