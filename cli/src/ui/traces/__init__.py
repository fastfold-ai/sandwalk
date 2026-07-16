"""
Execution trace rendering for tool calls.

Renders real-time trace panels showing tool name, arguments, results,
and timing — used by both the SDK runner and legacy executor paths.

``TraceRenderer`` is assembled from focused mixins (tool events, background
task events, reasoning/todos) so each concern stays in its own module.
"""

from __future__ import annotations

from rich.console import Console

from ui.markdown import print_markdown_with_mermaid
from ui.traces.formatting import format_args, format_duration, truncate_output
from ui.traces.reasoning import _ReasoningMixin
from ui.traces.tasks import _TaskEventsMixin
from ui.traces.tool_events import _ToolEventsMixin

__all__ = [
    "TraceRenderer",
    "format_args",
    "format_duration",
    "truncate_output",
    "print_markdown_with_mermaid",
]


class TraceRenderer(_ToolEventsMixin, _TaskEventsMixin, _ReasoningMixin):
    """Renders tool call traces to a Rich Console.

    Accepts a ``Console`` at construction so tests can pass
    ``Console(file=StringIO())`` to capture output.
    """

    def __init__(self, console: Console | None = None, config=None):
        self.console = console or Console()
        self.config = config
