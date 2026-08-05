"""Unit tests for the owned scrollable transcript."""

from __future__ import annotations

from ui.terminal.transcript.render import entry_lines, render_lines, tool_header_line
from ui.terminal.transcript.store import TextEntry, ToolEntry, TranscriptStore


def test_tool_toggle_changes_line_count():
    store = TranscriptStore()
    tool = store.append_tool(
        name="shell.run",
        args={"command": "ls"},
        result="a\nb\nc",
        duration=0.4,
    )
    collapsed = entry_lines(tool, width=80)
    assert len(collapsed) == 1
    assert "▸" in collapsed[0][2] or "\u25b8" in collapsed[0][2]

    store.toggle_tool(tool.entry_id)
    expanded = entry_lines(tool, width=80)
    assert len(expanded) > 1
    assert any("command=" in row[2] for row in expanded)


def test_toggle_last_tool():
    store = TranscriptStore()
    store.append_tool(name="a", result="1")
    b = store.append_tool(name="b", result="2")
    store.toggle_last_tool()
    assert b.expanded is True
    store.toggle_last_tool()
    assert b.expanded is False


def test_scroll_offset_and_follow_tail():
    store = TranscriptStore()
    for i in range(30):
        store.append_text(f"line {i}")
    rows, _ = render_lines(store, width=40, height=5)
    # Last visible text should be near the end while following tail.
    flat = "".join(frag[1] for row in rows for frag in row)
    assert "line 29" in flat

    store.scroll_lines(10, viewport=5, total_lines=30)
    assert store.follow_tail is False
    rows2, _ = render_lines(store, width=40, height=5)
    flat2 = "".join(frag[1] for row in rows2 for frag in row)
    assert "line 29" not in flat2


def test_render_hit_map_marks_tools():
    store = TranscriptStore()
    store.append_text("hello")
    store.append_tool(name="neo", result="ok")
    rows, hit = render_lines(store, width=80, height=10)
    tool_hits = [e for e, _ in hit if isinstance(e, ToolEntry)]
    assert tool_hits
    text_hits = [e for e, idx in hit if isinstance(e, TextEntry) and idx >= 0]
    assert text_hits


def test_tool_header_arrow_flips():
    entry = ToolEntry(name="x", expanded=False)
    assert "\u25b8" in tool_header_line(entry)
    entry.expanded = True
    assert "\u25be" in tool_header_line(entry)


def test_control_cursor_anchors_scroll():
    """Window scrolls to keep cursor visible — cursor must anchor tail/manual scroll."""
    from ui.terminal.transcript.control import TranscriptControl

    class FakeWin:
        vertical_scroll = 0

    store = TranscriptStore()
    for i in range(40):
        store.append_text(f"line {i}")

    control = TranscriptControl(store)
    control.window = FakeWin()

    # Following tail: cursor on the last line so the window pins to bottom.
    content = control.create_content(80, 10)
    assert content.cursor_position.y == content.line_count - 1
    assert control.window.vertical_scroll == content.line_count - 10

    # Scrolled up: cursor tracks the manual scroll position, not line 0.
    store.follow_tail = False
    control.window.vertical_scroll = 5
    content2 = control.create_content(80, 10)
    assert content2.cursor_position.y == 5


def _click(control, x: int, y: int) -> None:
    from prompt_toolkit.data_structures import Point
    from prompt_toolkit.mouse_events import MouseButton, MouseEvent, MouseEventType

    for etype in (MouseEventType.MOUSE_DOWN, MouseEventType.MOUSE_UP):
        control.mouse_handler(
            MouseEvent(
                position=Point(x=x, y=y),
                event_type=etype,
                button=MouseButton.LEFT,
                modifiers=frozenset(),
            )
        )


