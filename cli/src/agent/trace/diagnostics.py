"""Diagnostics/summary analysis for TraceLogger."""

from __future__ import annotations

from typing import Any


class DiagnosticsMixin:
    """Adds `diagnostics` and `query_summaries` to TraceLogger."""

    session_id: str
    events: list[dict[str, Any]]

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
            "queries_with_failures": [
                q["query_number"] for q in queries if q["step_fail_count"] > 0
            ],
            "queries_with_no_plan": no_plan,
            "queries_with_no_completion": no_completion,
            "queries_with_synthesis_mismatch": synth_mismatch,
            "queries": queries,
        }
