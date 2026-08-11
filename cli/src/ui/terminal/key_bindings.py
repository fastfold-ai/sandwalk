"""Key bindings: Tab completions, double Ctrl+C exit, newlines, image paste."""

from __future__ import annotations

import threading
import time

from prompt_toolkit.filters import has_completions
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys


def _register_attach(terminal, relative: str) -> str:
    """Record upload path and return visible ``[Image N]`` chip text."""
    from ui.terminal.attachments import chip_label

    n = getattr(terminal, "_attach_count", 0) + 1
    terminal._attach_count = n
    mapping = getattr(terminal, "_attach_map", None)
    if mapping is None:
        mapping = {}
        terminal._attach_map = mapping
    mapping[n] = relative
    return chip_label(n)


def _insert_attach_chip(event, terminal, relative: str, rest: str = "") -> None:
    buf = event.app.current_buffer
    chip = _register_attach(terminal, relative)
    before = buf.document.text_before_cursor
    if before and not before[-1].isspace():
        buf.insert_text(" ")
    buf.insert_text(chip)
    if rest:
        if not rest[0].isspace():
            buf.insert_text(" ")
        buf.insert_text(rest)
    else:
        buf.insert_text(" ")
    event.app.invalidate()


def _try_path_attach(terminal, event, text: str) -> bool:
    from ui.terminal.attachments import (
        attach_from_pasted_text,
        session_workspace_path,
    )

    workspace = session_workspace_path(terminal)
    if workspace is None:
        return False
    try:
        result = attach_from_pasted_text(workspace, text)
    except (OSError, ValueError):
        return False
    if not result:
        return False
    relative, rest = result
    _insert_attach_chip(event, terminal, relative, rest)
    return True


