"""prompt_toolkit Application: scrollable transcript + input + toolbar."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.filters import Condition
from prompt_toolkit.history import History
from prompt_toolkit.key_binding import KeyBindings, merge_key_bindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import (
    Float,
    FloatContainer,
    HSplit,
    VSplit,
    Window,
)
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.styles import merge_styles

from ui.terminal.attach_lexer import AttachChipLexer
from ui.terminal.completion import ComposeCompletionsMenu, PT_STYLE
from ui.terminal.theme import (
    resolve_ui_palette,
    resolve_ui_theme,
    transcript_style_dict,
)
from ui.terminal.transcript.control import TranscriptControl

# Cursor OSC color (Warp/VT100); matches sandwalk green accent.
_COMPOSE_CURSOR = "#50fa7b"

# Match compose_block: [outer 2][accent ┃ 1][panel …][outer 2].
# Menu float includes the accent column so the ┃ continues into the menu.
_COMPOSE_OUTER = 2
_COMPOSE_BOX_LEFT = _COMPOSE_OUTER  # 2 — accent ┃ is first column of the menu
_COMPOSE_BOX_RIGHT = _COMPOSE_OUTER

# Coalesce store/toolbar invalidates so Rich re-renders can't pin the UI.
_INVALIDATE_MIN_INTERVAL_S = 0.05


def _merge_style(config=None, *, backdrop_dim: bool = False):
    from prompt_toolkit.styles import Style

    theme = resolve_ui_theme(config)
    palette = resolve_ui_palette(config)
    styles = transcript_style_dict(theme, palette=palette, config=config)
    if backdrop_dim:
        from ui.terminal.themes_modal import dim_transcript_styles_for_backdrop

        styles = dim_transcript_styles_for_backdrop(styles)
    return merge_styles(
        [
            PT_STYLE,
            Style.from_dict(styles),
        ]
    )


def _theme_fingerprint(config=None, *, backdrop_dim: bool = False) -> tuple[str, str, bool]:
    return (resolve_ui_theme(config), resolve_ui_palette(config), backdrop_dim)


def run_transcript_session(
    terminal,
    *,
    history: History | None = None,
    on_submit: Callable[[str], bool],
) -> None:
    """Run one persistent fullscreen transcript until ``on_submit`` returns False.

    Returning False from ``on_submit`` exits the session (e.g. /quit). Raising
    ``EOFError`` from Ctrl+D with an empty buffer also ends the session.
    """
    store = terminal.transcript
    config = getattr(getattr(terminal, "session", None), "config", None)
    control = TranscriptControl(store, config=config)

    buf = Buffer(
        completer=getattr(terminal, "_merged_completer", None),
        complete_while_typing=True,
        history=history,
        multiline=False,
        name="input",
    )

    def _meta():
        return terminal._compose_meta_toolbar()

    def _status():
        return terminal._compose_status_toolbar()

    transcript_window = Window(
        content=control,
        height=Dimension(weight=1),
        wrap_lines=False,
        dont_extend_height=False,
        allow_scroll_beyond_bottom=False,
        style="class:transcript-root",
    )
    control.window = transcript_window

    # One soft panel wraps input + meta + pads; path/context sit below.
    compose_input = Window(
        BufferControl(
            buffer=buf,
            lexer=AttachChipLexer(
                file_chips=lambda: list(
                    getattr(terminal, "_file_attach_map", {}) or {}
                )
            ),
            focusable=True,
        ),
        height=Dimension(min=1, max=6),
        wrap_lines=True,
        dont_extend_height=True,
        style="class:transcript-compose",
    )

    def _hpad(width: int = 2) -> Window:
        return Window(
            width=width,
            char=" ",
            style="class:transcript-compose",
        )

    def _vpad(height: int = 1) -> Window:
        # Exact height — plain height=1 spacers were collapsing in practice.
        return Window(
            height=Dimension.exact(height),
            char=" ",
            style="class:transcript-compose",
            dont_extend_height=True,
        )

    # Style every row so the panel fill is continuous (incl. meta + pads).
    compose_panel = HSplit(
        [
            _vpad(1),
            VSplit([_hpad(2), compose_input, _hpad(2)], padding=0),
            _vpad(1),
            VSplit(
                [
                    _hpad(2),
                    Window(
                        FormattedTextControl(_meta),
                        height=Dimension.exact(1),
                        dont_extend_height=True,
                        style="class:transcript-compose",
                    ),
                    _hpad(2),
                ],
                padding=0,
            ),
            _vpad(1),  # bottom inset under meta
        ],
        padding=0,
        style="class:transcript-compose",
    )
    status_bar = VSplit(
        [
            # Align under panel text (gold bar is outside the gray box).
            Window(width=2, char=" ", style="class:transcript-root"),
            Window(
                FormattedTextControl(_status),
                height=1,
                dont_extend_height=True,
                style="class:transcript-status",
            ),
            Window(width=2, char=" ", style="class:transcript-root"),
        ],
        padding=0,
        style="class:transcript-root",
    )

    def _outer(width: int = 2) -> Window:
        # Margin outside the soft panel — keep off the terminal edge.
        return Window(width=width, char=" ", style="class:transcript-root")

    # Gold bar sits left of the gray panel (outside the box), slightly heavier ┃.
    compose_block = VSplit(
        [
            _outer(),
            Window(
                width=1,
                char="┃",
                style="class:transcript-compose-accent",
            ),
            compose_panel,
            _outer(),
        ],
        padding=0,
        style="class:transcript-root",
    )
    status_block = VSplit(
        [
            _outer(),
            Window(width=1, char=" ", style="class:transcript-root"),
            status_bar,
            _outer(),
        ],
        padding=0,
        style="class:transcript-root",
    )

    root = FloatContainer(
        content=HSplit(
            [
                transcript_window,
                Window(height=1, style="class:transcript-root"),
                compose_block,
                status_block,
            ],
            style="class:transcript-root",
        ),
        floats=[
            Float(
                # Full compose-panel width, flush with accent ┃ borderline.
                left=_COMPOSE_BOX_LEFT,
                right=_COMPOSE_BOX_RIGHT,
                ycursor=True,
                content=ComposeCompletionsMenu(max_height=12, scroll_offset=1, lift=1),
            )
        ],
    )

    kb = _build_transcript_bindings(terminal, store, control, buf, on_submit)

    from prompt_toolkit.output.color_depth import ColorDepth

    theme_state = {"fp": _theme_fingerprint(config)}

    app = Application(
        layout=Layout(root, focused_element=buf),
        key_bindings=kb,
        style=_merge_style(config),
        # Soft panels need 24-bit color (light #f5f5f5 / dark #2a2a2e).
        color_depth=ColorDepth.TRUE_COLOR,
        full_screen=True,
        mouse_support=True,
        erase_when_done=False,
    )
    terminal._transcript_app = app

    invalidate_lock = threading.Lock()
    invalidate_state = {"last": 0.0, "pending": False}

    def _sync_theme_style(*, force: bool = False) -> None:
        """Refresh panel colors when OS appearance or /themes selection changes."""
        from ui.terminal.theme import clear_appearance_cache

        # Avoid OSC 11 spam inside the fullscreen app; env + macOS are enough live.
        if not force:
            clear_appearance_cache()
        # Reload config so /themes writes are visible without restart.
        live_cfg = config
        try:
            sess = getattr(terminal, "session", None)
            if sess is not None and getattr(sess, "config", None) is not None:
                live_cfg = sess.config
        except Exception:  # noqa: BLE001
            pass
        themes_host = getattr(terminal, "_themes_modal_host", None)
        models_host = getattr(terminal, "_models_modal_host", None)
        dim = bool(
            (themes_host is not None and getattr(themes_host.state, "open", False))
            or (models_host is not None and getattr(models_host.state, "open", False))
        )
        fp = _theme_fingerprint(live_cfg, backdrop_dim=dim)
        if not force and fp == theme_state["fp"]:
            return
        theme_state["fp"] = fp
        try:
            app.style = _merge_style(live_cfg, backdrop_dim=dim)
        except Exception:  # noqa: BLE001
            pass

    def _force_theme_refresh() -> None:
        _sync_theme_style(force=True)
        try:
            if app.is_running:
                app.invalidate()
        except Exception:  # noqa: BLE001
            pass

    terminal._ui_theme_refresh = _force_theme_refresh

    # In-app /themes and /models overlays (centered dialogs over live transcript).
    from ui.terminal.models_modal import ModelsModalHost
    from ui.terminal.themes_modal import ThemesModalHost

    def _focus_compose() -> None:
        try:
            app.layout.focus(buf)
        except Exception:  # noqa: BLE001
            pass

    themes_host = ThemesModalHost(
        terminal,
        app=app,
        on_style_refresh=_force_theme_refresh,
        focus_compose=_focus_compose,
    )
    models_host = ModelsModalHost(
        terminal,
        app=app,
        on_style_refresh=_force_theme_refresh,
        focus_compose=_focus_compose,
    )
    terminal._themes_modal_host = themes_host
    terminal._models_modal_host = models_host
    root.floats.extend(themes_host.floats)
    root.floats.extend(models_host.floats)
    app.key_bindings = merge_key_bindings(
        [themes_host.key_bindings, models_host.key_bindings, kb]
    )

    def _invalidate_now() -> None:
        try:
            if app.is_running:
                _sync_theme_style()
                app.invalidate()
        except Exception:  # noqa: BLE001
            pass

    def _invalidate() -> None:
        """Debounce invalidates from worker threads + toolbar animation."""
        now = time.monotonic()
        with invalidate_lock:
            wait = _INVALIDATE_MIN_INTERVAL_S - (now - invalidate_state["last"])
            if wait <= 0:
                invalidate_state["last"] = now
                invalidate_state["pending"] = False
                do_now = True
            else:
                if invalidate_state["pending"]:
                    return
                invalidate_state["pending"] = True
                do_now = False
                delay = wait
        if do_now:
            _invalidate_now()
            return

        def _flush() -> None:
            time.sleep(delay)
            with invalidate_lock:
                invalidate_state["pending"] = False
                invalidate_state["last"] = time.monotonic()
            _invalidate_now()

        threading.Thread(target=_flush, daemon=True, name="ct-invalidate").start()

    unsubscribe = store.subscribe(_invalidate)
    terminal._transcript_app = app
    terminal._transcript_buffer = buf
    app._sandwalk_terminal = terminal  # type: ignore[attr-defined]

    def _auto_highlight_first(buffer):
        if (
            buffer.text.lstrip().startswith("/")
            and buffer.complete_state
            and buffer.complete_state.complete_index is None
            and buffer.complete_state.completions
        ):
            buffer.complete_state.go_to_index(0)

    buf.on_completions_changed += _auto_highlight_first

    def _set_cursor_color(color: str | None) -> None:
        """Best-effort VT cursor color (OSC 12); reset with OSC 112."""
        try:
            out = getattr(app, "output", None)
            write = getattr(out, "write_raw", None) or getattr(out, "write", None)
            if write is None:
                import sys

                write = sys.stdout.write
            if color:
                write(f"\x1b]12;{color}\x07")
            else:
                write("\x1b]112\x07")
            flush = getattr(out, "flush", None)
            if callable(flush):
                flush()
        except Exception:  # noqa: BLE001
            pass

    # Re-assert each frame — some hosts (Warp) reset cursor color on redraw.
    app.before_render += lambda _app: _set_cursor_color(_COMPOSE_CURSOR)

    # Capture stdout/stderr while the fullscreen app owns the TTY. Without this,
    # library/logging dumps (e.g. LangGraph task notes + traceback from
    # logger.warning) write into the alternate screen and shatter the compose box.
    from prompt_toolkit.patch_stdout import patch_stdout

    try:
        with patch_stdout(raw=True):
            result = app.run()
    finally:
        _set_cursor_color(None)
        unsubscribe()
        terminal._transcript_app = None
        terminal._transcript_buffer = None
        terminal._themes_modal_host = None
        terminal._models_modal_host = None

    if result is None:
        raise EOFError


def prompt_with_transcript(terminal, *, history: History | None = None) -> str:
    """One-shot prompt (tests / legacy). Prefer ``run_transcript_session``."""
    box: dict[str, str | None] = {"value": None}

    def _on_submit(text: str) -> bool:
        box["value"] = text
        return False

    run_transcript_session(terminal, history=history, on_submit=_on_submit)
    if box["value"] is None:
        raise EOFError
    return str(box["value"])


def _build_transcript_bindings(
    terminal, store, control, buf, on_submit: Callable[[str], bool]
) -> KeyBindings:
    """Bindings for the persistent transcript app.

    ``include_mouse=False`` keeps prompt_toolkit's default mouse dispatch so
    wheel scroll and ``TranscriptControl.mouse_handler`` work.
    """
    from ui.terminal.key_bindings import _build_key_bindings

    kb = _build_key_bindings(terminal, include_mouse=False)

    def _picker_modal_closed() -> bool:
        for attr in ("_themes_modal_host", "_models_modal_host"):
            host = getattr(terminal, attr, None)
            if host is not None and getattr(host.state, "open", False):
                return False
        return True

    modal_closed = Condition(_picker_modal_closed)

    @kb.add("enter", filter=modal_closed, eager=True)
    def _enter(event):
        from ui.terminal.completion_accept import (
            accept_file_completion,
            accept_slash_completion,
        )

        buffer = event.app.current_buffer
        # @ file pick: insert orange @[filename] chip only — do not send yet.
        if accept_file_completion(buffer):
            event.app.invalidate()
            return
        accept_slash_completion(buffer)
        text = buffer.text
        if text.strip():
            buffer.append_to_history()
        buffer.reset()
        store.pin_tail()
        # Keep the Application alive across turns — exiting/recreating it every
        # submit flickers the screen and stacked store listeners freeze the UI.
        try:
            keep_going = on_submit(text)
        except Exception:  # noqa: BLE001
            keep_going = True
        if not keep_going:
            event.app.exit(result=text if text != "__EXIT__" else "__EXIT__")
        else:
            event.app.invalidate()

    @kb.add("escape", "enter", filter=modal_closed, eager=True)
    def _alt_enter(event):
        event.app.current_buffer.insert_text("\n")

    @kb.add("c-d", filter=modal_closed, eager=True)
    def _eof(event):
        if not event.app.current_buffer.text:
            event.app.exit(result=None)
        else:
            event.app.current_buffer.delete()

    @kb.add(Keys.PageUp)
    def _page_up(event):
        control.scroll_by(-(max(1, control._height - 1)))
        event.app.invalidate()

    @kb.add(Keys.PageDown)
    def _page_down(event):
        control.scroll_by(max(1, control._height - 1))
        event.app.invalidate()

    @kb.add("c-up")
    def _scroll_up(event):
        control.scroll_by(-3)
        event.app.invalidate()

    @kb.add("c-down")
    def _scroll_down(event):
        control.scroll_by(3)
        event.app.invalidate()

    @kb.add("c-e", eager=True)
    def _expand(event):
        store.toggle_last_tool()
        event.app.invalidate()

    @kb.add("c-c", filter=Condition(control.has_selection), eager=True)
    def _copy_selection(event):
        control.copy_selection_to_clipboard()
        control.clear_selection()
        event.app.invalidate()

    @kb.add("escape", filter=Condition(control.has_selection), eager=True)
    def _clear_selection(event):
        control.clear_selection()
        event.app.invalidate()

    return kb