def test_mouse_click_toggles_each_tool_when_scrolled():
    """Clicks use absolute content rows — must work for every tool past the fold."""
    from ui.terminal.transcript.control import TranscriptControl

    class FakeWin:
        vertical_scroll = 0

    store = TranscriptStore()
    for i in range(20):
        store.append_text(f"pad {i}")
    tools = [
        store.append_tool(name="first", args={"a": 1}, result="r1"),
        store.append_tool(name="second", args={"b": 2}, result="r2"),
        store.append_tool(name="third", args={"c": 3}, result="r3"),
    ]

    control = TranscriptControl(store)
    control.window = FakeWin()
    control.create_content(80, 10)
    assert control.window.vertical_scroll > 0

    headers = [
        i
        for i, (entry, line_idx) in enumerate(control._hit_map)
        if isinstance(entry, ToolEntry) and line_idx == 0
    ]
    assert len(headers) == 3

    for tool, row in zip(tools, headers, strict=True):
        for t in tools:
            t.expanded = False
        _click(control, 2, row)
        assert tool.expanded is True
        assert sum(1 for t in tools if t.expanded) == 1


def test_store_subscribe_can_unsubscribe():
    store = TranscriptStore()
    hits = []
    unsub = store.subscribe(lambda: hits.append(1))
    store.append_text("a")
    unsub()
    store.append_text("b")
    assert hits == [1]


def test_render_cache_skips_rerender_when_revision_unchanged():
    from ui.terminal.transcript.control import TranscriptControl

    class FakeWin:
        vertical_scroll = 0

    store = TranscriptStore()
    store.append_text("hello")
    control = TranscriptControl(store)
    control.window = FakeWin()
    control.create_content(80, 10)
    rows_id = id(control._rows)
    rev = store.revision
    # Toolbar-style invalidate with no store change must reuse cached rows.
    control.create_content(80, 10)
    assert id(control._rows) == rows_id
    assert store.revision == rev
    store.append_text("world")
    control.create_content(80, 10)
    assert id(control._rows) != rows_id


def test_system_ansi_from_rich_keeps_color_codes_out_of_plain_path():
    from ui.terminal.transcript.render import entry_rows
    from ui.terminal.transcript.sink import rich_print_to_text

    colored = rich_print_to_text("[cyan]hello[/cyan] [dim]world[/dim]", width=40)
    assert "\x1b[" in colored
    store = TranscriptStore()
    store.append_text(colored, kind="system")
    rows = entry_rows(store.entries[0], width=80)
    joined = "".join(t for _e, _i, frags in rows for _s, t in frags)
    assert "hello" in joined
    assert "world" in joined
    assert "\x1b[" not in joined  # ANSI parsed into styles, not raw escapes


def test_user_message_renders_upload_as_image_chip():
    from ui.terminal.transcript.render import entry_rows

    store = TranscriptStore()
    store.append_text("@uploads/20260804-clip.png what's this?", kind="user")
    rows = entry_rows(store.entries[0], width=80)
    assert rows
    joined = "".join(t for _e, _i, frags in rows for _s, t in frags)
    assert "[Image 1]" in joined
    assert "what's this?" in joined
    assert "@uploads/" not in joined
    assert "❯" not in joined
    assert any("image-chip" in s for _e, _i, frags in rows for s, _t in frags)
    # Compose-style soft box: gold accent + soft panel fill.
    assert any(
        "transcript-user-accent" in s for _e, _i, frags in rows for s, _t in frags
    )
    assert any("transcript-user" in s for _e, _i, frags in rows for s, _t in frags)
    assert any("┃" in t for _e, _i, frags in rows for _s, t in frags)


def test_user_message_renders_file_mention_as_orange_chip():
    from ui.terminal.transcript.render import entry_rows

    store = TranscriptStore()
    chip = "@[output_7addce64-8059-490b-b70f-61de66a4db78_model_0.cif]"
    store.append_text(f"{chip} what is this file?", kind="user")
    rows = entry_rows(store.entries[0], width=120)
    joined = "".join(t for _e, _i, frags in rows for _s, t in frags)
    assert chip in joined
    assert "what is this file?" in joined
    chip_text = "".join(
        t for _e, _i, frags in rows for s, t in frags if "image-chip" in s
    )
    assert chip_text == chip


