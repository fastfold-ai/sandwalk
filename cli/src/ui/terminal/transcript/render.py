"""Render transcript entries to prompt_toolkit FormattedText lines."""

from __future__ import annotations

from io import StringIO

from prompt_toolkit.formatted_text import ANSI, StyleAndTextTuples, to_formatted_text

from ui.terminal.transcript.store import (
    Entry,
    SeparatorEntry,
    TextEntry,
    ToolEntry,
    TranscriptStore,
)
from ui.traces.formatting import format_args, format_duration, truncate_output

# Horizontal inset so content is not flush against the terminal edge.
LEFT_PAD = "  "
_PAD_FRAG: StyleAndTextTuples = [("", LEFT_PAD)]

# User message soft panel — match compose box (outer margin + gold ┃ + theme bg).
_USER_OUTER = "  "
_USER_ACCENT = "┃"
_USER_INNER = "  "
_USER_STYLE = "class:transcript-user"
_USER_ACCENT_STYLE = "class:transcript-user-accent"


def markdown_to_plain(text: str, *, width: int, config=None) -> str:
    """Plain (no-ANSI) markdown render — used by tests and fallbacks."""
    lines = markdown_to_styled_lines(text, width=width, config=config, colored=False)
    out: list[str] = []
    for frags in lines:
        out.append("".join(piece for _style, piece in frags))
    return "\n".join(out).rstrip("\n")


def markdown_to_styled_lines(
    text: str,
    *,
    width: int,
    config=None,
    colored: bool = True,
    workspace: str | None = None,
) -> list[StyleAndTextTuples]:
    """Render markdown (+ mermaid fences) to per-line FormattedText.

    Uses the same Rich/termaid path as the pre-transcript CLI so diagrams,
    links, tables, and emphasis match the previous look.
    """
    if not text or not text.strip():
        return []
    try:
        import os

        from rich.console import Console

        from ui.markdown.render import print_markdown_with_mermaid
        from ui.markdown.theme import markdown_rich_theme

        buf = StringIO()
        # soft_wrap=False so Rich hard-wraps to `width`. soft_wrap=True leaves
        # one long line for the host terminal; our Window has wrap_lines=False
        # and would clip mid-word on the right edge.
        # Also pin height: Rich only honors width alone when height is set too
        # (otherwise TERM=dumb / tty probe can force an 80-col size).
        wrap_w = max(20, int(width))
        console = Console(
            file=buf,
            width=wrap_w,
            height=10_000,
            force_terminal=bool(colored),
            color_system="256" if colored else None,
            highlight=False,
            soft_wrap=False,
            theme=markdown_rich_theme(config=config),
        )
        ws = workspace
        if not ws:
            try:
                ws = str(
                    getattr(config, "get", lambda *_a, **_k: None)(
                        "session.workspace_path"
                    )
                    or ""
                ).strip() or None
            except Exception:  # noqa: BLE001
                ws = None
        if not ws:
            ws = str(os.environ.get("SANDWALK_SESSION_WORKSPACE") or "").strip() or None
        print_markdown_with_mermaid(
            console, text, config=config, workspace=ws
        )
        from ui.markdown.links import strip_osc8_hyperlinks

        # prompt_toolkit ANSI does not parse OSC-8; strip before convert or
        # users see ``8;id=…;https://…Label8;;`` garbage.
        raw = strip_osc8_hyperlinks(buf.getvalue()).rstrip("\n")
    except Exception:  # noqa: BLE001
        raw = text

    rows: list[StyleAndTextTuples] = []
    for line in raw.split("\n"):
        if colored:
            from ui.markdown.links import strip_osc8_hyperlinks

            body = list(to_formatted_text(ANSI(strip_osc8_hyperlinks(line))))
        else:
            body = [("", line)]
        rows.append([*_PAD_FRAG, *body] if body else list(_PAD_FRAG))
    return rows or [list(_PAD_FRAG)]


def _wrap(text: str, width: int) -> list[str]:
    if width <= 0:
        return text.split("\n") or [""]
    lines: list[str] = []
    for raw in text.split("\n"):
        if not raw:
            lines.append("")
            continue
        while len(raw) > width:
            lines.append(raw[:width])
            raw = raw[width:]
        lines.append(raw)
    return lines or [""]


