"""Ordered transcript entries for the owned interactive TUI."""

from __future__ import annotations

import itertools
import threading
from dataclasses import dataclass, field
from typing import Any, Callable


_ids = itertools.count(1)


@dataclass
class TextEntry:
    """Plain / markdown-ish text block (user, assistant, system chrome)."""

    text: str
    kind: str = "text"  # text | user | assistant | system
    entry_id: int = field(default_factory=lambda: next(_ids))


@dataclass
class ToolEntry:
    """Collapsible tool card shown as one line until expanded in place."""

    name: str
    args: dict[str, Any] = field(default_factory=dict)
    result: str = ""
    duration: float = 0.0
    is_error: bool = False
    expanded: bool = False
    entry_id: int = field(default_factory=lambda: next(_ids))


@dataclass
class SeparatorEntry:
    entry_id: int = field(default_factory=lambda: next(_ids))
    kind: str = "separator"


Entry = TextEntry | ToolEntry | SeparatorEntry


class TranscriptStore:
    """Thread-safe transcript backing the scrollable TUI window."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.entries: list[Entry] = []
        self.scroll_offset = 0  # lines from bottom; 0 = pinned to end
        self.follow_tail = True
        self._listeners: list[Callable[[], None]] = []

    def subscribe(self, callback: Callable[[], None]) -> None:
        self._listeners.append(callback)

    def _notify(self) -> None:
        for cb in list(self._listeners):
            try:
                cb()
            except Exception:  # noqa: BLE001
                pass

    def clear(self) -> None:
        with self._lock:
            self.entries.clear()
            self.scroll_offset = 0
            self.follow_tail = True
        self._notify()

    def append_text(self, text: str, *, kind: str = "text") -> TextEntry:
        entry = TextEntry(text=text.rstrip("\n"), kind=kind)
        with self._lock:
            self.entries.append(entry)
            if self.follow_tail:
                self.scroll_offset = 0
        self._notify()
        return entry

    def append_separator(self) -> SeparatorEntry:
        entry = SeparatorEntry()
        with self._lock:
            self.entries.append(entry)
            if self.follow_tail:
                self.scroll_offset = 0
        self._notify()
        return entry

    def append_tool(
        self,
        *,
        name: str,
        args: dict | None = None,
        result: str = "",
        duration: float = 0.0,
        is_error: bool = False,
        expanded: bool = False,
    ) -> ToolEntry:
        entry = ToolEntry(
            name=name,
            args=dict(args or {}),
            result=result or "",
            duration=float(duration or 0.0),
            is_error=bool(is_error),
            expanded=bool(expanded),
        )
        with self._lock:
            self.entries.append(entry)
            if self.follow_tail:
                self.scroll_offset = 0
        self._notify()
        return entry

    def get_tool(self, entry_id: int) -> ToolEntry | None:
        with self._lock:
            for entry in self.entries:
                if isinstance(entry, ToolEntry) and entry.entry_id == entry_id:
                    return entry
        return None

    def toggle_tool(self, entry_id: int) -> ToolEntry | None:
        with self._lock:
            for entry in self.entries:
                if isinstance(entry, ToolEntry) and entry.entry_id == entry_id:
                    entry.expanded = not entry.expanded
                    self._notify()
                    return entry
        return None

    def toggle_last_tool(self) -> ToolEntry | None:
        with self._lock:
            for entry in reversed(self.entries):
                if isinstance(entry, ToolEntry):
                    entry.expanded = not entry.expanded
                    self._notify()
                    return entry
        return None

    def snapshot(self) -> list[Entry]:
        with self._lock:
            return list(self.entries)

    def scroll_lines(self, delta: int, *, viewport: int, total_lines: int) -> None:
        """Move the viewport; positive delta scrolls up into history."""
        if total_lines <= viewport:
            self.scroll_offset = 0
            self.follow_tail = True
            self._notify()
            return
        max_off = total_lines - viewport
        with self._lock:
            self.scroll_offset = max(0, min(max_off, self.scroll_offset + delta))
            self.follow_tail = self.scroll_offset == 0
        self._notify()

    def pin_tail(self) -> None:
        with self._lock:
            self.scroll_offset = 0
            self.follow_tail = True
        self._notify()