def test_user_message_renders_skill_mention_as_pink_chip():
    from ui.terminal.transcript.render import entry_rows

    store = TranscriptStore()
    store.append_text("skill: fold what is this for?", kind="user")
    rows = entry_rows(store.entries[0], width=80)
    joined = "".join(t for _e, _i, frags in rows for _s, t in frags)
    assert "skill: fold" in joined
    chip_text = "".join(
        t for _e, _i, frags in rows for s, t in frags if "skill-chip" in s
    )
    assert chip_text == "skill: fold"


def test_user_message_chipifies_expanded_paths_on_resume():
    """Persisted queries store @rel/path; resume should show @[basename] chips."""
    from ui.terminal.transcript.render import entry_rows

    store = TranscriptStore()
    path = (
        "@artifacts/fold/7addce64-8059-490b-b70f-61de66a4db78/"
        "plddt_pae_metrics.json"
    )
    store.append_text(f"{path} what is this?", kind="user")
    rows = entry_rows(store.entries[0], width=120)
    joined = "".join(t for _e, _i, frags in rows for _s, t in frags)
    assert "@[plddt_pae_metrics.json]" in joined
    assert "@artifacts/" not in joined
    chip_text = "".join(
        t for _e, _i, frags in rows for s, t in frags if "image-chip" in s
    )
    assert chip_text == "@[plddt_pae_metrics.json]"


def test_user_message_box_has_no_prompt_arrow():
    from ui.terminal.transcript.render import entry_lines

    store = TranscriptStore()
    store.append_text("hello sandwalk", kind="user")
    lines = [line for _, _, line in entry_lines(store.entries[0], width=60)]
    joined = "\n".join(lines)
    assert "hello sandwalk" in joined
    assert "❯" not in joined
    assert any("┃" in line for line in lines)


def test_resize_reflows_to_current_width():
    """Wrap always tracks the live window width so text stays fully visible."""
    from ui.terminal.transcript.control import TranscriptControl

    store = TranscriptStore()
    store.append_text("hello world " * 20, kind="assistant")
    control = TranscriptControl(store)

    narrow = control.create_content(40, 10)
    assert control._cache_key == (int(store.revision), 40)
    narrow_lines = narrow.line_count

    wide = control.create_content(120, 10)
    assert control._cache_key == (int(store.revision), 120)
    # Wider wrap should produce fewer (or equal) content rows before height pad.
    assert control._line_count <= narrow_lines

    # Lines are padded to the window width so shrink-resizes clear ghosts.
    line0 = "".join(t for _s, t in wide.get_line(0))
    assert len(line0) >= 120


def test_banner_kind_preserves_mark_without_left_pad():
    from ui.terminal.transcript.render import LEFT_PAD, entry_lines

    store = TranscriptStore()
    store.append_text("██\nsandwalk v0.0.1\n12 tools · 3 skills", kind="banner")
    rows = entry_lines(store.entries[0], width=80)
    joined = "\n".join(line for _, _, line in rows)
    assert "sandwalk" in joined
    assert "██" in joined
    # Banner keeps Rich spacing; do not force the transcript LEFT_PAD.
    assert not all(line.startswith(LEFT_PAD) for _, _, line in rows if line.strip())


