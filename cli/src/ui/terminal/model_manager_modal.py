"""In-app /model-manager modal: list/activate compatible profiles; CRUD via host."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from ui.terminal.themes_modal import (
    dim_transcript_styles_for_backdrop,
    themes_modal_style_extras,
)

DIALOG_WIDTH = 72
PAD_X = 3
LIST_HEIGHT = 20
DIALOG_HEIGHT = 8 + LIST_HEIGHT


@dataclass
class _ProfileRow:
    kind: str  # "header" | "profile" | "action"
    title: str
    profile_id: str = ""
    meta: str = ""
    search: str = ""
    action: str = ""  # add | edit | delete
    active: bool = False


@dataclass
class _ModelManagerModalState:
    rows: list[_ProfileRow] = field(default_factory=list)
    filtered: list[_ProfileRow] = field(default_factory=list)
    index: int = 0
    query: str = ""
    open: bool = False
    scroll: int = 0
    status: str = ""
    confirm_delete_id: str = ""


def model_manager_modal_style_extras(colors: dict[str, str]) -> dict[str, str]:
    base = themes_modal_style_extras(colors)
    out = {k.replace("themes-", "mm-", 1): v for k, v in base.items()}
    muted = colors["muted_fg"]
    panel = colors["panel_bg"]
    accent = colors["accent"]
    out["mm-section"] = f"bg:{panel} {accent} bold"
    out["mm-meta"] = f"bg:{panel} {muted}"
    out["mm-meta-selected"] = out.get("mm-row-selected", f"bg:{accent} bold")
    return out


def collect_profile_rows(terminal: Any, *, query: str = "") -> list[_ProfileRow]:
    from agent.config import Config

    cfg = getattr(getattr(terminal, "session", None), "config", None) or Config.load()
    profiles = cfg.openai_profiles(include_cloud=False)
    active_id = str(cfg.get("llm.openai_active_profile") or "").strip()
    rows: list[_ProfileRow] = [
        _ProfileRow(kind="header", title="Compatible profiles", search="profiles")
    ]
    for profile_id, profile in sorted(
        profiles.items(),
        key=lambda item: str(item[1].get("label") or item[0]).strip().lower(),
    ):
        label = str(profile.get("label") or profile_id).strip()
        backend = str(profile.get("backend") or "other").strip().lower() or "other"
        endpoint = str(profile.get("base_url") or "").strip() or "—"
        display_backend = backend
        try:
            display_backend = terminal._compatible_backend_display_name(backend)
        except Exception:  # noqa: BLE001
            pass
        meta = f"{display_backend} · {endpoint}"
        rows.append(
            _ProfileRow(
                kind="profile",
                title=label,
                profile_id=str(profile_id),
                meta=meta,
                search=f"{label} {profile_id} {backend} {endpoint}".lower(),
                active=str(profile_id) == active_id,
            )
        )
    rows.append(_ProfileRow(kind="header", title="Actions", search="actions"))
    rows.append(
        _ProfileRow(
            kind="action",
            title="Add compatible profile",
            action="add",
            search="add create new profile",
        )
    )
    rows.append(
        _ProfileRow(
            kind="action",
            title="Edit selected profile",
            action="edit",
            search="edit update profile",
        )
    )
    rows.append(
        _ProfileRow(
            kind="action",
            title="Delete selected profile",
            action="delete",
            search="delete remove profile",
        )
    )
    q = (query or "").strip().lower()
    if not q:
        return rows
    out: list[_ProfileRow] = []
    pending: _ProfileRow | None = None
    for row in rows:
        if row.kind == "header":
            pending = row
            continue
        if q in row.search or q in row.title.lower() or q in row.meta.lower():
            if pending is not None and (
                not out or out[-1].kind != "header" or out[-1].title != pending.title
            ):
                out.append(pending)
            out.append(row)
    return out


def first_selectable_index(rows: list[_ProfileRow], start: int = 0) -> int:
    if not rows:
        return 0
    n = len(rows)
    i = max(0, min(start, n - 1))
    for _ in range(n):
        if rows[i].kind in {"profile", "action"}:
            return i
        i = (i + 1) % n
    return 0


class ModelManagerModalHost:
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
        self.state = _ModelManagerModalState()
        self.search_buf = Buffer(name="mm-search", multiline=False)
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
                        return [("class:mm-row", " " * width)]
                    row = rows[abs_i]
                    inset = " " * PAD_X
                    if row.kind == "header":
                        label = f"{inset}{row.title}"
                        pad = " " * max(0, width - len(label))
                        return [("class:mm-section", f"{label}{pad}")]
                    selected = abs_i == st.index
                    style = "class:mm-row-selected" if selected else "class:mm-row"
                    meta_style = (
                        "class:mm-meta-selected" if selected else "class:mm-meta"
                    )
                    mark = "●" if row.active else ("›" if row.kind == "action" else " ")
                    prefix = f"{inset}{mark} "
                    right = f"{row.meta}{inset}" if row.meta else inset
                    room = max(1, width - len(prefix) - len(right))
                    title = row.title
                    if len(title) > room:
                        title = title[: room - 1] + "…"
                    pad = " " * max(0, width - len(prefix) - len(title) - len(right))
                    return [
                        (style, prefix + title),
                        (style, pad),
                        (meta_style, right),
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
                width=PAD_X, char=" ", style="class:mm-dialog", dont_extend_width=True
            )

        list_window = Window(
            content=_ListControl(),
            height=Dimension.exact(LIST_HEIGHT),
            style="class:mm-dialog",
        )
        header = VSplit(
            [
                _side_pad(),
                Window(
                    content=FormattedTextControl(
                        lambda: [("class:mm-title", "Model Manager")]
                    ),
                    dont_extend_width=True,
                    style="class:mm-dialog",
                ),
                Window(char=" ", style="class:mm-dialog"),
                Window(
                    content=FormattedTextControl(lambda: [("class:mm-hint", "esc")]),
                    width=3,
                    style="class:mm-dialog",
                ),
                _side_pad(),
            ],
            height=1,
            style="class:mm-dialog",
        )
        search = VSplit(
            [
                _side_pad(),
                Window(
                    width=7,
                    content=FormattedTextControl(
                        lambda: [("class:mm-search.prompt", "Search ")]
                    ),
                    style="class:mm-search",
                ),
                Window(
                    content=BufferControl(buffer=self.search_buf, focusable=True),
                    height=1,
                    style="class:mm-search",
                ),
                _side_pad(),
            ],
            height=1,
            style="class:mm-search",
        )
        status = VSplit(
            [
                _side_pad(),
                Window(
                    content=FormattedTextControl(
                        lambda: [
                            ("class:mm-preview-accent", "┃"),
                            (
                                "class:mm-preview-panel",
                                f" {host.state.status or 'Enter activates · CRUD via action rows'}",
                            ),
                        ]
                    ),
                    height=1,
                    style="class:mm-preview",
                ),
                _side_pad(),
            ],
            height=1,
            style="class:mm-preview",
        )
        hints = VSplit(
            [
                _side_pad(),
                Window(
                    content=FormattedTextControl(
                        lambda: [
                            (
                                "class:mm-hint",
                                "↑/↓ · enter · ctrl+a add · ctrl+e edit · ctrl+d delete",
                            )
                        ]
                    ),
                    height=1,
                    style="class:mm-dialog",
                ),
                _side_pad(),
            ],
            height=1,
            style="class:mm-dialog",
        )
        dialog = HSplit(
            [
                Window(height=1, char=" ", style="class:mm-dialog"),
                header,
                search,
                Window(height=1, char=" ", style="class:mm-dialog"),
                list_window,
                Window(height=1, char=" ", style="class:mm-dialog"),
                status,
                hints,
                Window(height=1, char=" ", style="class:mm-dialog"),
            ],
            width=Dimension.exact(DIALOG_WIDTH),
            height=Dimension.exact(DIALOG_HEIGHT),
            style="class:mm-dialog",
        )
        with_shadow = HSplit(
            [
                VSplit(
                    [
                        dialog,
                        Window(width=1, char=" ", style="class:mm-shadow"),
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
                            style="class:mm-shadow",
                        ),
                    ],
                    height=1,
                ),
            ],
            width=Dimension.exact(DIALOG_WIDTH + 1),
            height=Dimension.exact(DIALOG_HEIGHT + 1),
            style="class:mm-dialog",
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

        @self.key_bindings.add("enter", filter=self.is_open, eager=True)
        def _enter(_e):
            host.confirm()

        @self.key_bindings.add("c-a", filter=self.is_open, eager=True)
        def _add(_e):
            host.run_action("add")

        @self.key_bindings.add("c-e", filter=self.is_open, eager=True)
        def _edit(_e):
            host.run_action("edit")

        @self.key_bindings.add("c-d", filter=self.is_open, eager=True)
        def _del(_e):
            host.run_action("delete")

        @self.key_bindings.add("escape", filter=self.is_open, eager=True)
        @self.key_bindings.add("c-c", filter=self.is_open, eager=True)
        def _esc(_e):
            if host.state.confirm_delete_id:
                host.state.confirm_delete_id = ""
                host.state.status = "Delete cancelled"
                host._invalidate()
                return
            host.cancel()

    def _rebuild_rows(self, *, keep: str | None = None) -> None:
        self.state.rows = collect_profile_rows(self.terminal, query=self.state.query)
        self.state.filtered = list(self.state.rows)
        if keep:
            for i, row in enumerate(self.state.filtered):
                if row.profile_id == keep or row.action == keep:
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
        keep = (cur.profile_id or cur.action) if cur else None
        self._rebuild_rows(keep=keep)
        self._invalidate()

    def _current(self) -> _ProfileRow | None:
        rows = self.state.filtered
        if not rows:
            return None
        row = rows[max(0, min(self.state.index, len(rows) - 1))]
        if row.kind in {"profile", "action"}:
            return row
        return None

    def _selected_profile_id(self) -> str:
        # Prefer highlighted profile; else last profile above actions.
        row = self._current()
        if row is not None and row.kind == "profile" and row.profile_id:
            return row.profile_id
        for r in reversed(self.state.filtered[: self.state.index + 1]):
            if r.kind == "profile" and r.profile_id:
                return r.profile_id
        for r in self.state.filtered:
            if r.kind == "profile" and r.profile_id:
                return r.profile_id
        return ""

    def _move(self, delta: int) -> None:
        rows = self.state.filtered
        if not rows:
            return
        n = len(rows)
        i = self.state.index
        for _ in range(n):
            i = (i + delta) % n
            if rows[i].kind in {"profile", "action"}:
                self.state.index = i
                self._invalidate()
                return

    def _move_to(self, idx: int) -> None:
        rows = self.state.filtered
        if not rows or idx < 0 or idx >= len(rows):
            return
        if rows[idx].kind not in {"profile", "action"}:
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
        self.state = _ModelManagerModalState(open=True)
        self.search_buf.reset()
        self._rebuild_rows()
        try:
            self.app.layout.focus(self.search_buf)
        except Exception:  # noqa: BLE001
            pass
        self._invalidate()

    def _close(self) -> None:
        self.state.open = False
        self._on_style_refresh()
        self._focus_compose()
        self._invalidate()

    def run_action(self, action: str) -> None:
        from agent.config import Config

        if action == "add":
            self._close()
            create = getattr(self.terminal, "_create_or_edit_compatible_profile", None)
            schedule = getattr(self.terminal, "_schedule_host_terminal", None)
            if callable(create) and callable(schedule):
                schedule(create)
            elif callable(create):
                create()
            return
        if action == "edit":
            pid = self._selected_profile_id()
            if not pid:
                self.state.status = "Select a profile to edit"
                self._invalidate()
                return
            self._close()
            create = getattr(self.terminal, "_create_or_edit_compatible_profile", None)
            schedule = getattr(self.terminal, "_schedule_host_terminal", None)
            if callable(create) and callable(schedule):
                schedule(create, profile_id=pid)
            elif callable(create):
                create(profile_id=pid)
            return
        if action == "delete":
            pid = self._selected_profile_id()
            if not pid:
                self.state.status = "Select a profile to delete"
                self._invalidate()
                return
            if self.state.confirm_delete_id != pid:
                self.state.confirm_delete_id = pid
                self.state.status = f"Enter again to delete {pid}"
                self._invalidate()
                return
            cfg = getattr(getattr(self.terminal, "session", None), "config", None) or Config.load()
            if not cfg.remove_openai_profile(pid):
                self.state.status = "Profile could not be deleted"
                self.state.confirm_delete_id = ""
                self._invalidate()
                return
            cfg.save()
            sess = getattr(self.terminal, "session", None)
            if sess is not None:
                sess.config = cfg
            self.state.confirm_delete_id = ""
            self.state.status = f"Deleted {pid}"
            self._rebuild_rows()
            self._invalidate()

    def confirm(self) -> None:
        from agent.config import Config

        row = self._current()
        if not self.state.open or row is None:
            return
        if row.kind == "action":
            self.run_action(row.action)
            return
        if self.state.confirm_delete_id:
            self.run_action("delete")
            return
        pid = row.profile_id
        if not pid:
            return
        cfg = getattr(getattr(self.terminal, "session", None), "config", None) or Config.load()
        try:
            cfg.set_openai_active_profile(pid)
        except ValueError as exc:
            self.state.status = str(exc)
            self._invalidate()
            return
        cfg.save()
        sess = getattr(self.terminal, "session", None)
        if sess is not None:
            sess.config = cfg
        self.state.status = f"Active → {pid}"
        self._rebuild_rows(keep=pid)
        self._invalidate()

    def cancel(self) -> None:
        if not self.state.open:
            return
        self._close()


def run_model_manager_modal(terminal: Any) -> bool:
    import os
    import sys

    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    host = getattr(terminal, "_model_manager_modal_host", None)
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
        styles.update(model_manager_modal_style_extras(colors))
        styles = dim_transcript_styles_for_backdrop(styles)
        nested.style = Style.from_dict(styles)
        try:
            nested.invalidate()
        except Exception:  # noqa: BLE001
            pass

    canvas = Window(char=" ", style="class:mm-dialog")
    root = FloatContainer(content=canvas, floats=[])
    nested_app = Application(
        layout=Layout(root),
        key_bindings=KeyBindings(),
        full_screen=True,
        mouse_support=True,
        color_depth=ColorDepth.TRUE_COLOR,
    )
    held["app"] = nested_app
    host = ModelManagerModalHost(
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
    host.open()
    try:
        return bool(nested_app.run())
    except Exception:  # noqa: BLE001
        return False
