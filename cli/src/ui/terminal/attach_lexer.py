"""Highlight ``[Image N]`` and ``[filename]`` file chips in the prompt buffer."""

from __future__ import annotations

import re
from collections.abc import Callable

from prompt_toolkit.document import Document
from prompt_toolkit.lexers import Lexer

_IMAGE_CHIP_RE = re.compile(r"\[Image\s+\d+\]")


class AttachChipLexer(Lexer):
    """Style image + file chips; leave the rest as plain text."""

    def __init__(
        self,
        file_chips: Callable[[], list[str]] | list[str] | None = None,
    ) -> None:
        self._file_chips = file_chips

    def _chips(self) -> list[str]:
        raw = self._file_chips
        if raw is None:
            return []
        if callable(raw):
            try:
                return list(raw() or [])
            except Exception:  # noqa: BLE001
                return []
        return list(raw)

    def lex_document(self, document: Document):
        lines = document.lines
        file_chips = sorted(self._chips(), key=len, reverse=True)

        def get_line(i: int):
            if i < 0 or i >= len(lines):
                return []
            line = lines[i]
            spans: list[tuple[int, int]] = [
                (m.start(), m.end()) for m in _IMAGE_CHIP_RE.finditer(line)
            ]
            for chip in file_chips:
                start = 0
                while True:
                    idx = line.find(chip, start)
                    if idx < 0:
                        break
                    spans.append((idx, idx + len(chip)))
                    start = idx + len(chip)
            if not spans:
                return [("", line)] if line else []
            spans.sort(key=lambda s: (s[0], -(s[1] - s[0])))
            merged: list[tuple[int, int]] = []
            for start, end in spans:
                if merged and start < merged[-1][1]:
                    continue
                merged.append((start, end))
            out: list[tuple[str, str]] = []
            pos = 0
            for start, end in merged:
                if start > pos:
                    out.append(("", line[pos:start]))
                out.append(("class:image-chip", line[start:end]))
                pos = end
            if pos < len(line):
                out.append(("", line[pos:]))
            return out

        return get_line