def test_drag_selects_text_without_toggling_tool():
    from prompt_toolkit.data_structures import Point
    from prompt_toolkit.mouse_events import MouseButton, MouseEvent, MouseEventType

    from ui.terminal.transcript.control import TranscriptControl

    class FakeWin:
        vertical_scroll = 0

    store = TranscriptStore()
    store.append_text("hello selectable world")
    tool = store.append_tool(name="neo", args={"x": 1}, result="ok")

    control = TranscriptControl(store)
    control.window = FakeWin()
    control.create_content(80, 20)
    plain = control._plain_lines[0]
    start = plain.index("selectable")
    end = start + len("selectable") - 1

    control.mouse_handler(
        MouseEvent(
            position=Point(x=start, y=0),
            event_type=MouseEventType.MOUSE_DOWN,
            button=MouseButton.LEFT,
            modifiers=frozenset(),
        )
    )
    control.mouse_handler(
        MouseEvent(
            position=Point(x=end, y=0),
            event_type=MouseEventType.MOUSE_MOVE,
            button=MouseButton.LEFT,
            modifiers=frozenset(),
        )
    )
    control.mouse_handler(
        MouseEvent(
            position=Point(x=end, y=0),
            event_type=MouseEventType.MOUSE_UP,
            button=MouseButton.LEFT,
            modifiers=frozenset(),
        )
    )

    assert control.selected_text() == "selectable"
    assert tool.expanded is False
    assert control.has_selection() is True

    # Highlight appears in rendered fragments.
    content = control.create_content(80, 20)
    frags = content.get_line(0)
    selected = "".join(text for style, text in frags if "transcript-selected" in style)
    assert "selectable" in selected


def test_click_opens_absolute_path_in_transcript():
    from unittest.mock import patch

    from prompt_toolkit.data_structures import Point
    from prompt_toolkit.mouse_events import MouseButton, MouseEvent, MouseEventType

    from ui.terminal.transcript.control import TranscriptControl

    class FakeWin:
        vertical_scroll = 0

    path = "/Users/juliocesar/Projects/sandwalk/cli/exports/session_demo.md"
    store = TranscriptStore()
    store.append_text(f"  {path}")

    control = TranscriptControl(store)
    control.window = FakeWin()
    content = control.create_content(120, 10)
    # Find the line that contains the path (may have left-pad).
    line_idx = next(
        i for i, line in enumerate(control._plain_lines) if path in line
    )
    x = control._plain_lines[line_idx].index(path) + 2
    frags = content.get_line(line_idx)
    assert any("transcript-link" in style for style, _t in frags)

    with patch("ui.terminal.transcript.control.open_link", return_value=True) as open_fn:
        control.mouse_handler(
            MouseEvent(
                position=Point(x=x, y=line_idx),
                event_type=MouseEventType.MOUSE_DOWN,
                button=MouseButton.LEFT,
                modifiers=frozenset(),
            )
        )
        control.mouse_handler(
            MouseEvent(
                position=Point(x=x, y=line_idx),
                event_type=MouseEventType.MOUSE_UP,
                button=MouseButton.LEFT,
                modifiers=frozenset(),
            )
        )
        open_fn.assert_called_once()
        kind, target = open_fn.call_args[0]
        assert kind == "path"
        assert target == path


def test_resume_line_keeps_left_pad_when_wrapped():
    """Continuation lines must keep the transcript inset (Rich drops it)."""
    from ui.terminal.transcript.render import LEFT_PAD, entry_lines

    store = TranscriptStore()
    store.append_text(
        "Resumed session d50b3d49 — what's this ?@uploads/20260804-180631-clipboard.png (1 turns)",
        kind="resume",
    )
    rows = entry_lines(store.entries[0], width=40)
    plain = [line for _, _, line in rows]
    assert len(plain) > 1
    assert all(line.startswith(LEFT_PAD) for line in plain)
    joined = "\n".join(plain)
    assert "@uploads/" not in joined
    assert "[Image 1]" in joined


def test_usage_footer_keeps_token_counts_inside_width():
    """Token arrows must stay fully visible (not clipped to ↓ 2 from ↓ 253)."""
    from ui.terminal.transcript.render import entry_lines

    store = TranscriptStore()
    store.append_text("✻ Generated for 20s\t↑ 10,980 ↓ 253", kind="usage")
    for width in (40, 60, 80, 100, 120):
        rows = entry_lines(store.entries[0], width=width)
        plain = [line for _, _, line in rows if line.strip()]
        assert plain, width
        assert all(len(line) <= width for _, _, line in rows), (width, rows)
        joined = "\n".join(plain)
        assert "↑ 10,980" in joined
        assert "↓ 253" in joined
        assert joined.rstrip().endswith("253")


