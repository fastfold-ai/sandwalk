"""prompt_toolkit style + completers for slash commands and @ mentions."""

from __future__ import annotations

from collections.abc import Callable

from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.styles import Style

from ui.terminal.slash_commands import SLASH_COMMANDS

# prompt_toolkit style — colored prompt, dark completion menu
PT_STYLE = Style.from_dict({
    "prompt": "bold #50fa7b",
    # Force plain, non-reversed toolbar text so no default
    # prompt_toolkit badge/background styling bleeds through.
    "bottom-toolbar": "noinherit noreverse #8a8f98 bg:default",
    "bottom-toolbar.text": "noinherit noreverse #8a8f98 bg:default",
    # Completion menu — dark background so mention colors stay readable
    "completion-menu": "bg:#1a1a2e #cccccc",
    "completion-menu.completion": "bg:#1a1a2e #cccccc",
    "completion-menu.completion.current": "bg:#333355 #ffffff bold",
    "completion-menu.meta.completion": "bg:#1a1a2e #888888",
    "completion-menu.meta.completion.current": "bg:#333355 #aaaaaa",
    "scrollbar.background": "bg:#1a1a2e",
    "scrollbar.button": "bg:#333355",
    # Mention kind colors
    "mention-tool": "#00d7ff",     # cyan for tool mentions
    "mention-dataset": "#50fa7b",  # green for dataset mentions
    "mention-file": "#ffd700",     # yellow for file mentions
    "mention-workflow": "#ff79c6",  # pink for workflow mentions
    # Image attach chips — OpenCode-like orange on dark
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
