"""In-app /effort modal: Low / Medium / High / Fast for the active model."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ui.terminal.themes_modal import (
    dim_transcript_styles_for_backdrop,
    themes_modal_style_extras,
)

DIALOG_WIDTH = 56
PAD_X = 3
LIST_HEIGHT = 8
DIALOG_HEIGHT = 7 + LIST_HEIGHT

EFFORT_OPTIONS = (
    ("low", False, "Low"),
    ("medium", False, "Medium"),
    ("high", False, "High"),
    ("low", True, "Fast (thinking off where supported)"),
)


@dataclass
class _EffortRow:
    kind: str  # "header" | "option"
    title: str
    effort: str = ""
    fast: bool = False
    search: str = ""


@dataclass
class _EffortModalState:
    rows: list[_EffortRow] = field(default_factory=list)
    filtered: list[_EffortRow] = field(default_factory=list)
    index: int = 0
    query: str = ""
    open: bool = False
    scroll: int = 0
    provider: str = ""
    model_id: str = ""
    display: str = ""
    current_label: str = ""


def effort_modal_style_extras(colors: dict[str, str]) -> dict[str, str]:
    base = themes_modal_style_extras(colors)
    out = {k.replace("themes-", "effort-", 1): v for k, v in base.items()}
    muted = colors["muted_fg"]
    panel = colors["panel_bg"]
    accent = colors["accent"]
    out["effort-section"] = f"bg:{panel} {accent} bold"
    out["effort-meta"] = f"bg:{panel} {muted}"
    out["effort-meta-selected"] = out.get("effort-row-selected", f"bg:{accent} bold")
    return out


def build_effort_rows(
    *,
    query: str = "",
    current_label: str = "",
    allow_fast: bool = True,
) -> list[_EffortRow]:
    rows = [
        _EffortRow(
            kind="header",
            title=f"Effort{f' · {current_label}' if current_label else ''}",
            search="effort",
        )
    ]
    for effort, fast, label in EFFORT_OPTIONS:
        if fast and not allow_fast:
            continue
        rows.append(
            _EffortRow(
                kind="option",
                title=label,
                effort=effort,
                fast=fast,
                search=label.lower(),
            )
        )
    q = (query or "").strip().lower()
    if not q:
        return rows
    out: list[_EffortRow] = []
    header = rows[0]
    for row in rows[1:]:
        if q in row.search or q in row.title.lower():
            if not out:
                out.append(header)
            out.append(row)
    return out


def first_selectable_index(rows: list[_EffortRow], start: int = 0) -> int:
    if not rows:
        return 0
    n = len(rows)
    i = max(0, min(start, n - 1))
    for _ in range(n):
        if rows[i].kind == "option":
            return i
        i = (i + 1) % n
    return 0


def resolve_effort_context(terminal: Any) -> tuple[Any, str, str, str] | None:
    """Return (cfg, store_provider, model_id, display) or None if unsupported."""
    from agent.config import Config

    cfg = getattr(getattr(terminal, "session", None), "config", None) or Config.load()
    mixin = terminal
    provider = str(
        getattr(getattr(terminal, "session", None), "current_provider", None)
        or cfg.get("llm.provider")
        or "openai"
    ).strip().lower()
    model_id = str(
        getattr(getattr(terminal, "session", None), "current_model", None)
        or cfg.get("llm.model")
        or ""
    ).strip()
    check_provider = provider
    if provider == "openai" and hasattr(mixin, "_compatible_backend_for_effort"):
        backend = mixin._compatible_backend_for_effort(cfg, "local")
        check_provider = "local" if backend == "unsloth" else "openai"
    if not model_id:
        return None
    supports = getattr(mixin, "_model_supports_effort_ui", None)
    if callable(supports) and not supports(cfg, check_provider, model_id):
        return None
    return cfg, check_provider, model_id, model_id


def apply_effort_choice(
    cfg: Any, *, provider: str, model_id: str, effort: str, fast: bool
) -> str:
    from agent.model_catalog import (
        format_reasoning_effort_label,
        normalize_reasoning_effort,
        upsert_model_reasoning,
    )

    store_provider = str(provider or "").strip().lower() or "openai"
    next_store = upsert_model_reasoning(
        cfg.get("llm.model_reasoning"),
        store_provider,
        model_id,
        effort=normalize_reasoning_effort(effort, allow_none=False),
        fast=fast,
    )
    cfg.set("llm.model_reasoning", next_store)
    cfg.save()
    return format_reasoning_effort_label(effort=effort, fast=fast)


class EffortModalHost:
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
        self.state = _EffortModalState()
        self.search_buf = Buffer(name="effort-search", multiline=False)
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
                        return [("class:effort-row", " " * width)]
                    row = rows[abs_i]
                    inset = " " * PAD_X
                    if row.kind == "header":
                        label = f"{inset}{row.title}"
                        pad = " " * max(0, width - len(label))
                        return [("class:effort-section", f"{label}{pad}")]
                    selected = abs_i == st.index
                    style = (
                        "class:effort-row-selected" if selected else "class:effort-row"
                    )
                    mark = "● " if selected else "  "
                    label = f"{inset}{mark}{row.title}"
                    pad = " " * max(0, width - len(label))
                    return [(style, f"{label}{pad}")]

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
                width=PAD_X, char=" ", style="class:effort-dialog", dont_extend_width=True
            )

        list_window = Window(
            content=_ListControl(),
            height=Dimension.exact(LIST_HEIGHT),
            style="class:effort-dialog",
        )
        header = VSplit(
            [
                _side_pad(),
                Window(
                    content=FormattedTextControl(
                        lambda: [("class:effort-title", "Effort")]
                    ),
                    dont_extend_width=True,
                    style="class:effort-dialog",
                ),
                Window(char=" ", style="class:effort-dialog"),
                Window(
                    content=FormattedTextControl(
                        lambda: [("class:effort-hint", "esc")]
                    ),
                    width=3,
                    style="class:effort-dialog",
                ),
                _side_pad(),
            ],
            height=1,
            style="class:effort-dialog",
        )
        search = VSplit(
            [
                _side_pad(),
                Window(
                    width=7,
                    content=FormattedTextControl(
                        lambda: [("class:effort-search.prompt", "Search ")]
                    ),
                    style="class:effort-search",
                ),
                Window(
                    content=BufferControl(buffer=self.search_buf, focusable=True),
                    height=1,
                    style="class:effort-search",
                ),
                _side_pad(),
            ],
            height=1,
            style="class:effort-search",
        )
        hints = VSplit(
            [
                _side_pad(),
                Window(
                    content=FormattedTextControl(
                        lambda: [
                            ("class:effort-hint", "↑/↓ · enter apply · esc")
                        ]
                    ),
                    height=1,
                    style="class:effort-dialog",
                ),
                _side_pad(),
            ],
            height=1,
            style="class:effort-dialog",
        )
        dialog = HSplit(
            [
                Window(height=1, char=" ", style="class:effort-dialog"),
                header,
                search,
                Window(height=1, char=" ", style="class:effort-dialog"),
                list_window,
                Window(height=1, char=" ", style="class:effort-dialog"),
                hints,
                Window(height=1, char=" ", style="class:effort-dialog"),
            ],
            width=Dimension.exact(DIALOG_WIDTH),
            height=Dimension.exact(DIALOG_HEIGHT),
            style="class:effort-dialog",
        )
        with_shadow = HSplit(
            [
                VSplit(
                    [
                        dialog,
                        Window(width=1, char=" ", style="class:effort-shadow"),
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
                            style="class:effort-shadow",
                        ),
                    ],
                    height=1,
                ),
            ],
            width=Dimension.exact(DIALOG_WIDTH + 1),
            height=Dimension.exact(DIALOG_HEIGHT + 1),
            style="class:effort-dialog",
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

        @self.key_bindings.add("escape", filter=self.is_open, eager=True)
        @self.key_bindings.add("c-c", filter=self.is_open, eager=True)
        def _esc(_e):
            host.cancel()

    def _rebuild_rows(self) -> None:
        from agent.model_catalog import model_supports_reasoning_fast

        allow_fast = model_supports_reasoning_fast(
            self.state.provider, self.state.model_id
        )
        self.state.rows = build_effort_rows(
            query=self.state.query,
            current_label=self.state.current_label,
            allow_fast=allow_fast,
        )
        self.state.filtered = list(self.state.rows)
        self.state.index = first_selectable_index(self.state.filtered)
        self.state.scroll = 0

    def _on_search_text(self, _buf) -> None:
        if not self.state.open:
            return
        self.state.query = self.search_buf.text
        self._rebuild_rows()
        self._invalidate()

    def _current(self) -> _EffortRow | None:
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
        from agent.model_catalog import (
            format_reasoning_effort_label,
            get_model_reasoning,
        )

        ctx = resolve_effort_context(self.terminal)
        if ctx is None:
            console = getattr(self.terminal, "console", None)
            if console is not None:
                console.print(
                    "  [dim]Active model does not support Effort / thinking controls.[/dim]"
                )
            return
        cfg, provider, model_id, display = ctx
        effort, fast = get_model_reasoning(
            cfg.get("llm.model_reasoning"),
            provider,
            model_id,
            default_effort=str(cfg.get("llm.reasoning_effort") or "medium"),
            default_fast=bool(cfg.get("llm.reasoning_fast", False)),
        )
        self.state = _EffortModalState(
            open=True,
            provider=provider,
            model_id=model_id,
            display=display,
            current_label=format_reasoning_effort_label(effort=effort, fast=fast),
        )
        self.search_buf.reset()
        self._rebuild_rows()
        try:
            self.app.layout.focus(self.search_buf)
        except Exception:  # noqa: BLE001
            pass
        self._invalidate()

    def confirm(self) -> None:
        from agent.config import Config

        row = self._current()
        if not self.state.open or row is None:
            return
        cfg = getattr(getattr(self.terminal, "session", None), "config", None) or Config.load()
        shown = apply_effort_choice(
            cfg,
            provider=self.state.provider,
            model_id=self.state.model_id,
            effort=row.effort,
            fast=row.fast,
        )
        sess = getattr(self.terminal, "session", None)
        if sess is not None:
            sess.config = cfg
        self.state.open = False
        self._on_style_refresh()
        self._focus_compose()
        self._invalidate()
        console = getattr(self.terminal, "console", None)
        if console is not None:
            console.print(f"  [green]Effort →[/green] {shown}")

    def cancel(self) -> None:
        if not self.state.open:
            return
        self.state.open = False
        self._on_style_refresh()
        self._focus_compose()
        self._invalidate()


def run_effort_modal(terminal: Any) -> bool:
    import os
    import sys

    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    host = getattr(terminal, "_effort_modal_host", None)
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
        styles.update(effort_modal_style_extras(colors))
        styles = dim_transcript_styles_for_backdrop(styles)
        nested.style = Style.from_dict(styles)
        try:
            nested.invalidate()
        except Exception:  # noqa: BLE001
            pass

    canvas = Window(char=" ", style="class:effort-dialog")
    root = FloatContainer(content=canvas, floats=[])
    nested_app = Application(
        layout=Layout(root),
        key_bindings=KeyBindings(),
        full_screen=True,
        mouse_support=True,
        color_depth=ColorDepth.TRUE_COLOR,
    )
    held["app"] = nested_app
    host = EffortModalHost(
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
    if not host.state.open:
        return False
    try:
        return bool(nested_app.run())
    except Exception:  # noqa: BLE001
        return False
