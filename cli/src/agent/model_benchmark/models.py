"""Dataclasses + shared constants for the model benchmark harness."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent.model_catalog import REASONING_EFFORT_LEVELS

DEFAULT_SUITE_PATH = (
    Path(__file__).resolve().parents[3] / "configs" / "model_benchmarks.json"
)

# Effort tokens exposed in the matrix / UI. ``fast`` maps to reasoning_fast=True
# (API effort ``none``); ``none`` is only used when a model has no effort UI.
EFFORT_MATRIX_VALUES = (*REASONING_EFFORT_LEVELS, "fast")


@dataclass(frozen=True)
class BenchmarkQuestion:
    id: str
    prompt: str
    expect_contains: list[str] = field(default_factory=list)
    description: str = ""


@dataclass(frozen=True)
class BenchmarkTarget:
    provider: str
    model: str
    label: str
    source: str = "cloud"
    profile_id: str | None = None
    supports_reasoning_effort: bool = False


@dataclass(frozen=True)
class BenchmarkCase:
    target: BenchmarkTarget
    question: BenchmarkQuestion
    """Effort token: low|medium|high|fast, or None when model has no effort control."""
    effort: str | None


@dataclass
class BenchmarkCaseResult:
    provider: str
    model: str
    label: str
    source: str
    profile_id: str | None
    supports_reasoning_effort: bool
    effort: str | None
    question_id: str
    question: str
    ok: bool
    latency_ms: int
    preview: str | None = None
    error: str | None = None
    expect_ok: bool | None = None
    usage: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "label": self.label,
            "source": self.source,
            "profileId": self.profile_id,
            "supportsReasoningEffort": self.supports_reasoning_effort,
            "effort": self.effort,
            "questionId": self.question_id,
            "question": self.question,
            "ok": self.ok,
            "latencyMs": self.latency_ms,
            "preview": self.preview,
            "error": self.error,
            "expectOk": self.expect_ok,
            "usage": self.usage,
        }


@dataclass
class BenchmarkRun:
    id: str
    suite: str
    started_at: str
    finished_at: str | None
    cases: list[BenchmarkCase]
    results: list[BenchmarkCaseResult] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        total = len(self.results)
        passed = sum(1 for row in self.results if row.ok)
        failed = total - passed
        by_provider: dict[str, dict[str, int]] = {}
        by_effort: dict[str, dict[str, int]] = {}
        for row in self.results:
            p = by_provider.setdefault(row.provider, {"passed": 0, "failed": 0})
            e_key = row.effort or "default"
            e = by_effort.setdefault(e_key, {"passed": 0, "failed": 0})
            bucket = "passed" if row.ok else "failed"
            p[bucket] += 1
            e[bucket] += 1
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "byProvider": by_provider,
            "byEffort": by_effort,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "suite": self.suite,
            "startedAt": self.started_at,
            "finishedAt": self.finished_at,
            "matrix": {
                "caseCount": len(self.cases),
                "models": sorted(
                    {
                        f"{c.target.provider}/{c.target.model}"
                        for c in self.cases
                    }
                ),
                "efforts": sorted(
                    {c.effort or "default" for c in self.cases}
                ),
                "questions": sorted({c.question.id for c in self.cases}),
            },
            "results": [row.to_dict() for row in self.results],
            "summary": self.summary(),
        }
