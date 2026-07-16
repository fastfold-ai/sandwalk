"""
Custom Markdown rendering for ct — left-aligned headings.

Rich's default Markdown renderer centers headings. This package provides
a LeftMarkdown class that renders headings left-aligned instead, plus a
mermaid-fence-aware ``print_markdown_with_mermaid`` renderer.
"""

from __future__ import annotations

from ui.markdown.config_utils import _as_bool, _config_get
from ui.markdown.fences import _split_mermaid_fences
from ui.markdown.heading import _LeftHeading, LeftMarkdown
from ui.markdown.mermaid_source import _neaten_mermaid_source
from ui.markdown.render import _print_mermaid_block, print_markdown_with_mermaid

__all__ = [
    "LeftMarkdown",
    "_LeftHeading",
    "print_markdown_with_mermaid",
    "_neaten_mermaid_source",
    "_split_mermaid_fences",
    "_print_mermaid_block",
    "_config_get",
    "_as_bool",
]
