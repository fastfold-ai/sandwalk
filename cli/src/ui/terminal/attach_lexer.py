"""Highlight ``[Image N]`` chips in the prompt buffer."""

from __future__ import annotations

import re

from prompt_toolkit.document import Document
from prompt_toolkit.lexers import Lexer

_CHIP_RE = re.compile(r"\[Image\s+\d+\]")


class AttachChipLexer(Lexer):
    """Style image chips; leave the rest as plain text."""

    def lex_document(self, document: Document):
        lines = document.lines

        def get_line(i: int):
            if i < 0 or i >= len(lines):
                return []
            line = lines[i]
            out: list[tuple[str, str]] = []
            pos = 0
            for match in _CHIP_RE.finditer(line):
                if match.start() > pos:
                    out.append(("", line[pos:match.start()]))
                out.append(("class:image-chip", match.group(0)))
                pos = match.end()
            if pos < len(line):
                out.append(("", line[pos:]))
            return out

        return get_line
