"""prompt_toolkit Application: scrollable transcript + input + toolbar."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.filters import Condition
from prompt_toolkit.history import History
from prompt_toolkit.key_binding import KeyBindings
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
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.styles import merge_styles

from ui.terminal.attach_lexer import AttachChipLexer
from ui.terminal.completion import PT_STYLE
from ui.terminal.transcript.control import TranscriptControl


# Match the pre-transcript Rich look: muted user chrome, cyan tools (like the
# old ▸ start indicator), soft green only on the checkmark via tool line text,
# default fg for assistant body (Rich ANSI supplies emphasis/links).
# Soft compose panel (pad + fill). Keep bg in sync with _COMPOSE_BG.
_TRANSCRIPT_STYLE = {
    "transcript-sep": "#d0d0d0",
    "transcript-text": "",
    # User turns share the compose soft panel (sync _COMPOSE_BG / accent).
    "transcript-user": "bg:#f5f5f5 #222222",
    "transcript-user-accent": "#c9a227",
    "transcript-system": "#7f8790",
    "transcript-tool": "#8be9fd",
    "transcript-tool-ok": "#98c379",
    "transcript-tool-error": "#ff5555",
    "transcript-tool-detail": "#7f8790",
    "transcript-selected": "reverse",
    # Same orange chip as the compose AttachChipLexer / PT_STYLE.
    "image-chip": "bold #111111 bg:#f0a030",
    # Soft panel #f5f5f5 on white #ffffff (sync _COMPOSE_BG; needs truecolor).
    "transcript-compose": "bg:#f5f5f5 #222222",
    "transcript-compose.prompt": "bold #555555",
    # Gold accent outside the soft panel (default/terminal bg behind it).
    "transcript-compose-accent": "#c9a227",
    "transcript-status": "bg:default #8a8f98",
}

# Cursor OSC color (Warp/VT100); matches sandwalk green accent.
_COMPOSE_CURSOR = "#50fa7b"

# Coalesce store/toolbar invalidates so Rich re-renders can't pin the UI.
_INVALIDATE_MIN_INTERVAL_S = 0.05


def _merge_style():
    from prompt_toolkit.styles import Style

    return merge_styles([PT_STYLE, Style.from_dict(_TRANSCRIPT_STYLE)])


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
    )
    control.window = transcript_window

    # One soft panel wraps input + meta + pads; path/context sit below.
    compose_input = Window(
        BufferControl(
            buffer=buf,
            lexer=AttachChipLexer(),
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
            Window(width=2, char=" "),
            Window(
                FormattedTextControl(_status),
                height=1,
                dont_extend_height=True,
                style="class:bottom-toolbar",
            ),
            Window(width=2, char=" "),
        ],
        padding=0,
    )

    def _outer(width: int = 2) -> Window:
        # Margin outside the soft panel — keep off the terminal edge.
        return Window(width=width, char=" ")

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
    )
    status_block = VSplit(
        [
            _outer(),
            Window(width=1, char=" "),  # same column as gold bar
            status_bar,
            _outer(),
        ],
        padding=0,
    )

    root = FloatContainer(
        content=HSplit(
            [
                transcript_window,
                Window(height=1),  # breath between history and composer
                compose_block,
                status_block,
            ]
        ),
        floats=[
            Float(
                xcursor=True,
                ycursor=True,
                content=CompletionsMenu(max_height=12, scroll_offset=1),
            )
        ],
    )

    kb = _build_transcript_bindings(terminal, store, control, buf, on_submit)

    from prompt_toolkit.output.color_depth import ColorDepth

    app = Application(
        layout=Layout(root, focused_element=buf),
        key_bindings=kb,
        style=_merge_style(),
        # Soft #f5f5f5 panel washes out to white without 24-bit color.
        color_depth=ColorDepth.TRUE_COLOR,
        full_screen=True,
        mouse_support=True,
        erase_when_done=False,
    )

    invalidate_lock = threading.Lock()
    invalidate_state = {"last": 0.0, "pending": False}

    def _invalidate_now() -> None:
        try:
            if app.is_running:
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

    try:
        result = app.run()
    finally:
        _set_cursor_color(None)
        unsubscribe()
        terminal._transcript_app = None
        terminal._transcript_buffer = None

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

    @kb.add("enter", eager=True)
    def _enter(event):
        buffer = event.app.current_buffer
        cs = buffer.complete_state
        if buffer.text.lstrip().startswith("/") and cs and cs.completions:
            if cs.complete_index is None:
                buffer.go_to_completion(0)
                cs = buffer.complete_state
            if cs and cs.current_completion:
                buffer.apply_completion(cs.current_completion)
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

    @kb.add("escape", "enter", eager=True)
    def _alt_enter(event):
        event.app.current_buffer.insert_text("\n")

    @kb.add("c-d", eager=True)
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
