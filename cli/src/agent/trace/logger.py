"""TraceLogger: collect, persist, and analyze query trace events."""

from __future__ import annotations

from typing import Any

from .diagnostics import DiagnosticsMixin
from .persistence import PersistenceMixin
from .recording import RecordingMixin


class TraceLogger(RecordingMixin, PersistenceMixin, DiagnosticsMixin):
    """Collect, persist, and analyze query trace events."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.events: list[dict[str, Any]] = []
