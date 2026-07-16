"""Rendering entry point: markdown text with mermaid fences as terminal diagrams."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from rich.markdown import Markdown

from ui.markdown.config_utils import _as_bool, _config_get
from ui.markdown.fences import _split_mermaid_fences
from ui.markdown.heading import LeftMarkdown
from ui.markdown.mermaid_source import _neaten_mermaid_source


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
