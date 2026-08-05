"""Rich Theme overrides for markdown rendered in the sandwalk TUI.

Rich defaults use ``markdown.code: bold cyan on black`` — dark chips that look
harsh on light themes and hide long paths. We keep a light tint (or none) and
prefer bold colored text instead.
"""

from __future__ import annotations

from typing import Any, Literal

from rich.theme import Theme

Mode = Literal["light", "dark"]


def resolve_markdown_mode(config: Any = None, theme: str | None = None) -> Mode:
    if theme is not None:
        return "dark" if str(theme).strip().lower() == "dark" else "light"
    try:
        from ui.terminal.theme import resolve_ui_theme

        return resolve_ui_theme(config)
    except Exception:  # noqa: BLE001
        return "light"


def markdown_rich_theme(
    mode: Mode | str | None = None, *, config: Any = None
) -> Theme:
    """Theme for Console.print(Markdown(...)) / transcript markdown capture."""
    resolved: Mode = (
        resolve_markdown_mode(config)
        if mode is None
        else ("dark" if str(mode).strip().lower() == "dark" else "light")
    )
    if resolved == "light":
        code = "bold #0284c7"
        code_block = "#0284c7"
        link = "underline #0284c7"
    else:
        code = "bold #7dd3fc"
        code_block = "#7dd3fc"
        link = "underline #7dd3fc"
    return Theme(
        {
            # Drop Rich's default ``on black`` chip background.
            "markdown.code": code,
            "markdown.code_block": code_block,
            "markdown.link": link,
            "markdown.link_url": link,
            # Avoid generic reverse chips if any path hits the bare ``code`` style.
            "code": code,
        }
    )
