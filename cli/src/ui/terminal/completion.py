"""prompt_toolkit style + completers for slash commands and @ mentions."""

from __future__ import annotations

from collections.abc import Callable

from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.filters import has_completions, is_done, to_filter
from prompt_toolkit.layout.containers import (
    ConditionalContainer,
    HSplit,
    VSplit,
    Window,
)
from prompt_toolkit.layout.controls import UIContent
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.layout.menus import CompletionsMenuControl, _get_menu_item_fragments
from prompt_toolkit.layout.screen import Point
from prompt_toolkit.styles import Style

from ui.terminal.slash_commands import SLASH_COMMANDS


class _FullWidthCompletionsMenuControl(CompletionsMenuControl):
    """Pad meta (or the command column) so the selection bar spans the float."""

    def create_content(self, width: int, height: int) -> UIContent:
        from prompt_toolkit.application.current import get_app

        complete_state = get_app().current_buffer.complete_state
        if not complete_state:
            return UIContent()

        completions = complete_state.completions
        index = complete_state.complete_index
        show_meta = self._show_meta(complete_state)
        menu_width = self._get_menu_width(width, complete_state)
        if show_meta:
            # Stretch descriptions so highlight / panel fill the compose box.
            menu_meta_width = max(0, width - menu_width)
        else:
            menu_width = max(menu_width, width)
            menu_meta_width = 0

        def get_line(i: int):
            c = completions[i]
            is_current = i == index
            result = _get_menu_item_fragments(
                c, is_current, menu_width, space_after=True
            )
            if show_meta and menu_meta_width > 0:
                result += self._get_menu_item_meta_fragments(
                    c, is_current, menu_meta_width
                )
            return result

        return UIContent(
            get_line=get_line,
            cursor_position=Point(x=0, y=index or 0),
            line_count=len(completions),
        )


class ComposeCompletionsMenu(ConditionalContainer):
    """Slash/@ menu sized to the compose panel (full width, accent ┃ border)."""

    def __init__(
        self,
        max_height: int = 12,
        scroll_offset: int = 1,
        *,
        lift: int = 1,
    ) -> None:
        from prompt_toolkit.layout.containers import ScrollOffsets

        menu = Window(
            content=_FullWidthCompletionsMenuControl(),
            width=Dimension(),
            height=Dimension(min=1, max=max_height),
            scroll_offsets=ScrollOffsets(top=scroll_offset, bottom=scroll_offset),
            # Thin gray scrollbar (not theme accent).
            right_margins=[ScrollbarMargin(display_arrows=False)],
            dont_extend_width=False,
            style="class:completion-menu",
            z_index=10**8,
        )
        # Bottom pad stays inside the menu panel (same fill + accent ┃), so it
        # reads as margin above the input — not a canvas hole between boxes.
        panel = menu
        if lift > 0:
            panel = HSplit(
                [
                    menu,
                    Window(
                        height=Dimension.exact(lift),
                        char=" ",
                        style="class:completion-menu",
                    ),
                ],
                padding=0,
            )
        body = VSplit(
            [
                Window(
                    width=1,
                    char="┃",
                    style="class:transcript-compose-accent",
                ),
                panel,
            ],
            padding=0,
        )
        super().__init__(
            content=body,
            filter=to_filter(True) & has_completions & ~is_done,
        )

# Base prompt_toolkit style (host PromptSession). Transcript TUI overlays
# theme-aware completion-menu colors via ``transcript_style_dict``.
PT_STYLE = Style.from_dict({
    "prompt": "bold #50fa7b",
    # Force plain, non-reversed toolbar text so no default
    # prompt_toolkit badge/background styling bleeds through.
    "bottom-toolbar": "noinherit noreverse #8a8f98 bg:default",
    "bottom-toolbar.text": "noinherit noreverse #8a8f98 bg:default",
    # Neutral fallback when not inside the themed transcript app.
    "completion-menu": "bg:#f5f5f5 #222222",
    "completion-menu.completion": "bg:#f5f5f5 #222222",
    "completion-menu.completion.current": "bg:#c9a227 #111111 bold",
    "completion-menu.meta.completion": "bg:#f5f5f5 #8a8f98",
    "completion-menu.meta.completion.current": "bg:#c9a227 #111111",
    "scrollbar.background": "bg:#f5f5f5",
    "scrollbar.button": "bg:#c8c8c8",
    "scrollbar.arrow": "bg:#f5f5f5 #aaaaaa",
    # Mention kind colors
    "mention-tool": "#00d7ff",     # cyan for tool mentions
    "mention-dataset": "#50fa7b",  # green for dataset mentions
    "mention-file": "#ffd700",     # yellow for file mentions
    "mention-workflow": "#ff79c6",  # pink for workflow mentions
    # Image attach chips — orange chip on dark
    "image-chip": "bold #111111 bg:#f0a030",
})


