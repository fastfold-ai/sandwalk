"""Collapsed tool-card store: click or Ctrl+E expands details into the console."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCard:
    """One completed tool call kept for on-demand detail expansion."""

    name: str
    args: dict[str, Any] = field(default_factory=dict)
    result: str = ""
    duration: float = 0.0
    is_error: bool = False
    # Monotonic console line index when the compact header was printed.
    line_index: int = 0
    expanded: bool = False


class ToolExpandStore:
    """Registry of collapsed tool cards for the interactive session."""

    def __init__(self) -> None:
        self.cards: list[ToolCard] = []
        self.line_count = 0
        self._on_expand: Callable[[ToolCard], None] | None = None

    def bind_expand(self, callback: Callable[[ToolCard], None]) -> None:
        self._on_expand = callback

    def note_lines(self, n: int = 1) -> None:
        """Account for non-tool console output so click row mapping stays close."""
        self.line_count += max(0, int(n))

    def add(
        self,
        *,
        name: str,
        args: dict | None = None,
        result: str = "",
        duration: float = 0.0,
        is_error: bool = False,
        lines: int = 1,
    ) -> ToolCard:
        self.line_count += max(1, int(lines))
        card = ToolCard(
            name=name,
            args=dict(args or {}),
            result=result or "",
            duration=float(duration or 0.0),
            is_error=bool(is_error),
            line_index=self.line_count,
        )
        self.cards.append(card)
        return card

    def card_at_line(self, line_index: int) -> ToolCard | None:
        """Exact line hit, else nearest card within a small window."""
        if not self.cards:
            return None
        for card in self.cards:
            if card.line_index == line_index:
                return card
        nearest: ToolCard | None = None
        best = 3
        for card in self.cards:
            dist = abs(card.line_index - line_index)
            if dist < best:
                best = dist
                nearest = card
        return nearest

    def card_for_screen_row(self, *, rows_above_layout: int, y: int) -> ToolCard | None:
        """Map a click in the region above the prompt to a tool card.

        Assumes the host has not scrolled the block away (best-effort in Warp).
        """
        if rows_above_layout <= 0 or y < 0 or y >= rows_above_layout:
            return None
        # Visible rows above the prompt are the last ``rows_above_layout`` lines.
        first_visible = max(1, self.line_count - rows_above_layout + 1)
        clicked = first_visible + y
        return self.card_at_line(clicked)

    def last_collapsed(self) -> ToolCard | None:
        for card in reversed(self.cards):
            if not card.expanded:
                return card
        return self.cards[-1] if self.cards else None

    def expand(self, card: ToolCard | None = None) -> ToolCard | None:
        target = card or self.last_collapsed()
        if target is None:
            return None
        target.expanded = True
        if self._on_expand is not None:
            self._on_expand(target)
        return target
