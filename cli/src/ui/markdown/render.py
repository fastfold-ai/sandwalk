"""Rendering entry point: markdown text with mermaid fences as terminal diagrams."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from rich.markdown import Markdown

from ui.markdown.config_utils import _as_bool, _config_get
from ui.markdown.fences import _split_mermaid_fences
from ui.markdown.heading import LeftMarkdown
from ui.markdown.links import expose_markdown_links
from ui.markdown.mermaid_source import _neaten_mermaid_source
from ui.markdown.paths import unwrap_path_code_spans


def _workspace_from_config(config: Any = None) -> str | None:
    if config is None:
        return None
    try:
        raw = config.get("session.workspace_path") or config.get("workspace_path")
    except Exception:  # noqa: BLE001
        raw = None
    text = str(raw or "").strip()
    return text or None


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
    workspace: str | None = None,
) -> None:
    """Render markdown text, converting mermaid fences to terminal diagrams."""
    if not text or not text.strip():
        return

    ws = workspace if workspace is not None else _workspace_from_config(config)
    # Bare URLs survive the transcript (OSC-8 does not); unwrap path code too.
    text = expose_markdown_links(unwrap_path_code_spans(text, workspace=ws))

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
