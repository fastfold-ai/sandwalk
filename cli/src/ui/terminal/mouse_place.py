"""Warp-friendly click-to-place cursor for inline prompt_toolkit prompts.

Warp's block grid reports mouse coordinates that often miss prompt_toolkit's
tiny non-fullscreen layout rectangle (``HeightIsUnknownError`` / out-of-range
``y``). When the default handler cannot map the click, we place the cursor by
column (and by line-from-bottom when possible).
"""

from __future__ import annotations

from prompt_toolkit.data_structures import Point
from prompt_toolkit.key_binding.key_processor import KeyPressEvent
from prompt_toolkit.keys import Keys
from prompt_toolkit.mouse_events import MouseButton, MouseEvent, MouseEventType
from prompt_toolkit.renderer import HeightIsUnknownError

# prompt_toolkit SGR table (subset) — left button down/up.
_SGR = {
    (0, "M"): (MouseButton.LEFT, MouseEventType.MOUSE_DOWN),
    (0, "m"): (MouseButton.LEFT, MouseEventType.MOUSE_UP),
    (32, "M"): (MouseButton.LEFT, MouseEventType.MOUSE_MOVE),
}


def parse_sgr_mouse(data: str) -> tuple[int, int, MouseButton, MouseEventType] | None:
    """Parse ``Vt100MouseEvent`` data → 0-based (x, y, button, type)."""
    if not data or len(data) < 3:
        return None
    # Xterm SGR: Esc[<button;x;yM/m  — prompt_toolkit sets data like ``\x1b[<0;5;10M``
    payload = data[2:] if data.startswith("\x1b[") else data
    if payload.startswith("<"):
        payload = payload[1:]
    elif "M" in data[2:3]:
        return None  # classic mode — let default bindings handle
    try:
        button_code, x_s, rest = payload.split(";", 2)
        y_s, kind = rest[:-1], rest[-1]
        button_i = int(button_code)
        x = int(x_s) - 1
        y = int(y_s) - 1
    except (ValueError, IndexError):
        return None
    parsed = _SGR.get((button_i, kind))
    if parsed is None:
        # Other buttons / scroll — not our placement path.
        return None
    button, etype = parsed
    return x, y, button, etype


def place_cursor_in_buffer(buf, *, x: int, local_y: int | None, prompt_width: int = 2) -> None:
    """Move buffer cursor from a click at column ``x`` / optional layout row."""
    doc = buf.document
    lines = doc.lines
    if not lines:
        return
    n_lines = len(lines)
    if local_y is None or local_y < 0:
        row = doc.cursor_position_row
    else:
        # Toolbar is usually below the buffer; clamp into buffer rows.
        row = max(0, min(n_lines - 1, local_y))
    col = max(0, x - prompt_width)
    col = min(col, len(lines[row]))
    buf.cursor_position = doc.translate_row_col_to_index(row, col)


def try_default_mouse_handler(event: KeyPressEvent, x: int, y: int, button, etype) -> bool:
    """Return True if prompt_toolkit's layout handled the click."""
    try:
        y_adj = y - event.app.renderer.rows_above_layout
    except HeightIsUnknownError:
        return False
    handlers = event.app.renderer.mouse_handlers.mouse_handlers
    try:
        handler = handlers[y_adj][x]
    except (IndexError, KeyError, TypeError):
        return False
    result = handler(
        MouseEvent(
            position=Point(x=x, y=y_adj),
            event_type=etype,
            button=button,
            modifiers=frozenset(),
        )
    )
    return result is not NotImplemented  # noqa: F632 — intentional singleton check


def _try_expand_tool_at_click(event: KeyPressEvent, y: int) -> bool:
    """Legacy host-scrollback expand; owned transcript handles clicks itself."""
    terminal = getattr(event.app, "_sandwalk_terminal", None)
    if terminal is None:
        return False
    # Owned transcript Window owns click-to-expand; skip host-row guessing.
    if getattr(terminal, "transcript", None) is not None:
        return False
    store = getattr(getattr(terminal, "session", None), "tool_expand_store", None)
    if store is None or not store.cards:
        return False
    try:
        rows_above = event.app.renderer.rows_above_layout
    except HeightIsUnknownError:
        rows_above = y + 1 if y >= 0 else 0
    if rows_above <= 0 or y >= rows_above:
        return False
    card = store.card_for_screen_row(rows_above_layout=rows_above, y=y)
    if card is None or card.expanded:
        return False
    expand = getattr(terminal, "_expand_tool_card", None)
    if not callable(expand):
        return False
    expand(card)
    return True


def handle_mouse_place_cursor(event: KeyPressEvent, *, prompt_width: int = 2):
    """Key-binding body: expand tool / place cursor on left-click."""
    parsed = parse_sgr_mouse(event.data or "")
    if parsed is None:
        return NotImplemented
    x, y, button, etype = parsed
    if button != MouseButton.LEFT:
        return NotImplemented

    if etype == MouseEventType.MOUSE_DOWN:
        # Prefer expanding a collapsed tool line in the scrollback above the prompt.
        if _try_expand_tool_at_click(event, y):
            return None
        if try_default_mouse_handler(event, x, y, button, etype):
            return None
        terminal = getattr(event.app, "_sandwalk_terminal", None)
        # Fullscreen owned-transcript app: layout hit-testing owns clicks/scroll.
        # Do not steal transcript clicks into the input buffer.
        if terminal is not None and getattr(terminal, "_transcript_app", None) is not None:
            return NotImplemented
        # Fallback for Warp / unknown height: map into the edit buffer.
        local_y = None
        try:
            local_y = y - event.app.renderer.rows_above_layout
        except HeightIsUnknownError:
            # Prefer last visible buffer row when the host grid is taller than
            # the prompt layout (typical Warp block).
            local_y = len(event.app.current_buffer.document.lines) - 1
        else:
            # Out of range → clamp into buffer rows.
            n = max(1, len(event.app.current_buffer.document.lines))
            if local_y < 0 or local_y >= n + 2:  # +2 toolbar/padding slack
                local_y = min(n - 1, max(0, local_y))
        place_cursor_in_buffer(
            event.app.current_buffer,
            x=x,
            local_y=local_y,
            prompt_width=prompt_width,
        )
        return None

    # Let default handle drag/up when possible.
    if try_default_mouse_handler(event, x, y, button, etype):
        return None
    return NotImplemented


def bind_mouse_place_cursor(kb, terminal=None, *, prompt_width: int = 2) -> None:
    @kb.add(Keys.Vt100MouseEvent)
    def _mouse_place(event):
        if terminal is not None:
            event.app._sandwalk_terminal = terminal  # type: ignore[attr-defined]
        return handle_mouse_place_cursor(event, prompt_width=prompt_width)
