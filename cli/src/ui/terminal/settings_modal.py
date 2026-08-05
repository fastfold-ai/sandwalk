"""In-app /settings modal: cycle toggles over the live transcript."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from ui.terminal.themes_modal import (
    dim_transcript_styles_for_backdrop,
    themes_modal_style_extras,
)

DIALOG_WIDTH = 64
PAD_X = 3
LIST_HEIGHT = 12
DIALOG_HEIGHT = 8 + LIST_HEIGHT


@dataclass
class _SettingsRow:
    kind: str  # "header" | "setting"
    key: str
    title: str
    value: str = ""
    search: str = ""


@dataclass
class _SettingsModalState:
    rows: list[_SettingsRow] = field(default_factory=list)
    filtered: list[_SettingsRow] = field(default_factory=list)
    index: int = 0
    query: str = ""
    open: bool = False
    scroll: int = 0
    status: str = ""


def settings_modal_style_extras(colors: dict[str, str]) -> dict[str, str]:
    base = themes_modal_style_extras(colors)
    out = {k.replace("themes-", "settings-", 1): v for k, v in base.items()}
    muted = colors["muted_fg"]
    panel = colors["panel_bg"]
    accent = colors["accent"]
    out["settings-section"] = f"bg:{panel} {accent} bold"
    out["settings-meta"] = f"bg:{panel} {muted}"
    out["settings-meta-selected"] = out.get(
        "settings-row-selected", f"bg:{accent} bold"
    )
    return out


def _current_settings_snapshot() -> dict[str, str]:
    from agent.config import Config
    from ui.status import SPINNERS

    cfg = Config.load()
    spinner = str(cfg.get("ui.spinner") or "dna_helix")
    if spinner not in SPINNERS:
        spinner = next(iter(SPINNERS.keys()), spinner)
    profile = str(cfg.get("agent.profile") or "research")
    auto_html = bool(cfg.get("output.auto_publish_html_interactive", True))
    return {
        "spinner": spinner,
        "profile": profile,
        "auto_publish": "Yes" if auto_html else "No",
    }


def build_settings_rows(*, query: str = "") -> list[_SettingsRow]:
    snap = _current_settings_snapshot()
    rows = [
        _SettingsRow(kind="header", key="", title="Preferences", search="preferences"),
        _SettingsRow(
            kind="setting",
            key="spinner",
            title="UI Loading Spinner",
            value=snap["spinner"],
            search=f"spinner ui loading {snap['spinner']}",
        ),
        _SettingsRow(
            kind="setting",
            key="profile",
            title="Agent Profile",
            value=snap["profile"],
            search=f"agent profile research enterprise pharma {snap['profile']}",
        ),
        _SettingsRow(
            kind="setting",
            key="auto_publish",
            title="Auto-publish HTML Reports",
            value=snap["auto_publish"],
            search=f"auto publish html reports {snap['auto_publish']}",
        ),
        _SettingsRow(
            kind="setting",
            key="openai_profiles",
            title="OpenAI-compatible Profiles",
            value="Manage…",
            search="openai compatible profiles model-manager",
        ),
    ]
    q = (query or "").strip().lower()
    if not q:
        return rows
    out: list[_SettingsRow] = []
    pending_header: _SettingsRow | None = None
    for row in rows:
        if row.kind == "header":
            pending_header = row
            continue
        blob = f"{row.title} {row.value} {row.search}".lower()
        if q in blob:
            if pending_header is not None and (
                not out or out[-1].kind != "header" or out[-1].title != pending_header.title
            ):
                out.append(pending_header)
            out.append(row)
    return out


def first_selectable_index(rows: list[_SettingsRow], start: int = 0) -> int:
    if not rows:
        return 0
    n = len(rows)
    i = max(0, min(start, n - 1))
    for _ in range(n):
        if rows[i].kind == "setting":
            return i
        i = (i + 1) % n
    return 0


def cycle_spinner(current: str) -> str:
    from ui.status import SPINNERS

    keys = list(SPINNERS.keys())
    if not keys:
        return current
    try:
        idx = keys.index(current)
    except ValueError:
        return keys[0]
    return keys[(idx + 1) % len(keys)]


def cycle_profile(current: str) -> str:
    from agent.config import AGENT_PROFILE_PRESETS

    keys = list(AGENT_PROFILE_PRESETS.keys())
    if not keys:
        return current
    try:
        idx = keys.index(current)
    except ValueError:
        return keys[0]
    return keys[(idx + 1) % len(keys)]


def apply_setting_action(key: str) -> str | None:
    """Apply Enter on a settings row. Returns status text, or ``openai_profiles`` sentinel."""
    from agent.config import Config

    if key == "openai_profiles":
        return "openai_profiles"

    cfg = Config.load()
    if key == "spinner":
        current = str(cfg.get("ui.spinner") or "dna_helix")
        nxt = cycle_spinner(current)
        cfg.set("ui.spinner", nxt)
        cfg.save()
        return f"Spinner → {nxt}"
    if key == "profile":
        current = str(cfg.get("agent.profile") or "research")
        nxt = cycle_profile(current)
        cfg.set("agent.profile", nxt)
        cfg.save()
        return f"Profile → {nxt}"
    if key == "auto_publish":
        current = bool(cfg.get("output.auto_publish_html_interactive", True))
        nxt = not current
        cfg.set("output.auto_publish_html_interactive", nxt)
        cfg.save()
        return f"Auto-publish HTML → {'Yes' if nxt else 'No'}"
    return None


class SettingsModalHost:
    """In-app settings overlay hosted by the transcript FloatContainer."""

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
        self.state = _SettingsModalState()
        self._list_viewport_h = LIST_HEIGHT
        self.search_buf = Buffer(name="settings-search", multiline=False)
        self.search_buf.on_text_changed += self._on_search_text

        host = self
        self.is_open = Condition(lambda: host.state.open)

        class _SettingsListControl(UIControl):
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
                        return [("class:settings-row", " " * width)]
                    row = rows[abs_i]
                    inset = " " * PAD_X
                    if row.kind == "header":
                        label = f"{inset}{row.title}"
                        pad = " " * max(0, width - len(label))
                        return [("class:settings-section", f"{label}{pad}")]
                    selected = abs_i == st.index
                    style = (
                        "class:settings-row-selected"
                        if selected
                        else "class:settings-row"
                    )
                    right_style = (
                        "class:settings-meta-selected"
                        if selected
                        else "class:settings-meta"
                    )
                    right = f"{row.value}{inset}" if row.value else inset
                    prefix = f"{inset}"
                    room = max(1, width - len(prefix) - len(right))
                    title = row.title
                    if len(title) > room:
                        title = title[: room - 1] + "…"
                    pad = " " * max(0, width - len(prefix) - len(title) - len(right))
                    return [
                        (style, prefix + title),
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

        list_window = Window(
            content=_SettingsListControl(),
            height=Dimension.exact(LIST_HEIGHT),
            dont_extend_height=True,
            style="class:settings-dialog",
        )

        def _side_pad():
            return Window(
                width=PAD_X,
                char=" ",
                style="class:settings-dialog",
                dont_extend_width=True,
            )

        header = VSplit(
            [
                _side_pad(),
                Window(
                    content=FormattedTextControl(
                        lambda: [("class:settings-title", "Settings")]
                    ),
                    dont_extend_width=True,
                    style="class:settings-dialog",
                ),
                Window(char=" ", style="class:settings-dialog"),
                Window(
                    content=FormattedTextControl(
                        lambda: [("class:settings-hint", "esc")]
                    ),
                    width=3,
                    dont_extend_width=True,
                    style="class:settings-dialog",
                ),
                _side_pad(),
            ],
            height=1,
            style="class:settings-dialog",
        )

        search = VSplit(
            [
                _side_pad(),
                Window(
                    width=7,
                    content=FormattedTextControl(
                        lambda: [("class:settings-search.prompt", "Search ")]
                    ),
                    style="class:settings-search",
                ),
                Window(
                    content=BufferControl(buffer=self.search_buf, focusable=True),
                    height=1,
                    style="class:settings-search",
                ),
                _side_pad(),
            ],
            height=1,
            style="class:settings-search",
        )

        status = VSplit(
            [
                _side_pad(),
                Window(
                    content=FormattedTextControl(self._status_strip),
                    height=1,
                    style="class:settings-preview",
                ),
                _side_pad(),
            ],
            height=1,
            style="class:settings-preview",
        )

        hints = VSplit(
            [
                _side_pad(),
                Window(
                    content=FormattedTextControl(
                        lambda: [
                            (
                                "class:settings-hint",
                                "↑/↓ · enter cycle/open · esc",
                            )
                        ]
                    ),
                    height=1,
                    style="class:settings-dialog",
                ),
                _side_pad(),
            ],
            height=1,
            style="class:settings-dialog",
        )

        dialog = HSplit(
            [
                Window(height=1, char=" ", style="class:settings-dialog"),
                header,
                search,
                Window(height=1, char=" ", style="class:settings-dialog"),
                list_window,
                Window(height=1, char=" ", style="class:settings-dialog"),
                status,
                hints,
                Window(height=1, char=" ", style="class:settings-dialog"),
            ],
            width=Dimension.exact(DIALOG_WIDTH),
            height=Dimension.exact(DIALOG_HEIGHT),
            style="class:settings-dialog",
        )

        with_shadow = HSplit(
            [
                VSplit(
                    [
                        dialog,
                        Window(width=1, char=" ", style="class:settings-shadow"),
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
                            style="class:settings-shadow",
                        ),
                    ],
                    height=1,
                ),
            ],
            width=Dimension.exact(DIALOG_WIDTH + 1),
            height=Dimension.exact(DIALOG_HEIGHT + 1),
            style="class:settings-dialog",
        )
        dialog_layer = ConditionalContainer(content=with_shadow, filter=self.is_open)
        self.floats = [Float(content=dialog_layer, z_index=10**8)]

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
            host._move(-5)

        @self.key_bindings.add("pagedown", filter=self.is_open, eager=True)
        def _pgdn(_event):
            host._move(5)

        @self.key_bindings.add("enter", filter=self.is_open, eager=True)
        def _enter(_event):
            host.confirm()

        @self.key_bindings.add("escape", filter=self.is_open, eager=True)
        @self.key_bindings.add("c-c", filter=self.is_open, eager=True)
        def _esc(_event):
            host.cancel()

    def _status_strip(self):
        text = self.state.status or "Enter cycles the selected setting"
        max_len = max(12, DIALOG_WIDTH - PAD_X * 2 - 4)
        if len(text) > max_len:
            text = text[: max_len - 1] + "…"
        return [
            ("class:settings-preview-accent", "┃"),
            ("class:settings-preview-panel", f" {text}"),
        ]

    def _rebuild_rows(self, *, keep_key: str | None = None) -> None:
        self.state.rows = build_settings_rows(query=self.state.query)
        self.state.filtered = list(self.state.rows)
        if keep_key:
            for i, row in enumerate(self.state.filtered):
                if row.kind == "setting" and row.key == keep_key:
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
        cur = self._current_row()
        keep = cur.key if cur is not None else None
        self._rebuild_rows(keep_key=keep)
        self._invalidate()

    def _current_row(self) -> _SettingsRow | None:
        rows = self.state.filtered
        if not rows:
            return None
        idx = max(0, min(self.state.index, len(rows) - 1))
        row = rows[idx]
        if row.kind != "setting":
            return None
        return row

    def _move(self, delta: int) -> None:
        rows = self.state.filtered
        if not rows:
            return
        n = len(rows)
        i = self.state.index
        for _ in range(n):
            i = (i + delta) % n
            if rows[i].kind == "setting":
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
        if rows[idx].kind != "setting":
            return
        if idx == self.state.index:
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

    def _sync_session_config(self) -> None:
        from agent.config import Config

        cfg = Config.load()
        sess = getattr(self.terminal, "session", None)
        if sess is not None:
            sess.config = cfg

    def open(self) -> None:
        self.state = _SettingsModalState(open=True)
        self.search_buf.reset()
        self._rebuild_rows()
        try:
            self.app.layout.focus(self.search_buf)
        except Exception:  # noqa: BLE001
            pass
        self._invalidate()

    def confirm(self) -> None:
        row = self._current_row()
        if not self.state.open or row is None:
            return
        result = apply_setting_action(row.key)
        if result == "openai_profiles":
            self.state.open = False
            self._on_style_refresh()
            self._focus_compose()
            self._invalidate()
            mm = getattr(self.terminal, "_model_manager_modal_host", None)
            app = getattr(self.terminal, "_transcript_app", None)
            if mm is not None and getattr(app, "is_running", False):
                mm.open()
            else:
                handle = getattr(self.terminal, "_handle_model_manager_command", None)
                schedule = getattr(self.terminal, "_schedule_host_terminal", None)
                if callable(handle) and callable(schedule):
                    schedule(handle, "")
            return
        if result:
            self._sync_session_config()
            self.state.status = result
            self._rebuild_rows(keep_key=row.key)
            self._invalidate()

    def cancel(self) -> None:
        if not self.state.open:
            return
        self.state.open = False
        self._on_style_refresh()
        self._focus_compose()
        self._invalidate()


def run_settings_modal(terminal: Any) -> bool:
    """Open settings UI. Prefers in-app overlay; nested fullscreen is fallback."""
    import os
    import sys

    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False

    host = getattr(terminal, "_settings_modal_host", None)
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
        styles.update(settings_modal_style_extras(colors))
        styles = dim_transcript_styles_for_backdrop(styles)
        nested.style = Style.from_dict(styles)
        try:
            nested.invalidate()
        except Exception:  # noqa: BLE001
            pass

    canvas = Window(char=" ", style="class:settings-dialog")
    root = FloatContainer(content=canvas, floats=[])
    nested_app = Application(
        layout=Layout(root),
        key_bindings=KeyBindings(),
        full_screen=True,
        mouse_support=True,
        color_depth=ColorDepth.TRUE_COLOR,
    )
    held["app"] = nested_app
    host = SettingsModalHost(
        terminal,
        app=nested_app,
        on_style_refresh=_refresh,
        focus_compose=lambda: None,
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
        try:
            original_cancel()
        except Exception:  # noqa: BLE001
            pass
        return False
