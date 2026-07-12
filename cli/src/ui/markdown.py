"""
Custom Markdown rendering for ct — left-aligned headings.

Rich's default Markdown renderer centers headings. This module provides
a LeftMarkdown class that renders headings left-aligned instead.
"""

from __future__ import annotations

import html
import re
from typing import Any, Callable

from rich import box
from rich.markdown import Heading, Markdown
from rich.panel import Panel
from rich.text import Text


class _LeftHeading(Heading):
    """Heading with left alignment instead of Rich's default centered."""

    def __rich_console__(self, console, options):
        text = self.text
        text.justify = "left"
        if self.tag == "h1":
            yield Panel(text, box=box.HEAVY, style="markdown.h1.border")
        else:
            yield Text("")
            yield text
            yield Text("")


class LeftMarkdown(Markdown):
    """Markdown renderer with left-aligned headings."""

    elements = {**Markdown.elements, "heading_open": _LeftHeading}


def _config_get(config: Any, key: str, default: Any) -> Any:
    if config is None or not hasattr(config, "get"):
        return default
    try:
        value = config.get(key, default)
    except Exception:
        return default
    return default if value is None else value


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _split_mermaid_fences(text: str) -> list[tuple[str, str]]:
    """Split markdown into ('markdown'|'mermaid', content) sections."""
    if "```mermaid" not in text.lower():
        return [("markdown", text)]

    sections: list[tuple[str, str]] = []
    markdown_buf: list[str] = []
    mermaid_buf: list[str] = []
    mermaid_open_line: str | None = None
    in_mermaid = False

    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        if not in_mermaid:
            if stripped.lower().startswith("```mermaid"):
                if markdown_buf:
                    sections.append(("markdown", "".join(markdown_buf)))
                    markdown_buf = []
                in_mermaid = True
                mermaid_open_line = line
                mermaid_buf = []
                continue
            markdown_buf.append(line)
            continue

        if stripped.startswith("```"):
            sections.append(("mermaid", "".join(mermaid_buf)))
            in_mermaid = False
            mermaid_open_line = None
            mermaid_buf = []
            continue

        mermaid_buf.append(line)

    if in_mermaid:
        # Unclosed mermaid fence: preserve source as plain markdown.
        if mermaid_open_line is not None:
            markdown_buf.append(mermaid_open_line)
        markdown_buf.extend(mermaid_buf)

    if markdown_buf:
        sections.append(("markdown", "".join(markdown_buf)))

    if not sections:
        return [("markdown", text)]

    merged: list[tuple[str, str]] = []
    for section_type, content in sections:
        if not content:
            continue
        if merged and merged[-1][0] == section_type:
            merged[-1] = (section_type, merged[-1][1] + content)
        else:
            merged.append((section_type, content))
    return merged or [("markdown", text)]


_BR_TAG_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_HTML_TAG_RE = re.compile(r"</?[a-zA-Z][^>]*>")


def _neaten_mermaid_source(code: str) -> str:
    """Normalize LLM-generated Mermaid so it renders cleanly in a terminal.

    termaid does not interpret HTML the way the Mermaid web renderer does, so
    constructs like ``<br/>`` and ``&amp;`` otherwise leak into node labels and
    blow out the layout. Convert line-break tags to spaces, strip leftover HTML
    tags, decode entities, and collapse the extra whitespace that introduces.
    """
    text = str(code or "")
    if not text:
        return text
    text = _BR_TAG_RE.sub(" ", text)
    text = _HTML_TAG_RE.sub("", text)
    text = html.unescape(text)
    # Collapse interior runs of spaces/tabs left behind by tag removal, but keep
    # leading indentation and newlines so the diagram structure stays intact.
    cleaned_lines = []
    for line in text.splitlines():
        stripped = line.lstrip()
        indent = line[: len(line) - len(stripped)]
        cleaned_lines.append(indent + re.sub(r"[ \t]{2,}", " ", stripped).rstrip())
    return "\n".join(cleaned_lines)


def _print_mermaid_block(
    console: Any,
    code: str,
    *,
    use_ascii: bool,
    theme: str,
    markdown_factory: Callable[[str], Markdown],
) -> None:
    source = _neaten_mermaid_source(str(code or "").strip()).strip()
    if not source:
        return

    try:
        from termaid import render_rich

        console.print(
            render_rich(
                source,
                use_ascii=use_ascii,
                theme=theme,
            )
        )
        return
    except Exception:
        pass

    try:
        from termaid import render

        console.print(render(source, use_ascii=use_ascii))
        return
    except Exception:
        # Keep original markdown visible if rendering fails.
        console.print(markdown_factory(f"```mermaid\n{source}\n```"))


def print_markdown_with_mermaid(
    console: Any,
    text: str,
    *,
    config: Any = None,
    markdown_factory: Callable[[str], Markdown] = LeftMarkdown,
) -> None:
    """Render markdown text, converting mermaid fences to terminal diagrams."""
    if not text or not text.strip():
        return

    mermaid_enabled = _as_bool(_config_get(config, "ui.mermaid.enabled", True), True)
    if not mermaid_enabled:
        console.print(markdown_factory(text))
        return

    use_ascii = _as_bool(_config_get(config, "ui.mermaid.ascii", False), False)
    theme = str(_config_get(config, "ui.mermaid.theme", "default") or "default").strip() or "default"

    for section_type, section in _split_mermaid_fences(text):
        if section_type == "mermaid":
            _print_mermaid_block(
                console,
                section,
                use_ascii=use_ascii,
                theme=theme,
                markdown_factory=markdown_factory,
            )
            continue
        if section.strip():
            console.print(markdown_factory(section))
