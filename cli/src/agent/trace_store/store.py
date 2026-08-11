"""TraceStore: captures and persists full agent message stream traces."""

import json
import logging
import time
from pathlib import Path

from .helpers import embed_plots

logger = logging.getLogger("trace_store")


class TraceStore:
    """Captures and persists full agent message stream traces.

    Usage::

        store = TraceStore(session_id="abc-123")
        events = []

        # ... pass events list to process_messages() ...

        store.add_events(events, query="my question", model="claude-sonnet-4-5")
        store.flush()  # persist to ~/.sandwalk/sessions/abc-123.trace.jsonl
    """

    def __init__(self, session_id: str):
        # Resolved lazily via the package attribute so tests can monkeypatch
        # `agent.trace_store._sessions_dir`.
        from agent import trace_store as _pkg

        self.session_id = session_id
        self._events: list[dict] = []
        self._path = _pkg._sessions_dir() / f"{session_id}.trace.jsonl"

    @property
    def path(self) -> Path:
        return self._path

    @property
    def events(self) -> list[dict]:
        return self._events

    def add_event(self, event: dict) -> None:
        """Add a single trace event."""
        if "timestamp" not in event:
            event["timestamp"] = time.time()
        self._events.append(event)

    def add_events(
        self,
        events: list[dict],
        query: str = "",
        model: str = "",
        duration_s: float = 0.0,
        cost_usd: float = 0.0,
    ) -> None:
        """Wrap a list of trace events with query_start/query_end and add them.

        Also performs eager base64 embedding of plots.
        """
        now = time.time()

        # query_start
        self._events.append({
            "type": "query_start",
            "session_id": self.session_id,
            "query": query,
            "model": model,
            "timestamp": now,
        })

        # Add all events (with plot embedding)
        for event in events:
            if event.get("type") == "tool_result" and event.get("plots"):
                embed_plots(event)
            self._events.append(event)

        # query_end
        self._events.append({
            "type": "query_end",
            "duration_s": duration_s,
            "cost_usd": cost_usd,
            "timestamp": time.time(),
        })

    def flush(self, path: Path | None = None) -> Path:
        """Persist all events to a JSONL file. Appends if file exists."""
        out = path or self._path
        out.parent.mkdir(parents=True, exist_ok=True)

        with open(out, "a", encoding="utf-8") as f:
            for event in self._events:
                f.write(json.dumps(event, default=str) + "\n")

        count = len(self._events)
        self._events.clear()
        logger.info("Flushed %d trace events to %s", count, out)
        return out

    @staticmethod
    def load(path: Path | str) -> list[dict]:
        """Load trace events from a JSONL file."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Trace file not found: {path}")

        events = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
        return events

    @staticmethod
    def find_trace(session_id: str | None = None) -> Path | None:
        """Find a trace file by session ID prefix, or return the most recent.

        Args:
            session_id: Session ID or prefix to match. If None, returns
                the most recent trace file.

        Returns:
            Path to the trace file, or None if not found.
        """
        from agent import trace_store as _pkg

        sessions_dir = _pkg._sessions_dir()
        traces = sorted(
            sessions_dir.glob("*.trace.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not traces:
            return None

        if session_id is None:
            return traces[0]

        # Exact match first
        exact = sessions_dir / f"{session_id}.trace.jsonl"
        if exact.exists():
            return exact

        # Prefix match
        for t in traces:
            if t.stem.replace(".trace", "").startswith(session_id):
                return t

        return None
