"""Splitting markdown text into markdown/mermaid fence sections."""

from __future__ import annotations


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
