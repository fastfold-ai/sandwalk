"""Lightweight trace logger used by CLI trace diagnostics/export commands."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class TraceLogger:
    """Collect, persist, and analyze query trace events."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.events: list[dict[str, Any]] = []

    @staticmethod
    def traces_dir() -> Path:
        d = Path.home() / ".fastfold-cli" / "traces"
        d.mkdir(parents=True, exist_ok=True)
        return d

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
        self, iterations: int = 0, total_steps: int = 0, completed_steps: int = 0, failed_steps: int = 0
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

    def save(self, path: Path | None = None) -> Path:
        out = path or (self.traces_dir() / f"{self.session_id}.trace.jsonl")
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as f:
            for event in self.events:
                f.write(json.dumps(event, default=str) + "\n")
        return out

    @classmethod
    def load(cls, path: Path | str) -> TraceLogger:
        p = Path(path)
        events: list[dict[str, Any]] = []
        with p.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
        session_id = ""
        for e in events:
            if e.get("type") == "query_start" and e.get("session_id"):
                session_id = str(e["session_id"])
                break
        if not session_id:
            session_id = p.stem.replace(".trace", "")
        obj = cls(session_id=session_id)
        obj.events = events
        return obj

    def to_text(self) -> str:
        return "\n".join(json.dumps(e, default=str) for e in self.events)

    def query_summaries(self) -> list[dict[str, Any]]:
        diag = self.diagnostics()
        return [
            {
                "query_number": q["query_number"],
                "query": q["query"],
                "closed": q["closed"],
                "plan_count": q["plan_count"],
                "step_complete_count": q["step_complete_count"],
                "step_fail_count": q["step_fail_count"],
            }
            for q in diag["queries"]
        ]

    def diagnostics(self) -> dict[str, Any]:
        queries: list[dict[str, Any]] = []
        current: dict[str, Any] | None = None
        qn = 0

        for e in self.events:
            t = e.get("type")
            if t == "query_start":
                if current is not None:
                    queries.append(current)
                qn += 1
                current = {
                    "query_number": qn,
                    "query": e.get("query", ""),
                    "closed": False,
                    "plan_count": 0,
                    "step_start_count": 0,
                    "step_complete_count": 0,
                    "step_fail_count": 0,
                    "step_retry_count": 0,
                    "synthesize_start_count": 0,
                    "synthesize_end_count": 0,
                }
                continue

            if current is None:
                continue

            if t == "plan":
                current["plan_count"] += 1
            elif t == "step_start":
                current["step_start_count"] += 1
            elif t == "step_complete":
                current["step_complete_count"] += 1
            elif t == "step_fail":
                current["step_fail_count"] += 1
            elif t == "step_retry":
                current["step_retry_count"] += 1
            elif t == "synthesize_start":
                current["synthesize_start_count"] += 1
            elif t == "synthesize_end":
                current["synthesize_end_count"] += 1
            elif t == "query_end":
                current["closed"] = True
                queries.append(current)
                current = None

        if current is not None:
            queries.append(current)

        unclosed = [q["query_number"] for q in queries if not q["closed"]]
        no_plan = [q["query_number"] for q in queries if q["plan_count"] == 0]
        no_completion = [q["query_number"] for q in queries if q["step_complete_count"] == 0]
        synth_mismatch = [
            q["query_number"]
            for q in queries
            if q["synthesize_start_count"] != q["synthesize_end_count"]
        ]

        return {
            "session_id": self.session_id,
            "event_count": len(self.events),
            "query_count": len(queries),
            "query_start_count": len(queries),
            "query_end_count": sum(1 for q in queries if q["closed"]),
            "total_step_start_count": sum(q["step_start_count"] for q in queries),
            "total_step_complete_count": sum(q["step_complete_count"] for q in queries),
            "total_step_fail_count": sum(q["step_fail_count"] for q in queries),
            "total_step_retry_count": sum(q["step_retry_count"] for q in queries),
            "unclosed_queries": unclosed,
            "queries_with_failures": [q["query_number"] for q in queries if q["step_fail_count"] > 0],
            "queries_with_no_plan": no_plan,
            "queries_with_no_completion": no_completion,
            "queries_with_synthesis_mismatch": synth_mismatch,
            "queries": queries,
        }
