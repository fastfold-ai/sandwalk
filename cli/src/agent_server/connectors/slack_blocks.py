"""Render an agent reply as Slack Block Kit.

Slack's `mrkdwn` is not Markdown: bold is `*one asterisk*`, links are
`<url|text>`, and there are no headings or tables. The tool description asks the
model for mrkdwn and capable models comply, but weaker and local ones do not, so
:func:`to_mrkdwn` normalizes the common Markdown spellings rather than trusting
the prompt.

Block Kit is what makes a reply look like a card instead of a wall of text, and
it comes with limits a plain ``text`` post does not have: 3000 characters per
section and 50 blocks per message, against 40,000 characters for plain text. So
chunking is a cost of moving to blocks, not a pre-existing bug.
"""

from __future__ import annotations

import re

# Slack's documented ceilings.
SECTION_LIMIT = 3000
MAX_BLOCKS = 50
# Room for the divider, context footer and any button.
_RESERVED_BLOCKS = 3

_FENCE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE = re.compile(r"`[^`\n]+`")
_BOLD = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", re.DOTALL)
_BOLD_UNDERSCORE = re.compile(r"__(?=\S)(.+?)(?<=\S)__", re.DOTALL)
_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", re.MULTILINE)
_BULLET = re.compile(r"^(\s*)[-*+]\s+(?=\S)", re.MULTILINE)
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")


def _protect(text: str) -> tuple[str, list[str]]:
    """Swap code spans for placeholders so conversion cannot touch them."""
    held: list[str] = []

    def stash(match: re.Match[str]) -> str:
        held.append(match.group(0))
        return f"\x00{len(held) - 1}\x00"

    return _INLINE_CODE.sub(stash, _FENCE.sub(stash, text)), held


def _restore(text: str, held: list[str]) -> str:
    for index, value in enumerate(held):
        text = text.replace(f"\x00{index}\x00", value)
    return text


def _tables_to_code(text: str) -> str:
    """Wrap Markdown tables in a code fence — Slack has no table primitive.

    Left as pipes they wrap into unreadable prose; monospaced they at least
    keep their columns.
    """
    lines = text.split("\n")
    out: list[str] = []
    run: list[str] = []

    def flush() -> None:
        if not run:
            return
        # A single piped line is more likely prose than a table.
        if len(run) > 1:
            out.extend(["```", *run, "```"])
        else:
            out.extend(run)
        run.clear()

    for line in lines:
        if _TABLE_ROW.match(line):
            run.append(line.rstrip())
            continue
        flush()
        out.append(line)
    flush()
    return "\n".join(out)


def to_mrkdwn(text: str) -> str:
    """Convert common Markdown spellings to Slack mrkdwn.

    Idempotent for text that is already mrkdwn: single-asterisk bold is left
    alone, so a compliant model's output passes through unchanged.
    """
    body, held = _protect(text or "")
    body = _tables_to_code(body)
    body = _HEADING.sub(lambda m: f"*{m.group(1).strip()}*", body)
    body = _LINK.sub(lambda m: f"<{m.group(2)}|{m.group(1)}>", body)
    body = _BOLD.sub(lambda m: f"*{m.group(1)}*", body)
    body = _BOLD_UNDERSCORE.sub(lambda m: f"*{m.group(1)}*", body)
    body = _BULLET.sub(lambda m: f"{m.group(1)}• ", body)
    return _restore(body, held)


def _split_paragraph(chunk: str, limit: int) -> list[str]:
    """Hard-split an oversized paragraph on line, then word, then character."""
    parts: list[str] = []
    remaining = chunk
    while len(remaining) > limit:
        window = remaining[:limit]
        cut = window.rfind("\n")
        if cut <= 0:
            cut = window.rfind(" ")
        if cut <= 0:
            cut = limit
        parts.append(remaining[:cut].rstrip())
        remaining = remaining[cut:].lstrip()
    if remaining:
        parts.append(remaining)
    return parts


def split_for_sections(text: str, limit: int = SECTION_LIMIT) -> list[str]:
    """Break text into section-sized pieces, preferring paragraph breaks.

    Fenced code is never split across sections when it fits, since a torn fence
    renders as literal backticks.
    """
    body = (text or "").strip()
    if not body:
        return []

    pieces: list[str] = []
    for block in re.split(r"\n{2,}", body):
        block = block.strip()
        if not block:
            continue
        if len(block) <= limit:
            pieces.append(block)
        else:
            pieces.extend(_split_paragraph(block, limit))

    # Recombine neighbours that still fit, so short paragraphs stay together.
    merged: list[str] = []
    for piece in pieces:
        if merged and len(merged[-1]) + len(piece) + 2 <= limit:
            merged[-1] = f"{merged[-1]}\n\n{piece}"
        else:
            merged.append(piece)
    return merged


def build_blocks(
    text: str,
    *,
    footer: str | None = None,
    view_url: str | None = None,
    view_label: str = "View in Sandwalk",
) -> list[dict]:
    """Build Block Kit for a reply. Returns [] when there is nothing to say.

    ``view_url`` renders a link button. Buttons carrying a ``url`` are not
    interactions, so this needs no interactivity endpoint — but Slack requires
    a real http(s) URL, so callers pass None until a session has one.
    """
    sections = split_for_sections(to_mrkdwn(text))
    if not sections:
        return []

    budget = MAX_BLOCKS - _RESERVED_BLOCKS
    truncated = len(sections) > budget
    if truncated:
        sections = sections[:budget]

    blocks: list[dict] = [
        {"type": "section", "text": {"type": "mrkdwn", "text": piece}}
        for piece in sections
    ]
    if truncated:
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "_Reply truncated — open the session for the rest._",
                    }
                ],
            }
        )
    if view_url:
        blocks.append(
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": view_label},
                        "url": view_url,
                    }
                ],
            }
        )
    if footer:
        blocks.append(
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": footer}],
            }
        )
    return blocks[:MAX_BLOCKS]


def fallback_text(text: str, limit: int = 3000) -> str:
    """Notification text shown in the sidebar and on mobile push.

    Slack requires ``text`` alongside ``blocks``; without it the notification
    reads "This content can't be displayed".
    """
    body = to_mrkdwn(text).strip()
    if len(body) <= limit:
        return body
    return body[: limit - 1].rstrip() + "…"
