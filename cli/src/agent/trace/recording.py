"""Event-recording methods for TraceLogger."""

from __future__ import annotations

import time
from typing import Any


class RecordingMixin:
    """Adds `_append` and the query/step/synthesize event recorders."""

    events: list[dict[str, Any]]
    session_id: str

    def _append(self, payload: dict[str, Any]) -> None:
        if "timestamp" not in payload:
            payload["timestamp"] = time.time()
        self.events.append(payload)

    def query_start(self, query: str) -> None:
        self._append({"type": "query_start", "query": query, "session_id": self.session_id})

    def plan(self, steps: list[dict[str, Any]], query: str = "") -> None:
        self._append({"type": "plan", "steps": steps, "query": query})

    def step_start(self, step_number: int, tool: str, args: dict[str, Any]) -> None:
        self._append(
            {
                "type": "step_start",
                "step_number": step_number,
                "tool": tool,
                "args": args,
            }
        )

    def step_complete(
        self, step_number: int, tool: str, result: dict[str, Any], duration_s: float = 0.0
    ) -> None:
        self._append(
            {
                "type": "step_complete",
                "step_number": step_number,
                "tool": tool,
                "result": result,
                "duration_s": duration_s,
            }
        )

    def step_fail(
        self, step_number: int, tool: str, error: str, duration_s: float = 0.0
    ) -> None:
        self._append(
            {
                "type": "step_fail",
                "step_number": step_number,
                "tool": tool,
                "error": error,
                "duration_s": duration_s,
            }
        )

    def step_retry(self, step_number: int, tool: str, reason: str = "") -> None:
        self._append(
            {"type": "step_retry", "step_number": step_number, "tool": tool, "reason": reason}
        )

    def synthesize_start(self) -> None:
        self._append({"type": "synthesize_start"})

    def synthesize_end(self, token_count: int = 0, duration_s: float = 0.0) -> None:
        self._append(
            {
                "type": "synthesize_end",
                "token_count": token_count,
                "duration_s": duration_s,
            }
        )

    def query_end(
        self,
        iterations: int = 0,
        total_steps: int = 0,
        completed_steps: int = 0,
        failed_steps: int = 0,
    ) -> None:
        self._append(
            {
                "type": "query_end",
                "iterations": iterations,
                "total_steps": total_steps,
                "completed_steps": completed_steps,
                "failed_steps": failed_steps,
            }
        )