def test_markdown_assistant_hard_wraps_to_width():
    """Rich soft_wrap must be off — long assistant lines must not clip mid-word."""
    from ui.terminal.transcript.render import LEFT_PAD, entry_lines, markdown_to_plain

    text = (
        "That's a capybara (Hydrochoerus hydrochaeris) — the world's largest living rodent. "
        "It's a sharp, well-lit photo of one standing in short grass, given the clean "
        "lighting and isolated background."
    )
    width = 60
    plain = markdown_to_plain(text, width=width)
    lines = plain.splitlines()
    assert len(lines) > 1
    # LEFT_PAD is applied after Rich wraps to `width`, so each visible line
    # is at most pad + wrap-width (Rich may leave trailing spaces).
    assert max(len(line) for line in lines) <= len(LEFT_PAD) + width + 2
    assert "isolated" in plain  # not clipped away at the right edge

    store = TranscriptStore()
    store.append_text(text, kind="assistant")
    rows = entry_lines(store.entries[0], width=width)
    plain_rows = [line.rstrip() for _, _, line in rows]
    assert len(plain_rows) > 1
    assert max(len(line) for line in plain_rows) <= width
    assert any("isolated" in line for line in plain_rows)


def test_markdown_assistant_strips_emphasis_and_pads():
    from ui.terminal.transcript.render import LEFT_PAD, entry_lines, markdown_to_plain

    plain = markdown_to_plain("It handles **RNA** and **DNA**.", width=60)
    assert "**" not in plain
    assert "RNA" in plain
    assert "DNA" in plain

    store = TranscriptStore()
    store.append_text("| Metric | Value |\n| --- | --- |\n| conf | 0.9 |", kind="assistant")
    rows = entry_lines(store.entries[0], width=80)
    assert rows
    assert all(line.startswith(LEFT_PAD) or line == LEFT_PAD.rstrip() for _, _, line in rows)
    joined = "\n".join(line for _, _, line in rows)
    # Rich table render should not leave raw markdown pipe header alone as the only form,
    # but must at least not keep emphasis markers and should include cell text.
    assert "conf" in joined or "0.9" in joined
    assert "**" not in joined


def test_mermaid_fence_renders_not_raw_source():
    from ui.terminal.transcript.render import entry_lines, markdown_to_plain

    md = (
        "Overview\n\n"
        "```mermaid\n"
        "flowchart TD\n"
        "  A[Start] --> B[End]\n"
        "```\n"
    )
    plain = markdown_to_plain(md, width=80, config={"ui.mermaid.enabled": True})
    # Termaid/Rich should expand the diagram; raw fence marker must not remain.
    assert "```mermaid" not in plain
    assert "flowchart TD" not in plain or "Start" in plain
    # At minimum the surrounding prose stays and fence markers are gone.
    assert "Overview" in plain

    store = TranscriptStore()
    store.append_text(md, kind="assistant")
    rows = entry_lines(store.entries[0], width=80, config={"ui.mermaid.enabled": True})
    joined = "\n".join(line for _, _, line in rows)
    assert "```mermaid" not in joined


def test_trace_renderer_sink_skips_console_print():
    from io import StringIO
    from unittest.mock import MagicMock

    from rich.console import Console

    from ui.terminal.transcript.sink import TranscriptSink
    from ui.terminal.transcript.store import TranscriptStore
    from ui.traces import TraceRenderer

    store = TranscriptStore()
    sink = TranscriptSink(store)
    buf = StringIO()
    console = Console(file=buf, no_color=True, width=80)
    console.print = MagicMock()
    renderer = TraceRenderer(console, sink=sink)
    renderer.render_tool_compact(
        "shell.run", 0.5, args={"command": "ls"}, result="ok"
    )
    assert console.print.call_count == 0
    assert len(store.entries) == 1
    assert store.entries[0].name == "shell.run"
