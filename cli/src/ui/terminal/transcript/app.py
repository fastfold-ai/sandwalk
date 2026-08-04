"""prompt_toolkit Application: scrollable transcript + input + toolbar."""

from __future__ import annotations

from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
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
}


def _merge_style():
    from prompt_toolkit.styles import Style

    return merge_styles([PT_STYLE, Style.from_dict(_TRANSCRIPT_STYLE)])


def prompt_with_transcript(terminal, *, history: History | None = None) -> str:
    """Block until the user submits a line; transcript stays interactive."""
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
        result = terminal._bottom_toolbar()
        return result

    transcript_window = Window(
        content=control,
        height=Dimension(weight=1),
        wrap_lines=False,
        dont_extend_height=False,
        # Allow the window to receive wheel events over the transcript area.
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

    kb = _build_transcript_bindings(terminal, store, control, buf)

    app = Application(
        layout=Layout(root, focused_element=buf),
        key_bindings=kb,
        style=_merge_style(),
        full_screen=True,
        mouse_support=True,
        erase_when_done=False,
    )

    def _invalidate():
        try:
            if app.is_running:
                app.invalidate()
        except Exception:  # noqa: BLE001
            pass

    store.subscribe(_invalidate)
    terminal._transcript_app = app
    terminal._transcript_buffer = buf
    app._sandwalk_terminal = terminal  # type: ignore[attr-defined]

    # Auto-highlight first slash completion (same as PromptSession path).
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
        terminal._transcript_app = None

    if result is None:
        raise EOFError
    return str(result)


def _build_transcript_bindings(terminal, store, control, buf) -> KeyBindings:
    """Reuse interactive keybindings; Enter exits the app with buffer text.

    ``include_mouse=False`` is critical: the default prompt_toolkit mouse
    binding must stay active so wheel events reach the transcript Window
    (native scroll) and clicks reach ``TranscriptControl.mouse_handler``.
    """
    from ui.terminal.key_bindings import _build_key_bindings

    kb = _build_key_bindings(terminal, include_mouse=False)

    def _submit(event, text: str):
        event.app.exit(result=text)

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
        # Jump back to the live tail when the user sends a message.
        store.pin_tail()
        _submit(event, text)

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
        # Toward older history (smaller vertical_scroll).
        control.scroll_by(-(max(1, control._height - 1)))
        event.app.invalidate()

    @kb.add(Keys.PageDown)
    def _page_down(event):
        # Toward newer content / tail.
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

    # Override Ctrl+E to toggle in transcript store (in-place).
    @kb.add("c-e", eager=True)
    def _expand(event):
        store.toggle_last_tool()
        event.app.invalidate()

    return kb
