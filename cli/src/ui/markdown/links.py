"""Make markdown/http links safe for the prompt_toolkit transcript.

Rich emits OSC-8 hyperlinks (``\\x1b]8;id=…;url\\x1b\\\\``). prompt_toolkit's
ANSI parser does not understand OSC-8, so the escape bytes get dropped and the
user sees garbage like ``8;id=144809;https://…Dashboard8;;``.

We (1) rewrite ``[label](url)`` to bare ``label: url`` before Rich runs, and
(2) strip any residual OSC-8 sequences from ANSI capture.
"""

from __future__ import annotations

import re

# Inline markdown links to http(s). Skip images (![alt](url)).
_MD_LINK = re.compile(
    r"(?<!!)\[([^\]]+)\]\((https?://[^)\s]+)\)"
)

# OSC-8: ESC ] 8 ; params ; uri ST  where ST is ESC \ or BEL
_OSC8 = re.compile(r"\x1b\]8;[^\x1b\x07]*(?:\x1b\\|\x07)")


def expose_markdown_links(text: str) -> str:
    """Turn ``[Dashboard](https://…)`` into ``Dashboard: https://…``."""

    def repl(match: re.Match[str]) -> str:
        label = match.group(1).strip()
        url = match.group(2).strip()
        if not label or label == url or label.startswith(("http://", "https://")):
            return url
        return f"{label}: {url}"

    return _MD_LINK.sub(repl, str(text or ""))


def strip_osc8_hyperlinks(text: str) -> str:
    """Remove OSC-8 wrappers; keep the visible link text / surrounding ANSI."""
    return _OSC8.sub("", str(text or ""))
