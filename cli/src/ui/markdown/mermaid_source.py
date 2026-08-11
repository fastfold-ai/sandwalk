"""Normalizing LLM-generated Mermaid source for terminal rendering."""

from __future__ import annotations

import html
import re

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
