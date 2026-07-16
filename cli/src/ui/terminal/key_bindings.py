"""Custom prompt_toolkit key bindings for the interactive terminal."""

import threading
import time

from prompt_toolkit.filters import has_completions
from prompt_toolkit.key_binding import KeyBindings


def _build_key_bindings(terminal):
    """Key bindings: Tab accepts ghost suggestion, Ctrl+C double-tap to exit,
    Ctrl+O toggle verbose, Ctrl+J insert newline."""
    kb = KeyBindings()

    @kb.add("tab")
    def _accept_suggestion(event):
        buf = event.app.current_buffer
        if not buf.text:
            idx = terminal._suggestion_idx % len(terminal._suggestions)
            buf.insert_text(terminal._suggestions[idx])
        else:
            buf.start_completion()

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

    @kb.add("c-o")
    def _toggle_verbose(event):
        """Toggle verbose mode mid-session."""
        terminal.session.verbose = not terminal.session.verbose
        state = "ON" if terminal.session.verbose else "OFF"
        terminal._verbose_hint = f"Verbose {state}"
        event.app.invalidate()

        def _clear_hint():
            time.sleep(2.0)
            terminal._verbose_hint = None
            try:
                if event.app.is_running:
                    event.app.invalidate()
            except Exception:
                pass

        threading.Thread(target=_clear_hint, daemon=True).start()

    @kb.add("c-j")
    def _insert_newline(event):
        """Insert a newline for multi-line input."""
        event.app.current_buffer.insert_text("\n")

    @kb.add("escape", "enter")
    def _insert_newline_alt(event):
        """Option+Enter / Alt+Enter inserts newline."""
        event.app.current_buffer.insert_text("\n")

    @kb.add("enter", filter=has_completions)
    def _accept_first_completion(event):
        """When completions are visible on a / command, accept the current
        (or first) completion and submit."""
        buf = event.app.current_buffer
        cs = buf.complete_state
        if buf.text.lstrip().startswith("/") and cs and cs.completions:
            # If nothing is selected yet, jump to the first completion
            if cs.complete_index is None:
                buf.go_to_completion(0)
                cs = buf.complete_state  # refresh after navigation
            if cs and cs.current_completion:
                buf.apply_completion(cs.current_completion)
            buf.validate_and_handle()
        else:
            # Non-slash: just submit normally
            buf.cancel_completion()
            buf.validate_and_handle()

    @kb.add("right", filter=has_completions)
    def _mention_tab_right(event):
        """Switch to next mention tab while completions are visible."""
        completer = terminal._merged_completer
        if completer is None:
            return
        mc = completer.mention_completer
        mc._active_tab = (mc._active_tab + 1) % len(mc.TABS)
        buf = event.app.current_buffer
        buf.cancel_completion()
        buf.start_completion()

    @kb.add("left", filter=has_completions)
    def _mention_tab_left(event):
        """Switch to previous mention tab while completions are visible."""
        completer = terminal._merged_completer
        if completer is None:
            return
        mc = completer.mention_completer
        mc._active_tab = (mc._active_tab - 1) % len(mc.TABS)
        buf = event.app.current_buffer
        buf.cancel_completion()
        buf.start_completion()

    return kb
