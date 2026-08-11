"""In-app /sessions modal: search, date groups, pin/delete/rename, resume."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from ui.terminal.themes_modal import (
    dim_transcript_styles_for_backdrop,
    themes_modal_style_extras,
)

DIALOG_WIDTH = 72
PAD_X = 3
LIST_HEIGHT = 28
DIALOG_HEIGHT = 8 + LIST_HEIGHT


@dataclass
class SessionEntry:
    session_id: str
    title: str
    snippet: str
    updated_at: float
    pinned: bool = False
    path: str = ""
    in_store: bool = False
    n_turns: int = 0
    model: str = ""


@dataclass
class _SessionRow:
    kind: str  # "header" | "session"
    title: str
    entry: SessionEntry | None = None
    search: str = ""
    snippet: str = ""
    pinned: bool = False


@dataclass
class _SessionsModalState:
    entries: list[SessionEntry] = field(default_factory=list)
    rows: list[_SessionRow] = field(default_factory=list)
    filtered: list[_SessionRow] = field(default_factory=list)
    index: int = 0
    query: str = ""
    open: bool = False
    scroll: int = 0
    status: str = ""
    mode: str = "browse"  # browse | rename | confirm_delete
    rename_text: str = ""
    pending_delete_id: str = ""


def sessions_modal_style_extras(colors: dict[str, str]) -> dict[str, str]:
    base = themes_modal_style_extras(colors)
    out = {k.replace("themes-", "sessions-", 1): v for k, v in base.items()}
    muted = colors["muted_fg"]
    panel = colors["panel_bg"]
    accent = colors["accent"]
    out["sessions-section"] = f"bg:{panel} {accent} bold"
    out["sessions-meta"] = f"bg:{panel} {muted}"
    out["sessions-meta-selected"] = out.get(
        "sessions-row-selected", f"bg:{accent} bold"
    )
    out["sessions-desc"] = f"bg:{panel} {muted}"
    out["sessions-desc-selected"] = out.get(
        "sessions-row-selected", f"bg:{accent} bold"
    )
    return out


def lean_text(text: str, *, max_len: int = 56) -> str:
    one = " ".join((text or "").split())
    if len(one) <= max_len:
        return one
    return one[: max_len - 1] + "…"


def _ts_to_float(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, datetime):
        return value.timestamp()
    if isinstance(value, str) and value.strip():
        raw = value.strip()
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
        except ValueError:
            try:
                return float(raw)
            except ValueError:
                return 0.0
    return 0.0


def _first_turn_query(path: object) -> str:
    try:
        with open(Path(str(path or ""))) as handle:
            handle.readline()
            line = handle.readline().strip()
        if not line:
            return ""
        record = json.loads(line)
        if record.get("type") == "turn":
            return str(record.get("query") or "").strip()
    except Exception:  # noqa: BLE001
        return ""
    return ""


def _date_header(ts: float) -> str:
    if ts <= 0:
        return "Unknown date"
    return time.strftime("%a %b %d %Y", time.localtime(ts))


def collect_session_entries(terminal: Any | None = None) -> list[SessionEntry]:
    """Merge AgentStore + Trajectory sessions (store wins for pin/title)."""
    from agent.trajectory import Trajectory
    from agent_server.store import AgentStore
    from agent_server.title import is_placeholder_title

    by_id: dict[str, SessionEntry] = {}

    try:
        store = AgentStore()
        for sess in store.list_sessions():
            sid = str(sess.id or "").strip()
            if not sid:
                continue
            title = str(sess.title or "").strip() or "untitled"
            ts = _ts_to_float(sess.last_message_at or sess.updated_at or sess.created_at)
            by_id[sid] = SessionEntry(
                session_id=sid,
                title=title,
                snippet=title,
                updated_at=ts,
                pinned=str(sess.organize_label or "") == "pinned",
                in_store=True,
            )
    except Exception:  # noqa: BLE001
        pass

    for meta in Trajectory.list_sessions():
        sid = str(meta.get("session_id") or "").strip()
        if not sid:
            continue
        path = str(meta.get("path") or "")
        raw_title = str(meta.get("title") or "").strip()
        if not raw_title or is_placeholder_title(raw_title):
            raw_title = _first_turn_query(path) or raw_title or "untitled"
        snippet = _first_turn_query(path) or raw_title
        ts = _ts_to_float(meta.get("updated_at", meta.get("created_at")))
        existing = by_id.get(sid)
        if existing is None:
            by_id[sid] = SessionEntry(
                session_id=sid,
                title=raw_title,
                snippet=lean_text(snippet, max_len=72),
                updated_at=ts,
                path=path,
                n_turns=int(meta.get("n_turns") or 0),
                model=str(meta.get("model") or ""),
            )
            continue
        if not existing.path:
            existing.path = path
        existing.n_turns = int(meta.get("n_turns") or existing.n_turns or 0)
        existing.model = str(meta.get("model") or existing.model or "")
        if existing.updated_at <= 0 and ts > 0:
            existing.updated_at = ts
        if is_placeholder_title(existing.title) and raw_title:
            existing.title = raw_title
        if snippet:
            existing.snippet = lean_text(snippet, max_len=72)

    entries = list(by_id.values())
    entries.sort(
        key=lambda e: (0 if e.pinned else 1, -e.updated_at, e.session_id),
    )
    return entries


def build_session_rows(
    entries: list[SessionEntry], *, query: str = ""
) -> list[_SessionRow]:
    q = (query or "").strip().lower()
    matched = []
    for entry in entries:
        blob = " ".join(
            [entry.session_id, entry.title, entry.snippet, entry.model]
        ).lower()
        if q and q not in blob:
            continue
        matched.append(entry)

    pinned = [e for e in matched if e.pinned]
    unpinned = [e for e in matched if not e.pinned]

    rows: list[_SessionRow] = []

    def add_entry(entry: SessionEntry) -> None:
        rows.append(
            _SessionRow(
                kind="session",
                title=lean_text(entry.title, max_len=48),
                entry=entry,
                search=f"{entry.session_id} {entry.title} {entry.snippet}",
                snippet=lean_text(entry.snippet, max_len=56),
                pinned=entry.pinned,
            )
        )

    if pinned:
        rows.append(_SessionRow(kind="header", title="Pinned", search="pinned"))
        for entry in pinned:
            add_entry(entry)

    # Group unpinned by local calendar day (newest day first).
    by_day: dict[str, list[SessionEntry]] = {}
    day_order: list[str] = []
    for entry in unpinned:
        day = _date_header(entry.updated_at)
        if day not in by_day:
            by_day[day] = []
            day_order.append(day)
        by_day[day].append(entry)

    for day in day_order:
        rows.append(_SessionRow(kind="header", title=day, search=day.lower()))
        for entry in by_day[day]:
            add_entry(entry)
    return rows


def first_selectable_index(rows: list[_SessionRow], start: int = 0) -> int:
    if not rows:
        return 0
    n = len(rows)
    i = max(0, min(start, n - 1))
    for _ in range(n):
        if rows[i].kind == "session":
            return i
        i = (i + 1) % n
    return 0


def ensure_store_session(entry: SessionEntry) -> Any:
    """Return AgentStore session row, importing from Trajectory when needed."""
    from agent.trajectory import Trajectory
    from agent_server.session_sync.importer import import_trajectory
    from agent_server.store import AgentStore

    store = AgentStore()
    existing = store.get_session(entry.session_id)
    if existing is not None:
        return existing
    try:
        traj = Trajectory.load(entry.session_id)
    except Exception:  # noqa: BLE001
        return None
    try:
        import_trajectory(store, traj, force=False)
    except Exception:  # noqa: BLE001
        return None
    return store.get_session(entry.session_id)


def toggle_session_pin(entry: SessionEntry) -> bool:
    from agent_server.store import AgentStore

    if ensure_store_session(entry) is None:
        return False
    store = AgentStore()
    current = store.get_session(entry.session_id)
    if current is None:
        return False
    pinned = str(current.organize_label or "") == "pinned"
    store.update_session(
        entry.session_id,
        organize_label=None if pinned else "pinned",
        update_organize_label=True,
    )
    entry.pinned = not pinned
    return True


def rename_session_entry(entry: SessionEntry, title: str) -> bool:
    cleaned = " ".join((title or "").split()).strip()
    if not cleaned:
        return False
    from agent_server.store import AgentStore

    if ensure_store_session(entry) is None and not entry.path:
        return False
    store = AgentStore()
    if store.get_session(entry.session_id) is not None:
        store.update_session(entry.session_id, title=cleaned, title_source="user")
    if entry.path:
        _rewrite_trajectory_title(entry.path, cleaned)
    entry.title = cleaned
    entry.snippet = cleaned
    return True


def _rewrite_trajectory_title(path: str, title: str) -> None:
    p = Path(path)
    if not p.is_file():
        return
    try:
        lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
    except OSError:
        return
    if not lines:
        return
    try:
        meta = json.loads(lines[0])
    except json.JSONDecodeError:
        return
    if meta.get("type") != "meta":
        return
    meta["title"] = title
    lines[0] = json.dumps(meta, ensure_ascii=False) + (
        "\n" if lines[0].endswith("\n") else ""
    )
    try:
        p.write_text("".join(lines), encoding="utf-8")
    except OSError:
        return


def delete_session_entry(terminal: Any, entry: SessionEntry) -> bool:
    from agent.trajectory import Trajectory
    from agent_server.store import AgentStore

    sid = entry.session_id
    try:
        store = AgentStore()
        store.delete_session(sid)
    except Exception:  # noqa: BLE001
        pass
    try:
        Trajectory.delete_session(sid)
    except FileNotFoundError:
        pass
    except Exception:  # noqa: BLE001
        return False

    current = None
    agent = getattr(terminal, "agent", None)
    traj = getattr(agent, "trajectory", None)
    if traj is not None:
        current = str(getattr(traj, "session_id", "") or "")
    if current == sid:
        new_fn = getattr(terminal, "_new_session", None)
        if callable(new_fn):
            new_fn()
    return True


class SessionsModalHost:
    """In-app sessions overlay hosted by the transcript FloatContainer."""

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
        self.state = _SessionsModalState()
        self._list_viewport_h = LIST_HEIGHT
        self.search_buf = Buffer(name="sessions-search", multiline=False)
        self.search_buf.on_text_changed += self._on_search_text
        self.rename_buf = Buffer(name="sessions-rename", multiline=False)

        host = self
        self.is_open = Condition(lambda: host.state.open)
        self.is_browse = Condition(
            lambda: host.state.open and host.state.mode == "browse"
        )
        self.is_rename = Condition(
            lambda: host.state.open and host.state.mode == "rename"
        )

        class _SessionListControl(UIControl):
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
                        return [("class:sessions-row", " " * width)]
                    row = rows[abs_i]
                    inset = " " * PAD_X
                    if row.kind == "header":
                        label = f"{inset}{row.title}"
                        pad = " " * max(0, width - len(label))
                        return [("class:sessions-section", f"{label}{pad}")]
                    selected = abs_i == st.index
                    style = (
                        "class:sessions-row-selected"
                        if selected
                        else "class:sessions-row"
                    )
                    gutter = "●" if row.pinned else " "
                    gutter_style = (
                        "class:sessions-row-selected"
                        if selected
                        else "class:sessions-row-current"
                    )
                    desc_style = (
                        "class:sessions-desc-selected"
                        if selected
                        else "class:sessions-desc"
                    )
                    prefix = f"{inset}{gutter} "
                    room = max(1, width - len(prefix) - len(inset))
                    title = row.title
                    title_budget = min(len(title), max(8, room // 2))
                    if len(title) > title_budget:
                        title = title[: title_budget - 1] + "…"
                    rest = room - len(title)
                    desc = ""
                    if row.snippet and rest > 4:
                        desc = f"  {row.snippet}"
                        if len(desc) > rest:
                            desc = desc[: rest - 1] + "…"
                    pad = " " * max(
                        0, width - len(prefix) - len(title) - len(desc) - len(inset)
                    )
                    return [
                        (gutter_style, prefix),
                        (style, title),
                        (desc_style, desc),
                        (style, pad + inset),
                    ]

                return UIContent(
                    get_line=get_line,
                    line_count=max(1, min(height, len(rows) or 1)),
                    show_cursor=False,
                )

            def mouse_handler(self, mouse_event):
                if host.state.mode != "browse":
                    return NotImplemented
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
            content=_SessionListControl(),
            height=Dimension.exact(LIST_HEIGHT),
            dont_extend_height=True,
            style="class:sessions-dialog",
        )

        def _side_pad():
            return Window(
                width=PAD_X,
                char=" ",
                style="class:sessions-dialog",
                dont_extend_width=True,
            )

        header = VSplit(
            [
                _side_pad(),
                Window(
                    content=FormattedTextControl(
                        lambda: [("class:sessions-title", "Sessions")]
                    ),
                    dont_extend_width=True,
                    style="class:sessions-dialog",
                ),
                Window(char=" ", style="class:sessions-dialog"),
                Window(
                    content=FormattedTextControl(
                        lambda: [("class:sessions-hint", "esc")]
                    ),
                    width=3,
                    dont_extend_width=True,
                    style="class:sessions-dialog",
                ),
                _side_pad(),
            ],
            height=1,
            style="class:sessions-dialog",
        )

        search_browse = VSplit(
            [
                _side_pad(),
                Window(
                    width=7,
                    content=FormattedTextControl(
                        lambda: [("class:sessions-search.prompt", "Search ")]
                    ),
                    style="class:sessions-search",
                ),
                Window(
                    content=BufferControl(buffer=self.search_buf, focusable=True),
                    height=1,
                    style="class:sessions-search",
                ),
                _side_pad(),
            ],
            height=1,
            style="class:sessions-search",
        )
        search_rename = VSplit(
            [
                _side_pad(),
                Window(
                    width=7,
                    content=FormattedTextControl(
                        lambda: [("class:sessions-search.prompt", "Rename ")]
                    ),
                    style="class:sessions-search",
                ),
                Window(
                    content=BufferControl(buffer=self.rename_buf, focusable=True),
                    height=1,
                    style="class:sessions-search",
                ),
                _side_pad(),
            ],
            height=1,
            style="class:sessions-search",
        )
        search_layer = HSplit(
            [
                ConditionalContainer(content=search_browse, filter=self.is_browse),
                ConditionalContainer(content=search_rename, filter=self.is_rename),
                ConditionalContainer(
                    content=search_browse,
                    filter=Condition(
                        lambda: host.state.open and host.state.mode == "confirm_delete"
                    ),
                ),
            ]
        )

        status = VSplit(
            [
                _side_pad(),
                Window(
                    content=FormattedTextControl(self._status_strip),
                    height=1,
                    style="class:sessions-preview",
                ),
                _side_pad(),
            ],
            height=1,
            style="class:sessions-preview",
        )

        hints = VSplit(
            [
                _side_pad(),
                Window(
                    content=FormattedTextControl(self._hints_strip),
                    height=1,
                    style="class:sessions-dialog",
                ),
                _side_pad(),
            ],
            height=1,
            style="class:sessions-dialog",
        )

        dialog = HSplit(
            [
                Window(height=1, char=" ", style="class:sessions-dialog"),
                header,
                search_layer,
                Window(height=1, char=" ", style="class:sessions-dialog"),
                list_window,
                Window(height=1, char=" ", style="class:sessions-dialog"),
                status,
                hints,
                Window(height=1, char=" ", style="class:sessions-dialog"),
            ],
            width=Dimension.exact(DIALOG_WIDTH),
            height=Dimension.exact(DIALOG_HEIGHT),
            style="class:sessions-dialog",
        )

        with_shadow = HSplit(
            [
                VSplit(
                    [
                        dialog,
                        Window(width=1, char=" ", style="class:sessions-shadow"),
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
                            style="class:sessions-shadow",
                        ),
                    ],
                    height=1,
                ),
            ],
            width=Dimension.exact(DIALOG_WIDTH + 1),
            height=Dimension.exact(DIALOG_HEIGHT + 1),
            style="class:sessions-dialog",
        )
        dialog_layer = ConditionalContainer(content=with_shadow, filter=self.is_open)
        self.floats = [Float(content=dialog_layer, z_index=10**8)]

        self.key_bindings = KeyBindings()

        @self.key_bindings.add("up", filter=self.is_browse, eager=True)
        @self.key_bindings.add("c-p", filter=self.is_browse, eager=True)
        def _up(_event):
            host._move(-1)

        @self.key_bindings.add("down", filter=self.is_browse, eager=True)
        @self.key_bindings.add("c-n", filter=self.is_browse, eager=True)
        def _down(_event):
            host._move(1)

        @self.key_bindings.add("pageup", filter=self.is_browse, eager=True)
        def _pgup(_event):
            host._move(-10)

        @self.key_bindings.add("pagedown", filter=self.is_browse, eager=True)
        def _pgdn(_event):
            host._move(10)

        @self.key_bindings.add("enter", filter=self.is_open, eager=True)
        def _enter(_event):
            host.confirm()

        @self.key_bindings.add("c-f", filter=self.is_browse, eager=True)
        def _pin(_event):
            host.toggle_pin()

        @self.key_bindings.add("c-d", filter=self.is_browse, eager=True)
        def _del(_event):
            host.begin_delete()

        @self.key_bindings.add("c-r", filter=self.is_browse, eager=True)
        def _ren(_event):
            host.begin_rename()

        @self.key_bindings.add("escape", filter=self.is_open, eager=True)
        @self.key_bindings.add("c-c", filter=self.is_open, eager=True)
        def _esc(_event):
            if host.state.mode in {"rename", "confirm_delete"}:
                host.state.mode = "browse"
                host.state.pending_delete_id = ""
                host.state.status = ""
                try:
                    host.app.layout.focus(host.search_buf)
                except Exception:  # noqa: BLE001
                    pass
                host._invalidate()
                return
            host.cancel()

    def _hints_strip(self):
        if self.state.mode == "rename":
            text = "enter save · esc cancel"
        elif self.state.mode == "confirm_delete":
            text = "enter confirm delete · esc cancel"
        else:
            text = "pin/unpin: ctrl+f  delete: ctrl+d  rename: ctrl+r"
        return [("class:sessions-hint", text)]

    def _status_strip(self):
        st = self.state
        if st.mode == "confirm_delete":
            text = f"Delete {st.pending_delete_id}? Enter to confirm"
        elif st.status:
            text = st.status
        else:
            n = len([r for r in st.filtered if r.kind == "session"])
            text = f"{n} session{'s' if n != 1 else ''}"
            row = self._current_entry()
            if row is not None:
                text = f"{text} · {row.session_id}"
        max_len = max(12, DIALOG_WIDTH - PAD_X * 2 - 4)
        if len(text) > max_len:
            text = text[: max_len - 1] + "…"
        return [
            ("class:sessions-preview-accent", "┃"),
            ("class:sessions-preview-panel", f" {text}"),
        ]

    def _rebuild_rows(self, *, keep_id: str | None = None) -> None:
        self.state.rows = build_session_rows(self.state.entries, query=self.state.query)
        self.state.filtered = list(self.state.rows)
        if keep_id:
            for i, row in enumerate(self.state.filtered):
                if (
                    row.kind == "session"
                    and row.entry is not None
                    and row.entry.session_id == keep_id
                ):
                    self.state.index = i
                    break
            else:
                self.state.index = first_selectable_index(self.state.filtered)
        else:
            self.state.index = first_selectable_index(self.state.filtered)
        self.state.scroll = 0

    def _on_search_text(self, _buf) -> None:
        if not self.state.open or self.state.mode != "browse":
            return
        self.state.query = self.search_buf.text
        cur = self._current_entry()
        keep = cur.session_id if cur else None
        self._rebuild_rows(keep_id=keep)
        self._invalidate()

    def _current_entry(self) -> SessionEntry | None:
        rows = self.state.filtered
        if not rows:
            return None
        idx = max(0, min(self.state.index, len(rows) - 1))
        row = rows[idx]
        if row.kind != "session" or row.entry is None:
            return None
        return row.entry

    def _move(self, delta: int) -> None:
        rows = self.state.filtered
        if not rows:
            return
        n = len(rows)
        i = self.state.index
        for _ in range(n):
            i = (i + delta) % n
            if rows[i].kind == "session":
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
        if rows[idx].kind != "session":
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
        entries = collect_session_entries(self.terminal)
        self.state = _SessionsModalState(entries=entries, open=True, mode="browse")
        self.search_buf.reset()
        self.rename_buf.reset()
        self._rebuild_rows()
        try:
            self.app.layout.focus(self.search_buf)
        except Exception:  # noqa: BLE001
            pass
        self._invalidate()

    def toggle_pin(self) -> None:
        entry = self._current_entry()
        if entry is None:
            return
        if not toggle_session_pin(entry):
            self.state.status = "Could not pin (sync session first?)"
            self._invalidate()
            return
        self.state.status = "Pinned" if entry.pinned else "Unpinned"
        self.state.entries = collect_session_entries(self.terminal)
        self._rebuild_rows(keep_id=entry.session_id)
        self._invalidate()

    def begin_delete(self) -> None:
        entry = self._current_entry()
        if entry is None:
            return
        self.state.mode = "confirm_delete"
        self.state.pending_delete_id = entry.session_id
        self.state.status = f"Delete {entry.session_id}?"
        self._invalidate()

    def begin_rename(self) -> None:
        entry = self._current_entry()
        if entry is None:
            return
        self.state.mode = "rename"
        self.rename_buf.text = entry.title
        self.rename_buf.cursor_position = len(self.rename_buf.text)
        try:
            self.app.layout.focus(self.rename_buf)
        except Exception:  # noqa: BLE001
            pass
        self._invalidate()

    def confirm(self) -> None:
        if not self.state.open:
            return
        if self.state.mode == "rename":
            entry = self._current_entry()
            if entry is None:
                return
            title = self.rename_buf.text
            if rename_session_entry(entry, title):
                self.state.status = f"Renamed → {entry.title}"
                self.state.entries = collect_session_entries(self.terminal)
                self.state.mode = "browse"
                self._rebuild_rows(keep_id=entry.session_id)
                try:
                    self.app.layout.focus(self.search_buf)
                except Exception:  # noqa: BLE001
                    pass
            else:
                self.state.status = "Rename failed"
            self._invalidate()
            return
        if self.state.mode == "confirm_delete":
            entry = self._current_entry()
            sid = self.state.pending_delete_id
            if entry is None or entry.session_id != sid:
                # Find by id in entries
                entry = next(
                    (e for e in self.state.entries if e.session_id == sid), None
                )
            if entry is None:
                self.state.mode = "browse"
                self._invalidate()
                return
            if delete_session_entry(self.terminal, entry):
                self.state.status = f"Deleted {sid}"
                self.state.mode = "browse"
                self.state.pending_delete_id = ""
                self.state.entries = collect_session_entries(self.terminal)
                self._rebuild_rows()
            else:
                self.state.status = "Delete failed"
                self.state.mode = "browse"
            self._invalidate()
            return

        entry = self._current_entry()
        if entry is None:
            return
        sid = entry.session_id
        self.state.open = False
        self._on_style_refresh()
        self._focus_compose()
        self._invalidate()
        resume = getattr(self.terminal, "_resume_session", None)
        if callable(resume):
            # Resume without nested PromptSession picker.
            resume(sid)

    def cancel(self) -> None:
        if not self.state.open:
            return
        self.state.open = False
        self._on_style_refresh()
        self._focus_compose()
        self._invalidate()


def run_sessions_modal(terminal: Any) -> bool:
    import os
    import sys

    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False

    host = getattr(terminal, "_sessions_modal_host", None)
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
        styles.update(sessions_modal_style_extras(colors))
        styles = dim_transcript_styles_for_backdrop(styles)
        nested.style = Style.from_dict(styles)
        try:
            nested.invalidate()
        except Exception:  # noqa: BLE001
            pass

    canvas = Window(char=" ", style="class:sessions-dialog")
    root = FloatContainer(content=canvas, floats=[])
    nested_app = Application(
        layout=Layout(root),
        key_bindings=KeyBindings(),
        full_screen=True,
        mouse_support=True,
        color_depth=ColorDepth.TRUE_COLOR,
    )
    held["app"] = nested_app
    host = SessionsModalHost(
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
        # For resume: exit nested after closing; for rename/delete stay unless closed.
        was_browse = host.state.mode == "browse"
        original_confirm()
        if was_browse and not host.state.open and nested_app.is_running:
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
