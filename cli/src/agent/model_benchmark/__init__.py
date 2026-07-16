"""Model catalog performance benchmark harness.

Runs a suite of sample questions across cloud (and optional local) catalog
models, optionally varying reasoning effort / Fast. Designed as the shared
engine for:

- ``python scripts/benchmark.py`` (CLI automation)
- a future agent-server ``/v1/benchmarks`` + local-web UI

Result JSON is stable camelCase-friendly dicts so the web client can render
runs without reshaping.

Split across sibling modules (dataclasses/constants, suite loading, target
collection, case expansion, invocation, run orchestration) to stay under the
file-length cap; this package re-exports the full public surface.
"""

from __future__ import annotations

from dataclasses import asdict

from agent.model_benchmark.case_prep import expand_cases
from agent.model_benchmark.invoke import invoke_case
from agent.model_benchmark.models import (
    DEFAULT_SUITE_PATH,
    EFFORT_MATRIX_VALUES,
    BenchmarkCase,
    BenchmarkCaseResult,
    BenchmarkQuestion,
    BenchmarkRun,
    BenchmarkTarget,
)
from agent.model_benchmark.run import cases_to_preview, run_benchmark, write_run_report
from agent.model_benchmark.suite import default_questions, load_suite
from agent.model_benchmark.targets import collect_cloud_targets

__all__ = [
    "BenchmarkCase",
    "BenchmarkCaseResult",
    "BenchmarkQuestion",
    "BenchmarkRun",
    "BenchmarkTarget",
    "DEFAULT_SUITE_PATH",
    "EFFORT_MATRIX_VALUES",
    "asdict",
    "cases_to_preview",
    "collect_cloud_targets",
    "default_questions",
    "expand_cases",
    "invoke_case",
    "load_suite",
    "run_benchmark",
    "write_run_report",
]
