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
from prompt_toolkit.layout.containers import Float, FloatContainer, HSplit, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.layout.processors import BeforeInput
from prompt_toolkit.styles import merge_styles

from ui.terminal.attach_lexer import AttachChipLexer
from ui.terminal.completion import PT_STYLE
from ui.terminal.transcript.control import TranscriptControl


# Match the pre-transcript Rich look: muted user chrome, cyan tools (like the
# old ▸ start indicator), soft green only on the checkmark via tool line text,
# default fg for assistant body (Rich ANSI supplies emphasis/links).
_TRANSCRIPT_STYLE = {
    "transcript-sep": "#333333",
    "transcript-text": "",
    "transcript-user": "bold",
    "transcript-system": "#7f8790",
    "transcript-tool": "#8be9fd",
    "transcript-tool-ok": "#98c379",
    "transcript-tool-error": "#ff5555",
    "transcript-tool-detail": "#7f8790",
    "transcript-selected": "reverse",
    # Same orange chip as the compose AttachChipLexer / PT_STYLE.
    "image-chip": "bold #111111 bg:#f0a030",
}

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

    def _toolbar():
        return terminal._bottom_toolbar()

    transcript_window = Window(
        content=control,
        height=Dimension(weight=1),
        wrap_lines=False,
        dont_extend_height=False,
        allow_scroll_beyond_bottom=False,
    )
    control.window = transcript_window

    root = FloatContainer(
        content=HSplit(
            [
                transcript_window,
                Window(height=1, char="─", style="class:transcript-sep"),
                Window(
                    BufferControl(
                        buffer=buf,
                        lexer=AttachChipLexer(),
                        input_processors=[BeforeInput([("class:prompt", "❯ ")])],
                        focusable=True,
                    ),
                    height=Dimension(min=1, max=8),
                    wrap_lines=True,
                    dont_extend_height=True,
                ),
                Window(
                    FormattedTextControl(_toolbar),
                    height=1,
                    dont_extend_height=True,
                    style="class:bottom-toolbar",
                ),
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

    app = Application(
        layout=Layout(root, focused_element=buf),
        key_bindings=kb,
        style=_merge_style(),
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

    try:
        result = app.run()
    finally:
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