def _pad(line: str) -> str:
    return LEFT_PAD + line


def tool_header_line(entry: ToolEntry) -> str:
    clean = entry.name.replace("mcp__ct-tools__", "")
    mark = "\u2717" if entry.is_error else "\u2713"
    dur = f"  {format_duration(entry.duration)}" if entry.duration > 0 else ""
    arrow = "\u25be" if entry.expanded else "\u25b8"
    return _pad(f"{mark} Ran {clean}{dur} {arrow}")


def tool_header_frags(entry: ToolEntry) -> StyleAndTextTuples:
    """Soft green check / red x, cyan tool name (not neon whole-line green)."""
    clean = entry.name.replace("mcp__ct-tools__", "")
    mark = "\u2717" if entry.is_error else "\u2713"
    dur = f"  {format_duration(entry.duration)}" if entry.duration > 0 else ""
    arrow = "\u25be" if entry.expanded else "\u25b8"
    mark_style = (
        "class:transcript-tool-error" if entry.is_error else "class:transcript-tool-ok"
    )
    name_style = (
        "class:transcript-tool-error" if entry.is_error else "class:transcript-tool"
    )
    return [
        ("", LEFT_PAD),
        (mark_style, f"{mark} "),
        (name_style, f"Ran {clean}"),
        ("class:transcript-tool-detail", f"{dur} {arrow}"),
    ]


def tool_detail_lines(entry: ToolEntry) -> list[str]:
    lines: list[str] = []
    args_str = format_args(entry.args)
    if args_str:
        lines.append(_pad(f"  {args_str}"))
    summary = truncate_output(entry.result)
    if summary:
        for part in summary.split("\n"):
            lines.append(_pad(f"  {part}"))
    return lines


def _style_plain(style: str, text: str) -> StyleAndTextTuples:
    return [(style, text)]


def _user_panel_fill(panel_w: int) -> StyleAndTextTuples:
    return [
        ("", _USER_OUTER),
        (_USER_ACCENT_STYLE, _USER_ACCENT),
        (_USER_STYLE, " " * panel_w),
    ]


def _user_panel_content(
    content_frags: StyleAndTextTuples,
    *,
    content_len: int,
    panel_w: int,
) -> StyleAndTextTuples:
    """One soft-panel row: outer margin + gold ┃ + padded content fill."""
    inner_pad = len(_USER_INNER)
    used = inner_pad + content_len + inner_pad
    fill = max(0, panel_w - used)
    return [
        ("", _USER_OUTER),
        (_USER_ACCENT_STYLE, _USER_ACCENT),
        (_USER_STYLE, _USER_INNER),
        *content_frags,
        (_USER_STYLE, (" " * fill) + _USER_INNER),
    ]


def user_message_rows(
    text: str,
    *,
    width: int,
) -> list[StyleAndTextTuples]:
    """Compose-style soft box for a user turn (no ❯ prefix)."""
    from ui.terminal.attachments import (
        chipify_file_paths_for_display,
        chipify_uploads_for_display,
        find_file_chips,
        find_mcp_chips,
        find_skill_chips,
        style_with_image_chips,
    )

    raw = chipify_file_paths_for_display(chipify_uploads_for_display(text))
    file_chips = find_file_chips(raw)
    skill_chips = find_skill_chips(raw)
    mcp_chips = find_mcp_chips(raw)
    outer_w = len(_USER_OUTER)
    panel_w = max(8, width - outer_w - 1)
    inner_w = max(1, panel_w - 2 * len(_USER_INNER))
    body_lines = _wrap(raw, inner_w)
    use_chips = (
        "[Image " in raw
        or bool(file_chips)
        or bool(skill_chips)
        or bool(mcp_chips)
    )

    # Margin above the soft panel so system/usage lines ("Switched to…",
    # "✻ Validated for…") are not flush against the user box.
    rows: list[StyleAndTextTuples] = [[("", "")], _user_panel_fill(panel_w)]
    for line in body_lines:
        if use_chips:
            frags = style_with_image_chips(
                line,
                _USER_STYLE,
                file_chips=file_chips,
                skill_chips=skill_chips,
                mcp_chips=mcp_chips,
            )
        else:
            frags = [(_USER_STYLE, line)] if line else [(_USER_STYLE, "")]
        rows.append(
            _user_panel_content(frags, content_len=len(line), panel_w=panel_w)
        )
    rows.append(_user_panel_fill(panel_w))
    # Breath before the assistant reply (outside the soft panel).
    rows.append([("", "")])
    return rows