class SlashCompleter(Completer):
    """Autocomplete slash commands when input starts with /."""

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if text.startswith("/"):
            for cmd, desc in SLASH_COMMANDS.items():
                if cmd.startswith(text):
                    yield Completion(
                        cmd,
                        start_position=-len(text),
                        display_meta=desc,
                    )


class MentionCompleter(Completer):
    """Autocomplete tools, datasets, and files when input contains @.

    Supports tabbed filtering via TABS (All / Tools / DB / Files).
    Candidates are ``(name, category, description, kind)`` tuples where
    *kind* is ``"tool"``, ``"dataset"``, or ``"file"``.
    """

    TABS = ["All", "Tools", "DB", "Files", "Flows"]
    _TAB_FILTERS = {
        0: None,          # All
        1: "tool",        # Tools
        2: "dataset",     # DB
        3: "file",        # Files
        4: "workflow",    # Flows
    }

    def __init__(
        self,
        candidates: list[tuple[str, str, str, str]] | None = None,
        *,
        lazy_loader: Callable[[], list[tuple[str, str, str, str]]] | None = None,
    ):
        self.candidates = candidates or []
        self._active_tab = 0
        self._lazy_loader = lazy_loader
        self._lazy_loaded = lazy_loader is None

    def set_candidates(self, candidates: list[tuple[str, str, str, str]]) -> None:
        self.candidates = candidates

    def _ensure_lazy_loaded(self) -> None:
        if self._lazy_loaded:
            return
        self._lazy_loaded = True
        if self._lazy_loader is None:
            return
        try:
            loaded = self._lazy_loader()
            if loaded:
                self.set_candidates(loaded)
        except Exception:
            # Keep initial lightweight candidates if background loading fails.
            pass

    def get_completions(self, document, complete_event):
        self._ensure_lazy_loaded()
        text = document.text_before_cursor
        # Find the last @ in the text
        at_pos = text.rfind("@")
        if at_pos < 0:
            return

        partial = text[at_pos + 1:].lower()
        replace_len = len(text) - at_pos  # replace from @ onwards

        # Filter by active tab
        kind_filter = self._TAB_FILTERS.get(self._active_tab)

        # Group by category for ordering
        by_category: dict[str, list[tuple]] = {}
        for name, category, description, kind in self.candidates:
            if kind_filter and kind != kind_filter:
                continue
            # Case-insensitive substring match against name, category, description
            if (partial in name.lower()
                    or partial in category.lower()
                    or partial in description.lower()):
                by_category.setdefault(category, []).append(
                    (name, description, kind)
                )

        # Style mapping per kind
        styles = {
            "tool": "class:mention-tool",
            "dataset": "class:mention-dataset",
            "file": "class:mention-file",
            "workflow": "class:mention-workflow",
        }

        for category in sorted(by_category):
            for name, description, kind in sorted(by_category[category]):
                yield Completion(
                    f"@{name}",
                    start_position=-replace_len,
                    display_meta=description,
                    style=styles.get(kind, ""),
                )


class MergedCompleter(Completer):
    """Delegates to SlashCompleter for / and MentionCompleter for @."""

    def __init__(self, slash: Completer, mention: MentionCompleter):
        self._slash = slash
        self._mention = mention

    @property
    def mention_completer(self) -> MentionCompleter:
        return self._mention

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if text.lstrip().startswith("/"):
            yield from self._slash.get_completions(document, complete_event)
        elif "@" in text:
            yield from self._mention.get_completions(document, complete_event)
