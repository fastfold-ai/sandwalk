"""In-app /models modal: search, favorites, enable (Space), arrows, Esc.

Centered Float over the live transcript (same chrome as /themes).
Lists all catalog models (including disabled) to match Dashboard → Models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from ui.terminal.model_options import (
    collect_model_options,
    is_current_option,
    option_pref_key,
)
from ui.terminal.themes_modal import (
    dim_transcript_styles_for_backdrop,
    themes_modal_style_extras,
)

DIALOG_WIDTH = 64
PAD_X = 3  # left/right inset
# top + title + search + gap + list + gap + status + hints + bottom
LIST_HEIGHT = 25
DIALOG_HEIGHT = 8 + LIST_HEIGHT


@dataclass
class _ModelRow:
    kind: str  # "header" | "model"
    title: str
    option: dict | None = None
    search: str = ""
    context: str = ""  # e.g. "1M", "200k"
    effort: str = ""  # e.g. "Medium", "Low · Fast"
    meta: str = ""  # right-aligned fallback (provider) when no effort
    favorite: bool = False
    enabled: bool = True


@dataclass
class _ModelsModalState:
    options: list[dict] = field(default_factory=list)
    rows: list[_ModelRow] = field(default_factory=list)
    filtered: list[_ModelRow] = field(default_factory=list)
    index: int = 0
    query: str = ""
    open: bool = False
    scroll: int = 0
    current_model: str = ""
    current_provider: str = ""
    provider_label: str = ""
    provider_endpoint: str = ""
    active_profile_id: str | None = None
    active_backend: str = ""
    warnings: list[str] = field(default_factory=list)


def format_context_window_label(tokens: int | None) -> str:
    """Compact context badge: ``1M``, ``1.05M``, ``200k``."""
    if tokens is None or tokens <= 0:
        return ""
    n = int(tokens)
    if n >= 1_000_000:
        millions = n / 1_000_000
        if millions >= 10 or float(millions).is_integer():
            return f"{int(round(millions))}M"
        return f"{millions:.2f}".rstrip("0").rstrip(".") + "M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k".replace(".0k", "k")
    return str(n)


def _effort_label_for_option(opt: dict, cfg: Any | None) -> str:
    """Default/stored Effort · Fast label when the model supports it."""
    if cfg is None:
        return ""
    from agent.model_catalog import selected_reasoning_effort_label

    mid = str(opt.get("model_id") or "").strip()
    prov = str(opt.get("provider") or "").strip().lower()
    backend = str(opt.get("backend") or "").strip().lower() or None
    check_provider = "openai" if prov == "local" else prov
    if check_provider == "openai" and backend == "unsloth":
        check_provider = "local"
    try:
        store = cfg.get("llm.model_reasoning")
        default_effort = str(cfg.get("llm.reasoning_effort") or "medium")
        default_fast = bool(cfg.get("llm.reasoning_fast", False))
    except Exception:  # noqa: BLE001
        return ""
    label = selected_reasoning_effort_label(
        store,
        check_provider,
        mid,
        default_effort=default_effort,
        default_fast=default_fast,
        compatible_backend=backend if prov == "local" else None,
    )
    return str(label or "").strip()


def _context_label_for_option(opt: dict) -> str:
    from agent.model_catalog import context_window_for_model

    mid = str(opt.get("model_id") or "").strip()
    return format_context_window_label(context_window_for_model(mid))


def build_model_rows(
    options: list[dict],
    *,
    favorite_keys: list[str],
    recent_keys: list[str],
    query: str = "",
    config: Any | None = None,
) -> list[_ModelRow]:
    """Sectioned rows: Favorites → Recent → rest (by provider label)."""
    fav_set = set(favorite_keys)
    q = (query or "").strip().lower()

    def matches(opt: dict) -> bool:
        if not q:
            return True
        blob = " ".join(
            [
                str(opt.get("display") or ""),
                str(opt.get("model_id") or ""),
                str(opt.get("provider") or ""),
                str(opt.get("provider_label") or ""),
                str(opt.get("profile_id") or ""),
                str(opt.get("backend") or ""),
                _context_label_for_option(opt),
                _effort_label_for_option(opt, config),
            ]
        ).lower()
        return q in blob

    by_key = {option_pref_key(opt): opt for opt in options}
    matched = [opt for opt in options if matches(opt)]
    matched_keys = {option_pref_key(opt) for opt in matched}

    rows: list[_ModelRow] = []

    def add_section(title: str, keys: list[str]) -> None:
        section_opts = []
        for key in keys:
            if key not in matched_keys:
                continue
            opt = by_key.get(key)
            if opt is not None:
                section_opts.append(opt)
        if not section_opts:
            return
        rows.append(_ModelRow(kind="header", title=title, search=title.lower()))
        for opt in section_opts:
            rows.append(
                _row_for_option(
                    opt, favorite=option_pref_key(opt) in fav_set, config=config
                )
            )

    add_section("Favorites", favorite_keys)
    # Recent excludes keys already shown under Favorites.
    recent_only = [k for k in recent_keys if k not in fav_set]
    add_section("Recent", recent_only)

    # Provider sections list every matched model — Favorites/Recent are
    # shortcuts only and must not remove entries from the catalog.
    from ui.terminal.model_options import provider_display_label

    groups: dict[str, list[dict]] = {}
    group_titles: dict[str, str] = {}
    for opt in matched:
        raw = str(opt.get("provider_label") or opt.get("provider") or "Models")
        title = provider_display_label(
            str(opt.get("provider") or ""), fallback=raw
        )
        key = title.casefold()
        groups.setdefault(key, []).append(opt)
        group_titles.setdefault(key, title)
    for key in sorted(groups.keys()):
        label = group_titles[key]
        rows.append(_ModelRow(kind="header", title=label, search=label.lower()))
        for opt in groups[key]:
            rows.append(
                _row_for_option(
                    opt, favorite=option_pref_key(opt) in fav_set, config=config
                )
            )

    return rows


def _row_for_option(
    opt: dict, *, favorite: bool, config: Any | None = None
) -> _ModelRow:
    from ui.terminal.model_options import provider_display_label

    display = str(opt.get("display") or opt.get("model_id") or "")
    meta = provider_display_label(
        str(opt.get("provider") or ""),
        fallback=str(opt.get("provider_label") or opt.get("provider") or ""),
    )
    context = _context_label_for_option(opt)
    effort = _effort_label_for_option(opt, config)
    title = display
    search = " ".join(
        [
            display,
            str(opt.get("model_id") or ""),
            str(opt.get("provider") or ""),
            meta,
            context,
            effort,
            str(opt.get("profile_id") or ""),
        ]
    )
    return _ModelRow(
        kind="model",
        title=title,
        option=opt,
        search=search,
        context=context,
        effort=effort,
        meta=meta,
        favorite=favorite,
        enabled=bool(opt.get("enabled", True)),
    )


def filter_model_rows(rows: list[_ModelRow], query: str) -> list[_ModelRow]:
    """Rebuild is preferred; kept for tests on plain lists."""
    q = (query or "").strip().lower()
    if not q:
        return list(rows)
    out: list[_ModelRow] = []
    pending_header: _ModelRow | None = None
    for row in rows:
        if row.kind == "header":
            pending_header = row
            continue
        if q in row.search.lower() or q in row.title.lower():
            if pending_header is not None:
                out.append(pending_header)
                pending_header = None
            out.append(row)
    return out


def first_selectable_index(rows: list[_ModelRow], start: int = 0) -> int:
    if not rows:
        return 0
    n = len(rows)
    i = max(0, min(start, n - 1))
    for _ in range(n):
        if rows[i].kind == "model":
            return i
        i = (i + 1) % n
    return 0


def models_modal_style_extras(colors: dict[str, str]) -> dict[str, str]:
    """Mirror themes modal chrome under models-* class names."""
    base = themes_modal_style_extras(colors)
    out = {k.replace("themes-", "models-", 1): v for k, v in base.items()}
    # Section headers (Favorites / Recent / provider).
    muted = colors["muted_fg"]
    panel = colors["panel_bg"]
    accent = colors["accent"]
    out["models-section"] = f"bg:{panel} {accent} bold"
    out["models-meta"] = f"bg:{panel} {muted}"
    out["models-meta-selected"] = out.get(
        "models-row-selected", f"bg:{accent} bold"
    )
    out["models-context"] = f"bg:{panel} {muted}"
    out["models-context-selected"] = out.get(
        "models-row-selected", f"bg:{accent} bold"
    )
    # Disabled catalog rows (space to enable) — muted like skills ○.
    out["models-row-disabled"] = f"bg:{panel} {muted}"
    return out


class ModelsModalHost:
    """In-app models overlay hosted by the transcript FloatContainer."""

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
        self.state = _ModelsModalState()
        self._list_viewport_h = LIST_HEIGHT
        self.search_buf = Buffer(name="models-search", multiline=False)
        self.search_buf.on_text_changed += self._on_search_text

        host = self
        self.is_open = Condition(lambda: host.state.open)

        class _ModelListControl(UIControl):
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
                        return [("class:models-row", " " * width)]
                    row = rows[abs_i]
                    inset = " " * PAD_X
                    if row.kind == "header":
                        label = f"{inset}{row.title}"
                        pad = " " * max(0, width - len(label))
                        return [("class:models-section", f"{label}{pad}")]
                    selected = abs_i == st.index
                    opt = row.option or {}
                    enabled = bool(getattr(row, "enabled", True))
                    is_current = is_current_option(
                        opt,
                        current_model=st.current_model,
                        current_provider=st.current_provider,
                        active_profile_id=st.active_profile_id,
                        active_backend=st.active_backend,
                    )
                    if selected:
                        style = "class:models-row-selected"
                    elif not enabled:
                        style = "class:models-row-disabled"
                    else:
                        style = "class:models-row"
                    # One-char gutter: ★ favorite · ● current · ○ disabled · blank.
                    if row.favorite:
                        gutter = "★"
                    elif not enabled:
                        gutter = "○"
                    elif is_current:
                        gutter = "●"
                    else:
                        gutter = " "
                    gutter_style = (
                        "class:models-row-selected"
                        if selected
                        else (
                            "class:models-row-disabled"
                            if not enabled
                            else "class:models-row-current"
                        )
                    )
                    # Warp-like: name + context on left; effort/provider on right.
                    # Favorites always keep the provider so ★ rows stay unambiguous
                    # when the same display name exists under multiple providers.
                    if row.favorite and row.meta and row.effort:
                        right_label = f"{row.meta} · {row.effort}"
                    elif row.favorite and row.meta:
                        right_label = row.meta
                    else:
                        right_label = row.effort or row.meta
                    right_style = (
                        "class:models-meta-selected"
                        if selected
                        else "class:models-meta"
                    )
                    ctx_style = (
                        "class:models-context-selected"
                        if selected
                        else "class:models-context"
                    )
                    right = f"{right_label}{inset}" if right_label else inset
                    prefix = f"{inset}{gutter} "
                    ctx = f" {row.context}" if row.context else ""
                    room = max(1, width - len(prefix) - len(ctx) - len(right))
                    title = row.title
                    if len(title) > room:
                        title = title[: room - 1] + "…"
                    pad = " " * max(
                        0, width - len(prefix) - len(title) - len(ctx) - len(right)
                    )
                    return [
                        (gutter_style, prefix),
                        (style, title),
                        (ctx_style, ctx),
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
            content=_ModelListControl(),
            height=Dimension.exact(LIST_HEIGHT),
            dont_extend_height=True,
            style="class:models-dialog",
        )

        def _side_pad():
            return Window(
                width=PAD_X, char=" ", style="class:models-dialog", dont_extend_width=True
            )

        # Title left + esc pinned top-right (space-between), with side insets.
        header = VSplit(
            [
                _side_pad(),
                Window(
                    content=FormattedTextControl(
                        lambda: [("class:models-title", "Select model")]
                    ),
                    dont_extend_width=True,
                    style="class:models-dialog",
                ),
                Window(char=" ", style="class:models-dialog"),
                Window(
                    content=FormattedTextControl(
                        lambda: [("class:models-hint", "esc")]
                    ),
                    width=3,
                    dont_extend_width=True,
                    style="class:models-dialog",
                ),
                _side_pad(),
            ],
            height=1,
            style="class:models-dialog",
        )

        search = VSplit(
            [
                _side_pad(),
                Window(
                    width=7,
                    content=FormattedTextControl(
                        lambda: [("class:models-search.prompt", "Search ")]
                    ),
                    style="class:models-search",
                ),
                Window(
                    content=BufferControl(buffer=self.search_buf, focusable=True),
                    height=1,
                    style="class:models-search",
                ),
                _side_pad(),
            ],
            height=1,
            style="class:models-search",
        )

        status = VSplit(
            [
                _side_pad(),
                Window(
                    content=FormattedTextControl(self._status_strip),
                    height=1,
                    style="class:models-preview",
                ),
                _side_pad(),
            ],
            height=1,
            style="class:models-preview",
        )

        hints = VSplit(
            [
                _side_pad(),
                Window(
                    content=FormattedTextControl(
                        lambda: [
                            (
                                "class:models-hint",
                                "↑/↓ · enter confirm · space enable · ctrl+f favorite",
                            )
                        ]
                    ),
                    height=1,
                    style="class:models-dialog",
                ),
                _side_pad(),
            ],
            height=1,
            style="class:models-dialog",
        )

        dialog = HSplit(
            [
                Window(height=1, char=" ", style="class:models-dialog"),
                header,
                search,
                Window(height=1, char=" ", style="class:models-dialog"),
                list_window,
                Window(height=1, char=" ", style="class:models-dialog"),
                status,
                hints,
                Window(height=1, char=" ", style="class:models-dialog"),
            ],
            width=Dimension.exact(DIALOG_WIDTH),
            height=Dimension.exact(DIALOG_HEIGHT),
            style="class:models-dialog",
        )

        with_shadow = HSplit(
            [
                VSplit(
                    [
                        dialog,
                        Window(width=1, char=" ", style="class:models-shadow"),
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
                            style="class:models-shadow",
                        ),
                    ],
                    height=1,
                ),
            ],
            width=Dimension.exact(DIALOG_WIDTH + 1),
            height=Dimension.exact(DIALOG_HEIGHT + 1),
            style="class:models-dialog",
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
        def _space(_event):
            host.toggle_enabled()

        @self.key_bindings.add("c-f", filter=self.is_open, eager=True)
        def _fav(_event):
            host.toggle_favorite()

        @self.key_bindings.add("escape", filter=self.is_open, eager=True)
        @self.key_bindings.add("c-c", filter=self.is_open, eager=True)
        def _esc(_event):
            host.cancel()

    def _status_strip(self):
        st = self.state
        label = st.provider_label or st.current_provider or "—"
        endpoint = st.provider_endpoint or ""
        # Leave room for side pads already applied by the status VSplit.
        max_ep = max(12, DIALOG_WIDTH - PAD_X * 2 - 28)
        if len(endpoint) > max_ep:
            endpoint = endpoint[: max_ep - 1] + "…"
        bits = [st.current_model or "—", label]
        if endpoint:
            bits.append(endpoint)
        text = " · ".join(bits)
        return [
            ("class:models-preview-accent", "┃"),
            ("class:models-preview-panel", f" {text}"),
        ]

    def _cfg(self):
        return self.terminal.session.config

    def _rebuild_rows(self, *, keep_key: str | None = None) -> None:
        from agent.config import Config

        cfg = self._cfg()
        favs = cfg.favorite_models() if isinstance(cfg, Config) else []
        recent = cfg.recent_models() if isinstance(cfg, Config) else []
        self.state.rows = build_model_rows(
            self.state.options,
            favorite_keys=favs,
            recent_keys=recent,
            query=self.state.query,
            config=cfg if isinstance(cfg, Config) else None,
        )
        self.state.filtered = list(self.state.rows)
        if keep_key:
            for i, row in enumerate(self.state.filtered):
                if row.kind == "model" and row.option and option_pref_key(row.option) == keep_key:
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
        cur = self._current_option()
        keep = option_pref_key(cur) if cur else None
        self._rebuild_rows(keep_key=keep)
        self._invalidate()

    def _current_option(self) -> dict | None:
        rows = self.state.filtered
        if not rows:
            return None
        idx = max(0, min(self.state.index, len(rows) - 1))
        row = rows[idx]
        if row.kind != "model":
            return None
        return row.option

    def _move(self, delta: int) -> None:
        rows = self.state.filtered
        if not rows:
            return
        n = len(rows)
        i = self.state.index
        for _ in range(n):
            i = (i + delta) % n
            if rows[i].kind == "model":
                self.state.index = i
                self._invalidate()
                return

    def _scroll_by(self, delta: int) -> None:
        """Mouse-wheel viewport scroll (does not wrap)."""
        rows = self.state.filtered
        if not rows:
            return
        vh = max(1, int(getattr(self, "_list_viewport_h", LIST_HEIGHT) or LIST_HEIGHT))
        max_scroll = max(0, len(rows) - vh)
        nxt = max(0, min(max_scroll, self.state.scroll + delta))
        if nxt == self.state.scroll:
            return
        self.state.scroll = nxt
        # Keep the highlight inside the visible window.
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
        if rows[idx].kind != "model":
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
        from agent.config import Config

        provider, provider_label, provider_endpoint = self.terminal._current_provider_status()
        cfg = self._cfg()
        options, warnings = collect_model_options(self.terminal)
        active_profile_id = None
        active_backend = ""
        if isinstance(cfg, Config):
            active_profile_id = cfg.active_openai_profile_id()
            profile = cfg.get_openai_profile(active_profile_id)
            active_backend = str((profile or {}).get("backend") or "").strip().lower()

        self.state = _ModelsModalState(
            options=options,
            warnings=warnings,
            current_model=str(self.terminal.session.current_model or ""),
            current_provider=str(provider or ""),
            provider_label=str(provider_label or ""),
            provider_endpoint=str(provider_endpoint or ""),
            active_profile_id=active_profile_id,
            active_backend=active_backend,
            open=True,
        )
        self.search_buf.reset()
        self._rebuild_rows()
        # Focus current model if present.
        for i, row in enumerate(self.state.filtered):
            if row.kind != "model" or not row.option:
                continue
            if is_current_option(
                row.option,
                current_model=self.state.current_model,
                current_provider=self.state.current_provider,
                active_profile_id=self.state.active_profile_id,
                active_backend=self.state.active_backend,
            ):
                self.state.index = i
                break
        try:
            self.app.layout.focus(self.search_buf)
        except Exception:  # noqa: BLE001
            pass
        self._invalidate()

    def toggle_favorite(self) -> None:
        from agent.config import Config

        opt = self._current_option()
        if not opt:
            return
        cfg = self._cfg()
        if not isinstance(cfg, Config):
            return
        cfg.toggle_model_favorite(
            str(opt.get("model_id") or ""),
            str(opt.get("provider") or ""),
            profile_id=str(opt.get("profile_id") or "").strip() or None,
        )
        try:
            cfg.save()
        except Exception:  # noqa: BLE001
            pass
        self.terminal.session.config = cfg
        self._rebuild_rows(keep_key=option_pref_key(opt))
        self._invalidate()

    def toggle_enabled(self) -> None:
        """Toggle enable/disable for the highlighted model (stay open)."""
        from agent.config import Config

        opt = self._current_option()
        if not self.state.open or not opt:
            return
        cfg = self._cfg()
        if not isinstance(cfg, Config):
            return
        model_id = str(opt.get("model_id") or "").strip()
        provider = str(opt.get("provider") or "").strip().lower()
        if not model_id:
            return
        new_enabled = not bool(opt.get("enabled", True))
        # Prefer provider-scoped keys (same as Dashboard PATCH /v1/models).
        hide_key = (
            cfg.provider_model_key(provider, model_id) if provider else model_id
        )
        cfg.set_model_hidden(hide_key, hidden=not new_enabled)
        if provider and new_enabled and model_id in set(cfg.hidden_models()):
            cfg.set_model_hidden(model_id, hidden=False)
        try:
            cfg.save()
        except Exception:  # noqa: BLE001
            pass
        self.terminal.session.config = cfg
        for item in self.state.options:
            mid = str(item.get("model_id") or "")
            prov = str(item.get("provider") or "")
            item["enabled"] = not cfg.is_model_hidden(mid, prov)
        self._rebuild_rows(keep_key=option_pref_key(opt))
        self._invalidate()

    def confirm(self) -> None:
        opt = self._current_option()
        if not self.state.open or not opt:
            return
        if not bool(opt.get("enabled", True)):
            # Keep open — space enables; do not silently switch to a hidden model.
            return
        apply = getattr(self.terminal, "_apply_model_selection", None)
        self.state.open = False
        self._on_style_refresh()
        self._focus_compose()
        if callable(apply):
            apply(opt)
        self._invalidate()

    def cancel(self) -> None:
        if not self.state.open:
            return
        self.state.open = False
        self._on_style_refresh()
        self._focus_compose()
        self._invalidate()


def run_models_modal(terminal: Any) -> bool:
    """Open models UI. Prefers in-app overlay; nested fullscreen is fallback."""
    import os
    import sys

    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False

    host = getattr(terminal, "_models_modal_host", None)
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
        styles.update(models_modal_style_extras(colors))
        styles = dim_transcript_styles_for_backdrop(styles)
        nested.style = Style.from_dict(styles)
        try:
            nested.invalidate()
        except Exception:  # noqa: BLE001
            pass

    canvas = Window(char=" ", style="class:models-dialog")
    root = FloatContainer(content=canvas, floats=[])
    nested_app = Application(
        layout=Layout(root),
        key_bindings=KeyBindings(),
        full_screen=True,
        mouse_support=True,
        color_depth=ColorDepth.TRUE_COLOR,
    )
    held["app"] = nested_app
    host = ModelsModalHost(
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
