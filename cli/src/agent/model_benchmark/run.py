"""Sequential benchmark run execution, report writing, and preview rows."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from agent.model_benchmark.invoke import invoke_case
from agent.model_benchmark.models import BenchmarkCase, BenchmarkCaseResult, BenchmarkRun
from agent.model_benchmark.suite import _utc_now


def run_benchmark(
    cases: list[BenchmarkCase],
    *,
    suite_name: str = "default",
    with_tools: bool = True,
    on_case_start: Callable[[int, int, BenchmarkCase], None] | None = None,
    on_case_done: Callable[[BenchmarkCaseResult], None] | None = None,
    build_model: Callable[..., Any] | None = None,
    config: Any | None = None,
) -> BenchmarkRun:
    """Execute cases sequentially and return a structured run report."""
    run = BenchmarkRun(
        id=str(uuid.uuid4()),
        suite=suite_name,
        started_at=_utc_now(),
        finished_at=None,
        cases=list(cases),
    )
    total = len(cases)
    for index, case in enumerate(cases, start=1):
        if on_case_start:
            on_case_start(index, total, case)
        result = invoke_case(
            case,
            with_tools=with_tools,
            build_model=build_model,
            config=config,
        )
        run.results.append(result)
        if on_case_done:
            on_case_done(result)
    run.finished_at = _utc_now()
    return run


def write_run_report(run: BenchmarkRun, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(run.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def cases_to_preview(cases: list[BenchmarkCase]) -> list[dict[str, Any]]:
    """Dry-run friendly matrix rows."""
    return [
        {
            "provider": case.target.provider,
            "model": case.target.model,
            "label": case.target.label,
            "effort": case.effort,
            "questionId": case.question.id,
            "supportsReasoningEffort": case.target.supports_reasoning_effort,
        }
        for case in cases
    ]