def _build_key_bindings(terminal, *, include_mouse: bool = True):
    """Key bindings: Tab completions, Ctrl+C double-tap to exit,
    Enter submit / Ctrl+J·Alt+Enter newline, image paste.

    ``include_mouse=False`` skips the custom Warp click-to-place Vt100 mouse
    binding. The fullscreen transcript app must NOT bind it: key bindings have
    no NotImplemented fallthrough, so a custom Vt100MouseEvent binding shadows
    prompt_toolkit's default mouse dispatch and kills wheel scroll / clicks.
    """
    kb = KeyBindings()

    if include_mouse:
        # Legacy inline-prompt path only: click-to-place cursor in Warp.
        from ui.terminal.mouse_place import bind_mouse_place_cursor

        bind_mouse_place_cursor(kb, terminal, prompt_width=2)

    @kb.add("c-e")
    def _expand_last_tool(event):
        """Ctrl+E — toggle the most recent tool card in place."""
        transcript = getattr(terminal, "transcript", None)
        if transcript is not None:
            transcript.toggle_last_tool()
            event.app.invalidate()
            return
        expand = getattr(terminal, "_expand_tool_card", None)
        if callable(expand):
            expand(None)
            event.app.invalidate()

    @kb.add("tab")
    def _start_completion(event):
        event.app.current_buffer.start_completion()

    @kb.add("c-c")
    def _handle_ctrl_c(event):
        buf = event.app.current_buffer
        now = time.time()
        if terminal._has_active_query():
            force = (now - terminal._last_interrupt) < 0.7
            terminal._last_interrupt = now
            terminal._show_interrupt_hint = True
            terminal._request_interrupt(force=force)
            buf.reset()
            event.app.invalidate()

            def _clear_interrupt_hint():
                time.sleep(1.0)
                terminal._show_interrupt_hint = False
                try:
                    if event.app.is_running:
                        event.app.invalidate()
                except Exception:
                    pass

            threading.Thread(target=_clear_interrupt_hint, daemon=True).start()
            return

        if now - terminal._last_interrupt < 0.5:
            # Double Ctrl+C — signal exit
            event.app.exit(result="__EXIT__")
        else:
            terminal._last_interrupt = now
            terminal._show_exit_hint = True
            buf.reset()
            event.app.invalidate()

            def _clear_hint():
                time.sleep(0.5)
                terminal._show_exit_hint = False
                try:
                    if event.app.is_running:
                        event.app.invalidate()
                except Exception:
                    pass

            threading.Thread(target=_clear_hint, daemon=True).start()

    @kb.add("c-j")
    def _insert_newline(event):
        """Ctrl+J inserts a newline (multi-line input)."""
        event.app.current_buffer.insert_text("\n")

    @kb.add("escape", "enter")
    def _insert_newline_alt(event):
        """Option+Enter / Alt+Enter inserts newline."""
        event.app.current_buffer.insert_text("\n")

    # Enter always submits when completions are not forcing slash/file accept.
    # (multiline=False makes this the default; keep explicit for clarity.)
    @kb.add("enter", filter=has_completions)
    def _accept_first_completion(event):
        """Accept @ file chip without sending; / applies then submits."""
        from ui.terminal.completion_accept import (
            accept_file_completion,
            accept_slash_completion,
        )

        buf = event.app.current_buffer
        if accept_file_completion(buf):
            event.app.invalidate()
            return
        from ui.terminal.completion import prepare_slash_submit

        accept_slash_completion(buf)
        # Owned transcript Application registers its own Enter (eager) to exit
        # with buffer text; PromptSession uses validate_and_handle.
        if getattr(terminal, "transcript", None) is not None:
            text = buf.text
            submit_text, restore_prefix = prepare_slash_submit(text)
            if text.strip():
                buf.append_to_history()
            buf.reset()
            if restore_prefix:
                buf.insert_text(restore_prefix)
            event.app.exit(result=submit_text)
            return
        buf.validate_and_handle()

    @kb.add("c-v")
    def _paste_or_attach_image(event):
        """Prefer clipboard image → chip; else path attach; else normal paste."""
        from ui.terminal.attachments import (
            attach_from_clipboard,
            session_workspace_path,
        )

        workspace = session_workspace_path(terminal)
        if workspace is not None:
            try:
                relative = attach_from_clipboard(workspace)
            except (OSError, ValueError):
                relative = None
            if relative:
                _insert_attach_chip(event, terminal, relative)
                return

        data = event.app.clipboard.get_data()
        text = data.text if data is not None else ""
        if text and _try_path_attach(terminal, event, text):
            return
        if text:
            event.app.current_buffer.paste_clipboard_data(data)

    @kb.add(Keys.BracketedPaste)
    def _bracketed_paste(event):
        """Cmd+V / path-drop: attach leading image path as ``[Image N]`` chip."""
        text = event.data or ""
        if _try_path_attach(terminal, event, text):
            return
        # Also try clipboard image when paste is empty/weird (some hosts).
        if not text.strip():
            from ui.terminal.attachments import (
                attach_from_clipboard,
                session_workspace_path,
            )

            workspace = session_workspace_path(terminal)
            if workspace is not None:
                try:
                    relative = attach_from_clipboard(workspace)
                except (OSError, ValueError):
                    relative = None
                if relative:
                    _insert_attach_chip(event, terminal, relative)
                    return
        event.app.current_buffer.insert_text(text)

    @kb.add("right", filter=has_completions)
    def _mention_tab_right(event):
        """Switch to next # mention tab while tool completions are visible."""
        completer = terminal._merged_completer
        if completer is None:
            return
        buf = event.app.current_buffer
        # File (@) completions have no tabs.
        from ui.terminal.completion import _last_trigger

        text = buf.document.text_before_cursor
        trigger = _last_trigger(text)
        if trigger is not None and trigger[0] == "@":
            return
        mc = completer.mention_completer
        mc._active_tab = (mc._active_tab + 1) % len(mc.TABS)
        buf.cancel_completion()
        buf.start_completion()

    @kb.add("left", filter=has_completions)
    def _mention_tab_left(event):
        """Switch to previous # mention tab while tool completions are visible."""
        completer = terminal._merged_completer
        if completer is None:
            return
        from ui.terminal.completion import _last_trigger

        buf = event.app.current_buffer
        text = buf.document.text_before_cursor
        trigger = _last_trigger(text)
        if trigger is not None and trigger[0] == "@":
            return
        mc = completer.mention_completer
        mc._active_tab = (mc._active_tab - 1) % len(mc.TABS)
        buf.cancel_completion()
        buf.start_completion()

    return kb
