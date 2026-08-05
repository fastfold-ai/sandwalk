"""OpenCode-style /skills modal: search, lean rows, Esc close.

In-app centered Float over the live transcript (same chrome as /models).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from ui.terminal.themes_modal import (
    dim_transcript_styles_for_backdrop,
    themes_modal_style_extras,
)

DIALOG_WIDTH = 72
PAD_X = 3
# Taller than /models so more of a large skill catalog is visible at once.
LIST_HEIGHT = 36
DIALOG_HEIGHT = 8 + LIST_HEIGHT


@dataclass
class _SkillRow:
    kind: str  # "header" | "skill"
    title: str
    skill: Any | None = None
    search: str = ""
    description: str = ""
    meta: str = ""  # right: on/off · author · version
    enabled: bool = True


@dataclass
class _SkillsModalState:
    skills: list[Any] = field(default_factory=list)
    rows: list[_SkillRow] = field(default_factory=list)
    filtered: list[_SkillRow] = field(default_factory=list)
    index: int = 0
    query: str = ""
    open: bool = False
    scroll: int = 0
    specialist_label: str = ""
    enabled_count: int = 0


def lean_description(text: str, *, max_len: int = 48) -> str:
    """Single-line truncated description for modal rows."""
    one = " ".join((text or "").split())
    if len(one) <= max_len:
        return one
    return one[: max_len - 1] + "…"


def skill_insert_token(name: str) -> str:
    """Compose-box token inserted on Enter / click (user can keep typing)."""
    return f"skill: {str(name or '').strip()}"


def insert_skill_into_compose(terminal: Any, name: str) -> None:
    """Insert ``skill: <name> `` into the live transcript compose buffer."""
    buf = getattr(terminal, "_transcript_buffer", None)
    if buf is None:
        return
    token = skill_insert_token(name)
    if not token.strip():
        return
    try:
        before = buf.document.text_before_cursor
    except Exception:  # noqa: BLE001
        before = str(getattr(buf, "text", "") or "")
    if before and not before[-1].isspace():
        buf.insert_text(" ")
    buf.insert_text(token)
    buf.insert_text(" ")


def skill_meta_label(info: Any) -> str:
    """Compact right-column: ``on · author · version`` (omit missing bits)."""
    from agent.skills import display_author

    bits: list[str] = []
    bits.append("on" if getattr(info, "enabled", True) else "off")
    author = str(display_author(info) or "").strip()
    if author and author != "-":
        bits.append(author)
    version = str(getattr(info, "version", None) or "").strip()
    if version:
        bits.append(version)
    return " · ".join(bits)


def collect_skills_for_modal(terminal: Any | None = None) -> tuple[list[Any], str]:
    """Installed skills, optionally filtered to the active specialist."""
    from agent.skills import list_skills
    from agent.specialists_manage import get_active_specialist

    skills = list(list_skills())
    active = get_active_specialist()
    label = ""
    if active is not None:
        allowed = {
            str(name).strip().lower()
            for name in (active.skill_names or [])
            if str(name).strip()
        }
        skills = [
            info
            for info in skills
            if str(info.name).strip().lower() in allowed
        ]
        label = f"{active.name} ({active.slug})"
    # Stable: enabled first, then name.
    skills.sort(
        key=lambda info: (
            0 if getattr(info, "enabled", True) else 1,
            str(getattr(info, "name", "") or "").lower(),
        )
    )
    return skills, label


def build_skill_rows(skills: list[Any], *, query: str = "") -> list[_SkillRow]:
    """Sectioned rows: Enabled → Disabled (or a single Skills header)."""
    q = (query or "").strip().lower()

    def matches(info: Any) -> bool:
        if not q:
            return True
        blob = " ".join(
            [
                str(getattr(info, "name", "") or ""),
                str(getattr(info, "description", "") or ""),
                str(getattr(info, "source", "") or ""),
                skill_meta_label(info),
            ]
        ).lower()
        return q in blob

    matched = [info for info in skills if matches(info)]
    enabled = [info for info in matched if getattr(info, "enabled", True)]
    disabled = [info for info in matched if not getattr(info, "enabled", True)]

    rows: list[_SkillRow] = []

    def add_section(title: str, items: list[Any]) -> None:
        if not items:
            return
        rows.append(_SkillRow(kind="header", title=title, search=title.lower()))
        for info in items:
            rows.append(_row_for_skill(info))

    if enabled and disabled:
        add_section("Enabled", enabled)
        add_section("Disabled", disabled)
    else:
        add_section("Skills", matched)
    return rows


def _row_for_skill(info: Any) -> _SkillRow:
    name = str(getattr(info, "name", "") or "")
    desc = lean_description(str(getattr(info, "description", "") or ""))
    meta = skill_meta_label(info)
    enabled = bool(getattr(info, "enabled", True))
    search = " ".join(
        [
            name,
            str(getattr(info, "description", "") or ""),
            str(getattr(info, "source", "") or ""),
            meta,
        ]
    )
    return _SkillRow(
        kind="skill",
        title=name,
        skill=info,
        search=search,
        description=desc,
        meta=meta,
        enabled=enabled,
    )


def first_selectable_index(rows: list[_SkillRow], start: int = 0) -> int:
    if not rows:
        return 0
    n = len(rows)
    i = max(0, min(start, n - 1))
    for _ in range(n):
        if rows[i].kind == "skill":
            return i
        i = (i + 1) % n
    return 0


def skills_modal_style_extras(colors: dict[str, str]) -> dict[str, str]:
    """Mirror themes modal chrome under skills-* class names."""
    base = themes_modal_style_extras(colors)
    out = {k.replace("themes-", "skills-", 1): v for k, v in base.items()}
    muted = colors["muted_fg"]
    panel = colors["panel_bg"]
    accent = colors["accent"]
    out["skills-section"] = f"bg:{panel} {accent} bold"
    out["skills-meta"] = f"bg:{panel} {muted}"
    out["skills-meta-selected"] = out.get(
        "skills-row-selected", f"bg:{accent} bold"
    )
    out["skills-desc"] = f"bg:{panel} {muted}"
    out["skills-desc-selected"] = out.get(
        "skills-row-selected", f"bg:{accent} bold"
    )
    return out


class SkillsModalHost:
    """In-app skills overlay hosted by the transcript FloatContainer."""

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
        self.state = _SkillsModalState()
        self._list_viewport_h = LIST_HEIGHT
        self.search_buf = Buffer(name="skills-search", multiline=False)
        self.search_buf.on_text_changed += self._on_search_text

        host = self
        self.is_open = Condition(lambda: host.state.open)

        class _SkillListControl(UIControl):
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
                        return [("class:skills-row", " " * width)]
                    row = rows[abs_i]
                    inset = " " * PAD_X
                    if row.kind == "header":
                        label = f"{inset}{row.title}"
                        pad = " " * max(0, width - len(label))
                        return [("class:skills-section", f"{label}{pad}")]
                    selected = abs_i == st.index
                    style = (
                        "class:skills-row-selected"
                        if selected
                        else "class:skills-row"
                    )
                    gutter = "●" if row.enabled else "○"
                    gutter_style = (
                        "class:skills-row-selected"
                        if selected
                        else "class:skills-row-current"
                    )
                    right_style = (
                        "class:skills-meta-selected"
                        if selected
                        else "class:skills-meta"
                    )
                    desc_style = (
                        "class:skills-desc-selected"
                        if selected
                        else "class:skills-desc"
                    )
                    right = f"{row.meta}{inset}" if row.meta else inset
                    prefix = f"{inset}{gutter} "
                    # Name + lean description on the left; meta on the right.
                    room = max(1, width - len(prefix) - len(right))
                    title = row.title
                    title_budget = min(len(title), max(8, room // 3))
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
                if etype == MouseEventType.MOUSE_MOVE:
                    host._move_to(y)
                    return None
                if etype == MouseEventType.MOUSE_DOWN:
                    host._move_to(y)
                    return None
                if etype == MouseEventType.MOUSE_UP:
                    host._move_to(y)
                    host.confirm()
                    return None
                return NotImplemented

        list_window = Window(
            content=_SkillListControl(),
            height=Dimension.exact(LIST_HEIGHT),
            dont_extend_height=True,
            style="class:skills-dialog",
        )

        def _side_pad():
            return Window(
                width=PAD_X, char=" ", style="class:skills-dialog", dont_extend_width=True
            )

        header = VSplit(
            [
                _side_pad(),
                Window(
                    content=FormattedTextControl(
                        lambda: [("class:skills-title", "Skills")]
                    ),
                    dont_extend_width=True,
                    style="class:skills-dialog",
                ),
                Window(char=" ", style="class:skills-dialog"),
                Window(
                    content=FormattedTextControl(
                        lambda: [("class:skills-hint", "esc")]
                    ),
                    width=3,
                    dont_extend_width=True,
                    style="class:skills-dialog",
                ),
                _side_pad(),
            ],
            height=1,
            style="class:skills-dialog",
        )

        search = VSplit(
            [
                _side_pad(),
                Window(
                    width=7,
                    content=FormattedTextControl(
                        lambda: [("class:skills-search.prompt", "Search ")]
                    ),
                    style="class:skills-search",
                ),
                Window(
                    content=BufferControl(buffer=self.search_buf, focusable=True),
                    height=1,
                    style="class:skills-search",
                ),
                _side_pad(),
            ],
            height=1,
            style="class:skills-search",
        )

        status = VSplit(
            [
                _side_pad(),
                Window(
                    content=FormattedTextControl(self._status_strip),
                    height=1,
                    style="class:skills-preview",
                ),
                _side_pad(),
            ],
            height=1,
            style="class:skills-preview",
        )

        hints = VSplit(
            [
                _side_pad(),
                Window(
                    content=FormattedTextControl(
                        lambda: [
                            (
                                "class:skills-hint",
                                "↑/↓ · enter insert · space toggle · esc",
                            )
                        ]
                    ),
                    height=1,
                    style="class:skills-dialog",
                ),
                _side_pad(),
            ],
            height=1,
            style="class:skills-dialog",
        )

        dialog = HSplit(
            [
                Window(height=1, char=" ", style="class:skills-dialog"),
                header,
                search,
                Window(height=1, char=" ", style="class:skills-dialog"),
                list_window,
                Window(height=1, char=" ", style="class:skills-dialog"),
                status,
                hints,
                Window(height=1, char=" ", style="class:skills-dialog"),
            ],
            width=Dimension.exact(DIALOG_WIDTH),
            height=Dimension.exact(DIALOG_HEIGHT),
            style="class:skills-dialog",
        )

        with_shadow = HSplit(
            [
                VSplit(
                    [
                        dialog,
                        Window(width=1, char=" ", style="class:skills-shadow"),
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
                            style="class:skills-shadow",
                        ),
                    ],
                    height=1,
                ),
            ],
            width=Dimension.exact(DIALOG_WIDTH + 1),
            height=Dimension.exact(DIALOG_HEIGHT + 1),
            style="class:skills-dialog",
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
            host._move(-10)

        @self.key_bindings.add("pagedown", filter=self.is_open, eager=True)
        def _pgdn(_event):
            host._move(10)

        @self.key_bindings.add("enter", filter=self.is_open, eager=True)
        def _enter(_event):
            host.confirm()

        # Space toggles enable (eager so it does not type into Search).
        @self.key_bindings.add("space", filter=self.is_open, eager=True)
        @self.key_bindings.add("c-space", filter=self.is_open, eager=True)
        def _toggle(_event):
            host.toggle_enabled()

        @self.key_bindings.add("escape", filter=self.is_open, eager=True)
        @self.key_bindings.add("c-c", filter=self.is_open, eager=True)
        def _esc(_event):
            host.cancel()

    def _status_strip(self):
        st = self.state
        row = None
        if st.filtered and 0 <= st.index < len(st.filtered):
            cand = st.filtered[st.index]
            if cand.kind == "skill":
                row = cand
        total = len(st.skills)
        bits = [f"{st.enabled_count}/{total} enabled"]
        if st.specialist_label:
            bits.append(st.specialist_label)
        if row is not None:
            desc = lean_description(
                str(getattr(row.skill, "description", "") or ""), max_len=40
            )
            if desc:
                bits.append(desc)
        text = " · ".join(bits)
        max_len = max(12, DIALOG_WIDTH - PAD_X * 2 - 4)
        if len(text) > max_len:
            text = text[: max_len - 1] + "…"
        return [
            ("class:skills-preview-accent", "┃"),
            ("class:skills-preview-panel", f" {text}"),
        ]

    def _rebuild_rows(self, *, keep_name: str | None = None) -> None:
        self.state.rows = build_skill_rows(self.state.skills, query=self.state.query)
        self.state.filtered = list(self.state.rows)
        if keep_name:
            key = keep_name.strip().lower()
            for i, row in enumerate(self.state.filtered):
                if (
                    row.kind == "skill"
                    and row.skill is not None
                    and str(getattr(row.skill, "name", "")).strip().lower() == key
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
        cur = self._current_skill()
        keep = str(getattr(cur, "name", "") or "") if cur else None
        self._rebuild_rows(keep_name=keep)
        self._invalidate()

    def _current_skill(self) -> Any | None:
        rows = self.state.filtered
        if not rows:
            return None
        idx = max(0, min(self.state.index, len(rows) - 1))
        row = rows[idx]
        if row.kind != "skill":
            return None
        return row.skill

    def _move(self, delta: int) -> None:
        rows = self.state.filtered
        if not rows:
            return
        n = len(rows)
        i = self.state.index
        for _ in range(n):
            i = (i + delta) % n
            if rows[i].kind == "skill":
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
            self.state.index = first_selectable_index(
                rows, self.state.scroll + vh - 1
            )
        self._invalidate()

    def _move_to(self, idx: int) -> None:
        rows = self.state.filtered
        if not rows or idx < 0 or idx >= len(rows):
            return
        if rows[idx].kind != "skill":
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

    def open(self) -> None:
        skills, specialist = collect_skills_for_modal(self.terminal)
        enabled_count = len(
            [info for info in skills if getattr(info, "enabled", True)]
        )
        self.state = _SkillsModalState(
            skills=skills,
            specialist_label=specialist,
            enabled_count=enabled_count,
            open=True,
        )
        self.search_buf.reset()
        self._rebuild_rows()
        try:
            self.app.layout.focus(self.search_buf)
        except Exception:  # noqa: BLE001
            pass
        self._invalidate()

    def toggle_enabled(self) -> None:
        """Toggle enable/disable for the highlighted skill (stay open)."""
        from agent.skills import set_skill_enabled

        info = self._current_skill()
        if not self.state.open or info is None:
            return
        name = str(getattr(info, "name", "") or "").strip()
        if not name:
            return
        new_enabled = not bool(getattr(info, "enabled", True))
        result = set_skill_enabled(name, new_enabled)
        if not result.get("ok"):
            return
        skills, specialist = collect_skills_for_modal(self.terminal)
        self.state.skills = skills
        self.state.specialist_label = specialist
        self.state.enabled_count = len(
            [s for s in skills if getattr(s, "enabled", True)]
        )
        self._rebuild_rows(keep_name=name)
        self._invalidate()

    def confirm(self) -> None:
        """Insert ``skill: <name>`` into compose and close (like @ file chips)."""
        info = self._current_skill()
        if not self.state.open or info is None:
            return
        name = str(getattr(info, "name", "") or "").strip()
        if not name:
            return
        self.state.open = False
        self._on_style_refresh()
        self._focus_compose()
        insert_skill_into_compose(self.terminal, name)
        self._invalidate()

    def cancel(self) -> None:
        if not self.state.open:
            return
        self.state.open = False
        self._on_style_refresh()
        self._focus_compose()
        self._invalidate()


def run_skills_modal(terminal: Any) -> bool:
    """Open skills UI. Prefers in-app overlay; nested fullscreen is fallback."""
    import os
    import sys

    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False

    host = getattr(terminal, "_skills_modal_host", None)
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
        styles.update(skills_modal_style_extras(colors))
        styles = dim_transcript_styles_for_backdrop(styles)
        nested.style = Style.from_dict(styles)
        try:
            nested.invalidate()
        except Exception:  # noqa: BLE001
            pass

    canvas = Window(char=" ", style="class:skills-dialog")
    root = FloatContainer(content=canvas, floats=[])
    nested_app = Application(
        layout=Layout(root),
        key_bindings=KeyBindings(),
        full_screen=True,
        mouse_support=True,
        color_depth=ColorDepth.TRUE_COLOR,
    )
    held["app"] = nested_app
    host = SkillsModalHost(
        terminal,
        app=nested_app,
        on_style_refresh=_refresh,
        focus_compose=lambda: None,
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
        try:
            original_cancel()
        except Exception:  # noqa: BLE001
            pass
        return False
