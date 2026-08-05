"""OpenCode-style /mcps modal: search, lean rows, Esc close.

In-app centered Float over the live transcript (same chrome as /skills).
Enter inserts ``mcp: <id>``; Space toggles enable.
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
LIST_HEIGHT = 36
DIALOG_HEIGHT = 8 + LIST_HEIGHT


@dataclass
class _McpRow:
    kind: str  # "header" | "mcp"
    title: str
    server: dict[str, Any] | None = None
    search: str = ""
    description: str = ""
    meta: str = ""  # right: on/off · id · transport
    enabled: bool = True


@dataclass
class _McpModalState:
    servers: list[dict[str, Any]] = field(default_factory=list)
    rows: list[_McpRow] = field(default_factory=list)
    filtered: list[_McpRow] = field(default_factory=list)
    index: int = 0
    query: str = ""
    open: bool = False
    scroll: int = 0
    enabled_count: int = 0


def lean_description(text: str, *, max_len: int = 48) -> str:
    """Single-line truncated description for modal rows."""
    one = " ".join((text or "").split())
    if len(one) <= max_len:
        return one
    return one[: max_len - 1] + "…"


def mcp_insert_token(server: dict[str, Any] | str) -> str:
    """Compose-box token inserted on Enter / click."""
    if isinstance(server, dict):
        key = str(
            server.get("insert_key")
            or server.get("id")
            or server.get("name")
            or ""
        ).strip()
    else:
        key = str(server or "").strip()
    key = key.replace(" ", "_")
    return f"mcp: {key}"


def insert_mcp_into_compose(terminal: Any, server: dict[str, Any] | str) -> None:
    """Insert ``mcp: <id> `` into the live transcript compose buffer."""
    buf = getattr(terminal, "_transcript_buffer", None)
    if buf is None:
        return
    token = mcp_insert_token(server)
    if not token.strip() or token == "mcp:":
        return
    try:
        before = buf.document.text_before_cursor
    except Exception:  # noqa: BLE001
        before = str(getattr(buf, "text", "") or "")
    if before and not before[-1].isspace():
        buf.insert_text(" ")
    buf.insert_text(token)
    buf.insert_text(" ")


def mcp_meta_label(server: dict[str, Any]) -> str:
    """Compact right-column: ``on · id · transport`` (omit missing bits)."""
    bits: list[str] = []
    bits.append("on" if server.get("enabled") else "off")
    status = str(server.get("status") or "").strip()
    if status and status not in {"off", "on"}:
        bits.append(status)
    sid = str(server.get("id") or "").strip()
    if sid:
        bits.append(sid)
    transport = str(server.get("transport") or "").strip()
    if transport:
        # Shorten streamable_http → http for lean meta.
        bits.append("http" if transport == "streamable_http" else transport)
    return " · ".join(bits)


def collect_mcp_for_modal(_terminal: Any | None = None) -> list[dict[str, Any]]:
    """Catalog suggestions + custom registered servers for the picker."""
    from agent.mcp_manage.resolve import _service

    service = _service()
    catalog = service.catalog_statuses()
    servers = service.store.list_mcp_servers()
    catalog_ids = {str(row.get("id") or "") for row in catalog}

    items: list[dict[str, Any]] = []
    for row in catalog:
        if row.get("connected"):
            status = "connected"
        elif row.get("enabled"):
            status = "enabled"
        elif row.get("configured"):
            status = "key saved"
        else:
            status = "off"
        items.append(
            {
                "kind": "catalog",
                "id": str(row.get("id") or ""),
                "name": str(row.get("name") or ""),
                "description": str(row.get("description") or ""),
                "enabled": bool(row.get("enabled")),
                "status": status,
                "transport": str(row.get("transport") or ""),
                "target": str(row.get("url") or ""),
                "auth": str(
                    row.get("auth_method")
                    or row.get("preferred_auth")
                    or row.get("auth_mode")
                    or ""
                ),
                "ref": str(row.get("id") or ""),
                "insert_key": str(row.get("id") or ""),
            }
        )

    for server in servers:
        cid = str(getattr(server, "catalog_id", None) or "")
        if cid and cid in catalog_ids:
            continue
        target = server.url or (
            f"{server.command} {' '.join(server.args or [])}".strip()
            if server.command
            else ""
        )
        name = str(server.name or "").strip() or server.id[:8]
        items.append(
            {
                "kind": "custom",
                "id": server.id[:8],
                "name": name,
                "description": str(getattr(server, "description", None) or "Custom MCP"),
                "enabled": bool(server.enabled),
                "status": "on" if server.enabled else "off",
                "transport": str(server.transport or ""),
                "target": str(target or ""),
                "auth": "",
                "ref": server.id,
                "insert_key": name.replace(" ", "_"),
            }
        )

    items.sort(
        key=lambda row: (
            0 if row.get("enabled") else 1,
            str(row.get("name") or "").lower(),
        )
    )
    return items


def set_mcp_enabled(ref: str, enabled: bool) -> dict[str, Any]:
    """Enable/disable an MCP server by catalog id, UUID, or name."""
    from agent.mcp_manage.resolve import _service, _store, resolve_server_ref
    from agent_server.mcp_service.auth import credentials_configured

    key = (ref or "").strip()
    if not key:
        return {"ok": False, "summary": "Missing MCP id."}
    store = _store()
    service = _service(store)
    entry, server = resolve_server_ref(key, store)
    if server is None and entry is not None:
        server = service.ensure_catalog_server(entry.id, enabled=False)
    if server is None:
        return {"ok": False, "summary": f"MCP '{key}' not found."}
    if enabled and entry is not None and not credentials_configured(entry):
        return {
            "ok": False,
            "summary": f"{entry.name} is not connected. Run: /mcps connect {entry.id}",
        }
    store.update_mcp_server(server.id, enabled=enabled)
    return {
        "ok": True,
        "summary": f"{'Enabled' if enabled else 'Disabled'} {server.name}",
    }


def build_mcp_rows(
    servers: list[dict[str, Any]], *, query: str = ""
) -> list[_McpRow]:
    """Sectioned rows: Enabled → Disabled (or a single MCP header)."""
    q = (query or "").strip().lower()

    def matches(row: dict[str, Any]) -> bool:
        if not q:
            return True
        blob = " ".join(
            [
                str(row.get("name") or ""),
                str(row.get("id") or ""),
                str(row.get("description") or ""),
                str(row.get("target") or ""),
                str(row.get("auth") or ""),
                mcp_meta_label(row),
            ]
        ).lower()
        return q in blob

    matched = [row for row in servers if matches(row)]
    enabled = [row for row in matched if row.get("enabled")]
    disabled = [row for row in matched if not row.get("enabled")]

    rows: list[_McpRow] = []

    def add_section(title: str, items: list[dict[str, Any]]) -> None:
        if not items:
            return
        rows.append(_McpRow(kind="header", title=title, search=title.lower()))
        for item in items:
            rows.append(_row_for_mcp(item))

    if enabled and disabled:
        add_section("Enabled", enabled)
        add_section("Disabled", disabled)
    else:
        add_section("MCP", matched)
    return rows


def _row_for_mcp(server: dict[str, Any]) -> _McpRow:
    name = str(server.get("name") or server.get("id") or "")
    desc = lean_description(str(server.get("description") or ""))
    meta = mcp_meta_label(server)
    enabled = bool(server.get("enabled"))
    search = " ".join(
        [
            name,
            str(server.get("id") or ""),
            str(server.get("description") or ""),
            str(server.get("target") or ""),
            meta,
        ]
    )
    return _McpRow(
        kind="mcp",
        title=name,
        server=server,
        search=search,
        description=desc,
        meta=meta,
        enabled=enabled,
    )


def first_selectable_index(rows: list[_McpRow], start: int = 0) -> int:
    if not rows:
        return 0
    n = len(rows)
    i = max(0, min(start, n - 1))
    for _ in range(n):
        if rows[i].kind == "mcp":
            return i
        i = (i + 1) % n
    return 0


def mcp_modal_style_extras(colors: dict[str, str]) -> dict[str, str]:
    """Mirror themes modal chrome under mcp-* class names."""
    base = themes_modal_style_extras(colors)
    out = {k.replace("themes-", "mcp-", 1): v for k, v in base.items()}
    muted = colors["muted_fg"]
    panel = colors["panel_bg"]
    accent = colors["accent"]
    out["mcp-section"] = f"bg:{panel} {accent} bold"
    out["mcp-meta"] = f"bg:{panel} {muted}"
    out["mcp-meta-selected"] = out.get("mcp-row-selected", f"bg:{accent} bold")
    out["mcp-desc"] = f"bg:{panel} {muted}"
    out["mcp-desc-selected"] = out.get("mcp-row-selected", f"bg:{accent} bold")
    return out


class McpModalHost:
    """In-app MCP overlay hosted by the transcript FloatContainer."""

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
        self.state = _McpModalState()
        self._list_viewport_h = LIST_HEIGHT
        self.search_buf = Buffer(name="mcp-search", multiline=False)
        self.search_buf.on_text_changed += self._on_search_text

        host = self
        self.is_open = Condition(lambda: host.state.open)

        class _McpListControl(UIControl):
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
                        return [("class:mcp-row", " " * width)]
                    row = rows[abs_i]
                    inset = " " * PAD_X
                    if row.kind == "header":
                        label = f"{inset}{row.title}"
                        pad = " " * max(0, width - len(label))
                        return [("class:mcp-section", f"{label}{pad}")]
                    selected = abs_i == st.index
                    style = (
                        "class:mcp-row-selected" if selected else "class:mcp-row"
                    )
                    gutter = "●" if row.enabled else "○"
                    gutter_style = (
                        "class:mcp-row-selected"
                        if selected
                        else "class:mcp-row-current"
                    )
                    right_style = (
                        "class:mcp-meta-selected" if selected else "class:mcp-meta"
                    )
                    desc_style = (
                        "class:mcp-desc-selected" if selected else "class:mcp-desc"
                    )
                    right = f"{row.meta}{inset}" if row.meta else inset
                    prefix = f"{inset}{gutter} "
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
            content=_McpListControl(),
            height=Dimension.exact(LIST_HEIGHT),
            dont_extend_height=True,
            style="class:mcp-dialog",
        )

        def _side_pad():
            return Window(
                width=PAD_X, char=" ", style="class:mcp-dialog", dont_extend_width=True
            )

        header = VSplit(
            [
                _side_pad(),
                Window(
                    content=FormattedTextControl(
                        lambda: [("class:mcp-title", "MCP")]
                    ),
                    dont_extend_width=True,
                    style="class:mcp-dialog",
                ),
                Window(char=" ", style="class:mcp-dialog"),
                Window(
                    content=FormattedTextControl(
                        lambda: [("class:mcp-hint", "esc")]
                    ),
                    width=3,
                    dont_extend_width=True,
                    style="class:mcp-dialog",
                ),
                _side_pad(),
            ],
            height=1,
            style="class:mcp-dialog",
        )

        search = VSplit(
            [
                _side_pad(),
                Window(
                    width=7,
                    content=FormattedTextControl(
                        lambda: [("class:mcp-search.prompt", "Search ")]
                    ),
                    style="class:mcp-search",
                ),
                Window(
                    content=BufferControl(buffer=self.search_buf, focusable=True),
                    height=1,
                    style="class:mcp-search",
                ),
                _side_pad(),
            ],
            height=1,
            style="class:mcp-search",
        )

        status = VSplit(
            [
                _side_pad(),
                Window(
                    content=FormattedTextControl(self._status_strip),
                    height=1,
                    style="class:mcp-preview",
                ),
                _side_pad(),
            ],
            height=1,
            style="class:mcp-preview",
        )

        hints = VSplit(
            [
                _side_pad(),
                Window(
                    content=FormattedTextControl(
                        lambda: [
                            (
                                "class:mcp-hint",
                                "↑/↓ · enter insert · space toggle · esc",
                            )
                        ]
                    ),
                    height=1,
                    style="class:mcp-dialog",
                ),
                _side_pad(),
            ],
            height=1,
            style="class:mcp-dialog",
        )

        dialog = HSplit(
            [
                Window(height=1, char=" ", style="class:mcp-dialog"),
                header,
                search,
                Window(height=1, char=" ", style="class:mcp-dialog"),
                list_window,
                Window(height=1, char=" ", style="class:mcp-dialog"),
                status,
                hints,
                Window(height=1, char=" ", style="class:mcp-dialog"),
            ],
            width=Dimension.exact(DIALOG_WIDTH),
            height=Dimension.exact(DIALOG_HEIGHT),
            style="class:mcp-dialog",
        )

        with_shadow = HSplit(
            [
                VSplit(
                    [
                        dialog,
                        Window(width=1, char=" ", style="class:mcp-shadow"),
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
                            style="class:mcp-shadow",
                        ),
                    ],
                    height=1,
                ),
            ],
            width=Dimension.exact(DIALOG_WIDTH + 1),
            height=Dimension.exact(DIALOG_HEIGHT + 1),
            style="class:mcp-dialog",
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
            if cand.kind == "mcp":
                row = cand
        total = len(st.servers)
        bits = [f"{st.enabled_count}/{total} enabled"]
        if row is not None and row.server is not None:
            target = lean_description(str(row.server.get("target") or ""), max_len=36)
            if target:
                bits.append(target)
            elif row.description:
                bits.append(row.description[:40])
        text = " · ".join(bits)
        max_len = max(12, DIALOG_WIDTH - PAD_X * 2 - 4)
        if len(text) > max_len:
            text = text[: max_len - 1] + "…"
        return [
            ("class:mcp-preview-accent", "┃"),
            ("class:mcp-preview-panel", f" {text}"),
        ]

    def _rebuild_rows(self, *, keep_ref: str | None = None) -> None:
        self.state.rows = build_mcp_rows(self.state.servers, query=self.state.query)
        self.state.filtered = list(self.state.rows)
        if keep_ref:
            key = keep_ref.strip().lower()
            for i, row in enumerate(self.state.filtered):
                if row.kind != "mcp" or not row.server:
                    continue
                refs = {
                    str(row.server.get("ref") or "").lower(),
                    str(row.server.get("id") or "").lower(),
                    str(row.server.get("name") or "").lower(),
                }
                if key in refs:
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
        cur = self._current_server()
        keep = str((cur or {}).get("ref") or "") if cur else None
        self._rebuild_rows(keep_ref=keep)
        self._invalidate()

    def _current_server(self) -> dict[str, Any] | None:
        rows = self.state.filtered
        if not rows:
            return None
        idx = max(0, min(self.state.index, len(rows) - 1))
        row = rows[idx]
        if row.kind != "mcp":
            return None
        return row.server

    def _move(self, delta: int) -> None:
        rows = self.state.filtered
        if not rows:
            return
        n = len(rows)
        i = self.state.index
        for _ in range(n):
            i = (i + delta) % n
            if rows[i].kind == "mcp":
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
        if rows[idx].kind != "mcp":
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
        servers = collect_mcp_for_modal(self.terminal)
        enabled_count = len([row for row in servers if row.get("enabled")])
        self.state = _McpModalState(
            servers=servers,
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
        """Toggle enable/disable for the highlighted server (stay open)."""
        server = self._current_server()
        if not self.state.open or server is None:
            return
        ref = str(server.get("ref") or server.get("id") or "").strip()
        if not ref:
            return
        new_enabled = not bool(server.get("enabled"))
        result = set_mcp_enabled(ref, new_enabled)
        if not result.get("ok"):
            # Surface soft failure in the status strip via description flash.
            server["description"] = str(result.get("summary") or "Toggle failed")
            self._rebuild_rows(keep_ref=ref)
            self._invalidate()
            return
        servers = collect_mcp_for_modal(self.terminal)
        self.state.servers = servers
        self.state.enabled_count = len([s for s in servers if s.get("enabled")])
        self._rebuild_rows(keep_ref=ref)
        self._invalidate()

    def confirm(self) -> None:
        """Insert ``mcp: <id>`` into compose and close."""
        server = self._current_server()
        if not self.state.open or server is None:
            return
        self.state.open = False
        self._on_style_refresh()
        self._focus_compose()
        insert_mcp_into_compose(self.terminal, server)
        self._invalidate()

    def cancel(self) -> None:
        if not self.state.open:
            return
        self.state.open = False
        self._on_style_refresh()
        self._focus_compose()
        self._invalidate()


def run_mcp_modal(terminal: Any) -> bool:
    """Open MCP UI. Prefers in-app overlay; nested fullscreen is fallback."""
    import os
    import sys

    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False

    host = getattr(terminal, "_mcp_modal_host", None)
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
        styles.update(mcp_modal_style_extras(colors))
        styles = dim_transcript_styles_for_backdrop(styles)
        nested.style = Style.from_dict(styles)
        try:
            nested.invalidate()
        except Exception:  # noqa: BLE001
            pass

    canvas = Window(char=" ", style="class:mcp-dialog")
    root = FloatContainer(content=canvas, floats=[])
    nested_app = Application(
        layout=Layout(root),
        key_bindings=KeyBindings(),
        full_screen=True,
        mouse_support=True,
        color_depth=ColorDepth.TRUE_COLOR,
    )
    held["app"] = nested_app
    host = McpModalHost(
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