def usage_footer_rows(left: str, right: str, *, width: int) -> list[StyleAndTextTuples]:
    """Duration left / tokens right, laid out for the live transcript width.

    Pre-padding to ``console.width`` clips the trailing token digits when the
    Window is even one column narrower — reflow here instead.
    """
    style = "class:transcript-system"
    # Keep one column clear at the right edge so ↑/↓ counts never clip.
    usable = max(8, int(width) - 1)
    content_w = max(1, usable - len(LEFT_PAD))
    left = str(left or "")
    right = str(right or "")
    if len(left) + (1 if right else 0) + len(right) > content_w:
        line = f"{left} · {right}" if right else left
        if len(line) > content_w:
            line = line[:content_w]
        body = _pad(line)
    else:
        spaces = max(1, content_w - len(left) - len(right)) if right else 0
        body = LEFT_PAD + left + (" " * spaces) + right
    if len(body) > usable:
        body = body[:usable]
    return [
        [("", "")],
        [(style, body)],
    ]


def entry_rows(
    entry: Entry,
    *,
    width: int,
    config=None,
) -> list[tuple[Entry, int, StyleAndTextTuples]]:
    """Return (entry, line_index, styled fragments) for one entry."""
    inner = max(20, width - len(LEFT_PAD))
    if isinstance(entry, SeparatorEntry):
        bar = "─" * max(8, min(inner, 120))
        return [(entry, 0, _style_plain("class:transcript-sep", _pad(bar)))]

    if isinstance(entry, TextEntry):
        if entry.kind == "assistant":
            styled = markdown_to_styled_lines(
                entry.text, width=inner, config=config, colored=True
            )
            return [(entry, i, frags) for i, frags in enumerate(styled)]

        if entry.kind == "usage":
            left, sep, right = entry.text.partition("\t")
            rows = usage_footer_rows(left, right if sep else "", width=width)
            return [(entry, i, frags) for i, frags in enumerate(rows)]

        if entry.kind == "resume":
            # Wrap ourselves so every continuation line keeps LEFT_PAD.
            from ui.terminal.attachments import (
                chipify_uploads_for_display,
                style_with_image_chips,
            )

            raw = chipify_uploads_for_display(entry.text)
            style = "class:transcript-resume"
            out: list[tuple[Entry, int, StyleAndTextTuples]] = []
            for i, line in enumerate(_wrap(raw, inner)):
                frags = style_with_image_chips(line, style)
                out.append((entry, i, [("", LEFT_PAD), *frags]))
            return out or [(entry, 0, _style_plain(style, LEFT_PAD.rstrip()))]

        # Startup mark + meta (Rich ANSI). Banner already has Rich Padding;
        # leave blank lines alone so the inset breathes.
        if entry.kind == "banner":
            from ui.markdown.links import strip_osc8_hyperlinks

            rows: list[tuple[Entry, int, StyleAndTextTuples]] = []
            for i, line in enumerate(entry.text.split("\n")):
                clean = strip_osc8_hyperlinks(line)
                body = list(to_formatted_text(ANSI(clean))) if clean else [("", "")]
                rows.append((entry, i, body))
            return rows or [(entry, 0, [("", "")])]

        # Rich → transcript keeps ANSI; render it (model lists, tables, etc.).
        if entry.kind in {"system", "text"} and (
            "\x1b[" in entry.text or "\x1b]8;" in entry.text
        ):
            from ui.markdown.links import strip_osc8_hyperlinks

            rows: list[tuple[Entry, int, StyleAndTextTuples]] = []
            for i, line in enumerate(entry.text.split("\n")):
                clean = strip_osc8_hyperlinks(line)
                body = list(to_formatted_text(ANSI(clean))) if clean else [("", "")]
                rows.append((entry, i, body))
            return rows or [(entry, 0, [("", "")])]

        if entry.kind == "user":
            boxed = user_message_rows(entry.text, width=width)
            return [(entry, i, frags) for i, frags in enumerate(boxed)]

        # Intentional spacer rows (console.print() with no args).
        if not (entry.text or "").strip():
            return [(entry, 0, [("", "")])]

        raw = entry.text
        # Show the same orange [Image N] / @[file] chips as the compose box.
        if "@uploads/" in raw or "[Image " in raw:
            from ui.terminal.attachments import chipify_uploads_for_display

            raw = chipify_uploads_for_display(raw)
        from ui.terminal.attachments import (
            find_file_chips,
            find_mcp_chips,
            find_skill_chips,
            style_with_image_chips,
        )

        file_chips = find_file_chips(raw)
        skill_chips = find_skill_chips(raw)
        mcp_chips = find_mcp_chips(raw)
        style = {
            "system": "class:transcript-system",
            "error": "class:transcript-error",
        }.get(entry.kind, "class:transcript-text")
        out: list[tuple[Entry, int, StyleAndTextTuples]] = []
        use_chips = (
            "[Image " in raw
            or bool(file_chips)
            or bool(skill_chips)
            or bool(mcp_chips)
        )
        for i, line in enumerate(_wrap(raw, inner)):
            if use_chips:
                frags = style_with_image_chips(
                    line,
                    style,
                    file_chips=file_chips,
                    skill_chips=skill_chips,
                    mcp_chips=mcp_chips,
                )
                out.append((entry, i, [("", LEFT_PAD), *frags]))
            else:
                out.append((entry, i, _style_plain(style, _pad(line))))
        return out or [(entry, 0, _style_plain(style, LEFT_PAD.rstrip()))]

    if isinstance(entry, ToolEntry):
        rows: list[tuple[Entry, int, StyleAndTextTuples]] = [
            (entry, 0, tool_header_frags(entry))
        ]
        if entry.expanded:
            detail = tool_detail_lines(entry)
            for i, line in enumerate(detail, start=1):
                for j, wrapped in enumerate(_wrap(line[len(LEFT_PAD) :], inner)):
                    rows.append(
                        (
                            entry,
                            i + j,
                            _style_plain("class:transcript-tool-detail", _pad(wrapped)),
                        )
                    )
        return rows
    return []


