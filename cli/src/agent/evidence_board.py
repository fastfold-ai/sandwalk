"""
Shared evidence board for multi-agent parallel research.

Provides a thread-safe store where parallel research threads post
findings as they complete steps, allowing other threads to
optionally reference cross-thread discoveries.
"""

import threading
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class EvidenceEntry:
    """A single piece of evidence posted by a research thread."""
    thread_id: int
    step_id: Any
    tool: str
    summary: str
    data: dict = field(default_factory=dict)


class EvidenceBoard:
    """Thread-safe shared evidence store for parallel agent threads.

    Threads call ``post()`` after each completed step. The orchestrator
    reads ``__len__`` for display and can call ``get_all()`` for synthesis.
    """

    def __init__(self):
        self._entries: list[EvidenceEntry] = []
        self._lock = threading.Lock()

    def post(self, thread_id: int, step_id: Any, tool: str,
             summary: str, data: Optional[dict] = None) -> None:
        """Post a new evidence entry (thread-safe)."""
        entry = EvidenceEntry(
            thread_id=thread_id,
            step_id=step_id,
            tool=tool,
            summary=summary,
            data=data or {},
        )
        with self._lock:
            self._entries.append(entry)

    def get_all(self) -> list[EvidenceEntry]:
        """Return a snapshot of all entries (thread-safe)."""
        with self._lock:
            return list(self._entries)

    def get_by_thread(self, thread_id: int) -> list[EvidenceEntry]:
        """Return entries posted by a specific thread."""
        with self._lock:
            return [e for e in self._entries if e.thread_id == thread_id]

    def to_context_str(self) -> str:
        """Render board contents as a compact string for LLM context."""
        entries = self.get_all()
        if not entries:
            return ""
        lines = ["Cross-thread evidence board:"]
        for e in entries:
            lines.append(f"  [Thread {e.thread_id} / {e.tool}] {e.summary}")
        return "\n".join(lines)

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    def __repr__(self) -> str:
        return f"EvidenceBoard({len(self)} entries)"
