"""Benchmark question suite loading (built-in fallback + JSON config)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from agent.model_benchmark.models import DEFAULT_SUITE_PATH, BenchmarkQuestion


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def default_questions() -> list[BenchmarkQuestion]:
    """Built-in suite used when the JSON config is missing."""
    return [
        BenchmarkQuestion(
            id="hi",
            prompt="hi",
            description="Latency / connectivity smoke",
        ),
        BenchmarkQuestion(
            id="math",
            prompt="What is 17 multiplied by 19? Reply with only the number.",
            expect_contains=["323"],
            description="Short deterministic reasoning check",
        ),
        BenchmarkQuestion(
            id="kras",
            prompt=(
                "In one short sentence, what is the KRAS G12C mutation "
                "in cancer biology?"
            ),
            expect_contains=["kras"],
            description="Domain knowledge smoke (case-insensitive contains)",
        ),
    ]


def load_suite(path: Path | None = None) -> tuple[str, list[BenchmarkQuestion]]:
    """Load questions from JSON. Returns (suite_name, questions)."""
    source = path or DEFAULT_SUITE_PATH
    if not source.exists():
        return "builtin", default_questions()
    raw = json.loads(source.read_text(encoding="utf-8"))
    name = str(raw.get("name") or source.stem)
    questions: list[BenchmarkQuestion] = []
    for item in raw.get("questions") or []:
        if not isinstance(item, dict):
            continue
        qid = str(item.get("id") or "").strip()
        prompt = str(item.get("prompt") or "").strip()
        if not qid or not prompt:
            continue
        expects = item.get("expectContains") or item.get("expect_contains") or []
        if isinstance(expects, str):
            expects = [expects]
        questions.append(
            BenchmarkQuestion(
                id=qid,
                prompt=prompt,
                expect_contains=[str(x) for x in expects if str(x).strip()],
                description=str(item.get("description") or ""),
            )
        )
    if not questions:
        return name, default_questions()
    return name, questions