def entry_lines(entry: Entry, *, width: int, config=None) -> list[tuple[Entry, int, str]]:
    """Plain-text view of an entry (tests / line-count helpers)."""
    rows = entry_rows(entry, width=width, config=config)
    out: list[tuple[Entry, int, str]] = []
    for ent, idx, frags in rows:
        text = "".join(piece for _style, piece in frags)
        out.append((ent, idx, text))
    return out


def render_all_lines(
    store: TranscriptStore,
    *,
    width: int,
    config=None,
) -> tuple[list[StyleAndTextTuples], list[tuple[Entry, int]]]:
    """Build FormattedText for the full transcript (Window scrolls natively)."""
    entries = store.snapshot()
    formatted: list[StyleAndTextTuples] = []
    hit_map: list[tuple[Entry, int]] = []
    for entry in entries:
        for ent, idx, frags in entry_rows(entry, width=width, config=config):
            hit_map.append((ent, idx))
            formatted.append(frags)
    if not formatted:
        formatted = [[("", "")]]
        hit_map = [(TextEntry(""), -1)]
    return formatted, hit_map


def render_lines(
    store: TranscriptStore,
    *,
    width: int,
    height: int,
    config=None,
) -> tuple[list[StyleAndTextTuples], list[tuple[Entry, int]]]:
    """Viewport slice of the transcript (tests / legacy custom scroll)."""
    rows, hit_map = render_all_lines(store, width=width, config=config)
    total = len(rows)
    viewport = max(1, height)
    if store.follow_tail:
        start = max(0, total - viewport)
    else:
        end = total - store.scroll_offset
        start = max(0, end - viewport)
    visible_rows = rows[start : start + viewport]
    visible_hits = hit_map[start : start + viewport]
    while len(visible_rows) < viewport:
        visible_rows.append([("", "")])
        visible_hits.append((TextEntry(""), -1))
    return visible_rows, visible_hits
