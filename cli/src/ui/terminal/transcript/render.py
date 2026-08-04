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
) -> list[StyleAndTextTuples]:
    """Render markdown (+ mermaid fences) to per-line FormattedText.

    Uses the same Rich/termaid path as the pre-transcript CLI so diagrams,
    links, tables, and emphasis match the previous look.
    """
    if not text or not text.strip():
        return []
    try:
        from rich.console import Console

        from ui.markdown.render import print_markdown_with_mermaid

        buf = StringIO()
        console = Console(
            file=buf,
            width=max(40, width),
            force_terminal=bool(colored),
            color_system="256" if colored else None,
            highlight=False,
            soft_wrap=True,
        )
        print_markdown_with_mermaid(console, text, config=config)
        raw = buf.getvalue().rstrip("\n")
    except Exception:  # noqa: BLE001
        raw = text

    rows: list[StyleAndTextTuples] = []
    for line in raw.split("\n"):
        if colored:
            body = list(to_formatted_text(ANSI(line)))
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

        # Startup mark + meta (Rich ANSI); keep original spacing, no extra pad.
        if entry.kind == "banner":
            rows: list[tuple[Entry, int, StyleAndTextTuples]] = []
            for i, line in enumerate(entry.text.split("\n")):
                body = list(to_formatted_text(ANSI(line))) if line else [("", "")]
                rows.append((entry, i, body))
            return rows or [(entry, 0, [("", "")])]

        # Rich → transcript keeps ANSI; render it (model lists, tables, etc.).
        if entry.kind in {"system", "text"} and "\x1b[" in entry.text:
            rows: list[tuple[Entry, int, StyleAndTextTuples]] = []
            for i, line in enumerate(entry.text.split("\n")):
                body = list(to_formatted_text(ANSI(line))) if line else [("", "")]
                rows.append((entry, i, body))
            return rows or [(entry, 0, [("", "")])]

        prefix = "❯ " if entry.kind == "user" else ""
        raw = entry.text
        # Show the same orange [Image N] chips as the compose box (not @uploads/…).
        if entry.kind == "user" or "@uploads/" in raw or "[Image " in raw:
            from ui.terminal.attachments import chipify_uploads_for_display

            raw = chipify_uploads_for_display(raw)
        body = prefix + raw if prefix else raw
        style = {
            "user": "class:transcript-user",
            "system": "class:transcript-system",
        }.get(entry.kind, "class:transcript-text")
        out: list[tuple[Entry, int, StyleAndTextTuples]] = []
        use_chips = "[Image " in body
        for i, line in enumerate(_wrap(body, inner)):
            if use_chips:
                from ui.terminal.attachments import style_with_image_chips

                frags = style_with_image_chips(line, style)
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
