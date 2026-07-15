"""Model catalog performance benchmark harness.

Runs a suite of sample questions across cloud (and optional local) catalog
models, optionally varying reasoning effort / Fast. Designed as the shared
engine for:

- ``python scripts/benchmark.py`` (CLI automation)
- a future agent-server ``/v1/benchmarks`` + local-web UI

Result JSON is stable camelCase-friendly dicts so the web client can render
runs without reshaping.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timezone
from pathlib import Path
from typing import Any

from agent.model_catalog import (
    REASONING_EFFORT_LEVELS,
    cloud_catalog_models,
    model_supports_reasoning_effort,
    resolve_catalog_model_id,
)

DEFAULT_SUITE_PATH = (
    Path(__file__).resolve().parents[2] / "configs" / "model_benchmarks.json"
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


def collect_cloud_targets(
    *,
    provider: str | None = None,
    model: str | None = None,
    has_key: Callable[[str], bool] | None = None,
    discover: bool = True,
) -> list[BenchmarkTarget]:
    """Cloud catalog targets for providers with a configured API key.

    When ``discover`` is True and an OpenCode Zen key is set, also include
    live-discovered Zen models (minus the unsupported denylist).
    """
    targets: list[BenchmarkTarget] = []
    seen: set[tuple[str, str]] = set()
    for entry in cloud_catalog_models():
        prov = entry["provider"]
        mid = resolve_catalog_model_id(entry["id"])
        if provider and prov != provider:
            continue
        if model and mid != model and entry["id"] != model:
            continue
        if has_key is not None and not has_key(prov):
            continue
        seen.add((prov, mid))
        targets.append(
            BenchmarkTarget(
                provider=prov,
                model=mid,
                label=entry["label"],
                source="cloud",
                profile_id=None,
                supports_reasoning_effort=model_supports_reasoning_effort(
                    prov, mid
                ),
            )
        )

    if discover and (provider is None or provider == "opencode"):
        if has_key is None or has_key("opencode"):
            try:
                from agent_server.models_service import ModelsService

                listed = ModelsService().list_models(
                    discover=True, enabled_only=False
                )
            except Exception:
                listed = None
            if listed is not None:
                for item in listed.data:
                    if item.provider != "opencode":
                        continue
                    mid = resolve_catalog_model_id(item.id)
                    if model and mid != model and item.id != model:
                        continue
                    key = ("opencode", mid)
                    if key in seen:
                        continue
                    seen.add(key)
                    targets.append(
                        BenchmarkTarget(
                            provider="opencode",
                            model=mid,
                            label=item.label,
                            source="cloud",
                            profile_id=None,
                            supports_reasoning_effort=model_supports_reasoning_effort(
                                "opencode", mid
                            ),
                        )
                    )
    return targets


def expand_cases(
    targets: Iterable[BenchmarkTarget],
    questions: Iterable[BenchmarkQuestion],
    *,
    efforts: Iterable[str] | None = None,
) -> list[BenchmarkCase]:
    """Cartesian product of targets × questions × applicable efforts."""
    effort_list = list(efforts) if efforts is not None else list(EFFORT_MATRIX_VALUES)
    normalized_efforts: list[str] = []
    for raw in effort_list:
        value = str(raw or "").strip().lower()
        if value in EFFORT_MATRIX_VALUES and value not in normalized_efforts:
            normalized_efforts.append(value)
    if not normalized_efforts:
        normalized_efforts = list(EFFORT_MATRIX_VALUES)

    cases: list[BenchmarkCase] = []
    question_list = list(questions)
    for target in targets:
        if target.supports_reasoning_effort:
            effort_values: list[str | None] = list(normalized_efforts)
        else:
            effort_values = [None]
        for effort in effort_values:
            for question in question_list:
                cases.append(
                    BenchmarkCase(
                        target=target,
                        question=question,
                        effort=effort,
                    )
                )
    return cases


def _extract_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text") or ""))
            elif isinstance(item, dict) and "text" in item:
                parts.append(str(item.get("text") or ""))
            else:
                # Skip pure reasoning blobs when a text sibling exists later.
                text = getattr(item, "text", None)
                if text:
                    parts.append(str(text))
                elif not (
                    isinstance(item, dict) and item.get("type") == "reasoning"
                ):
                    parts.append(str(item))
        return "".join(parts).strip()
    text = getattr(content, "text", None)
    if text:
        return str(text).strip()
    return str(content).strip()


def _usage_from_message(message: Any) -> dict[str, Any] | None:
    meta = getattr(message, "usage_metadata", None)
    if isinstance(meta, dict) and meta:
        return {
            "input": meta.get("input_tokens") or meta.get("input"),
            "output": meta.get("output_tokens") or meta.get("output"),
            "total": meta.get("total_tokens") or meta.get("total"),
        }
    usage = getattr(message, "usage", None)
    if usage is None:
        return None
    if isinstance(usage, dict):
        return usage
    return {
        "input": getattr(usage, "input_tokens", None)
        or getattr(usage, "prompt_tokens", None),
        "output": getattr(usage, "output_tokens", None)
        or getattr(usage, "completion_tokens", None),
    }


def _check_expectations(text: str, expects: list[str]) -> bool | None:
    if not expects:
        return None
    haystack = text.lower()
    return all(str(item).lower() in haystack for item in expects)


def invoke_case(
    case: BenchmarkCase,
    *,
    with_tools: bool = True,
    build_model: Callable[..., Any] | None = None,
    config: Any | None = None,
) -> BenchmarkCaseResult:
    """Run a single benchmark case against a live (or injected) model."""
    from langchain_core.messages import HumanMessage

    from agent.config import Config
    from agent.deepagents_runtime import build_chat_model

    cfg = config if config is not None else Config.load()
    factory = build_model or build_chat_model
    target = case.target
    question = case.question

    previous = {
        "llm.provider": cfg.get("llm.provider"),
        "llm.model": cfg.get("llm.model"),
        "llm.reasoning_effort": cfg.get("llm.reasoning_effort"),
        "llm.reasoning_fast": cfg.get("llm.reasoning_fast"),
        "llm.model_reasoning": cfg.get("llm.model_reasoning"),
        "llm.openai_active_profile": cfg.get("llm.openai_active_profile"),
    }

    started = time.perf_counter()
    try:
        cfg.set("llm.provider", target.provider)
        cfg.set("llm.model", target.model)
        if target.profile_id:
            try:
                cfg.set_openai_active_profile(str(target.profile_id))
            except Exception:
                pass
        elif target.provider == "openai" and target.source == "cloud":
            try:
                cfg.set_openai_active_profile("openai_cloud")
            except Exception:
                pass

        if case.effort == "fast":
            from agent.model_catalog import upsert_model_reasoning

            store = upsert_model_reasoning(
                cfg.get("llm.model_reasoning"),
                target.provider,
                target.model,
                effort="medium",
                fast=True,
            )
            cfg.set("llm.model_reasoning", store)
            cfg.set("llm.reasoning_fast", True)
            cfg.set("llm.reasoning_effort", "medium")
        elif case.effort in REASONING_EFFORT_LEVELS:
            from agent.model_catalog import upsert_model_reasoning

            store = upsert_model_reasoning(
                cfg.get("llm.model_reasoning"),
                target.provider,
                target.model,
                effort=case.effort,
                fast=False,
            )
            cfg.set("llm.model_reasoning", store)
            cfg.set("llm.reasoning_fast", False)
            cfg.set("llm.reasoning_effort", case.effort)
        # else: leave config effort alone for non-reasoning models

        chat = factory(cfg, streaming=False)
        if with_tools:
            from langchain_core.tools import tool

            @tool
            def ping() -> str:
                """Health-check tool used only for benchmark smoke."""
                return "pong"

            chat = chat.bind_tools([ping])

        message = chat.invoke([HumanMessage(content=question.prompt)])
        text = _extract_text(getattr(message, "content", message))
        expect_ok = _check_expectations(text, question.expect_contains)
        ok = True if expect_ok is None else bool(expect_ok)
        latency_ms = int((time.perf_counter() - started) * 1000)
        return BenchmarkCaseResult(
            provider=target.provider,
            model=target.model,
            label=target.label,
            source=target.source,
            profile_id=target.profile_id,
            supports_reasoning_effort=target.supports_reasoning_effort,
            effort=case.effort,
            question_id=question.id,
            question=question.prompt,
            ok=ok,
            latency_ms=latency_ms,
            preview=text[:400] if text else "",
            error=None
            if ok
            else (
                f"Expected to contain {question.expect_contains!r}"
                if expect_ok is False
                else None
            ),
            expect_ok=expect_ok,
            usage=_usage_from_message(message),
        )
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        return BenchmarkCaseResult(
            provider=target.provider,
            model=target.model,
            label=target.label,
            source=target.source,
            profile_id=target.profile_id,
            supports_reasoning_effort=target.supports_reasoning_effort,
            effort=case.effort,
            question_id=question.id,
            question=question.prompt,
            ok=False,
            latency_ms=latency_ms,
            preview=None,
            error=f"{type(exc).__name__}: {exc}",
            expect_ok=False if question.expect_contains else None,
            usage=None,
        )
    finally:
        for key, value in previous.items():
            if value is None:
                continue
            try:
                cfg.set(key, value)
            except Exception:
                pass


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


# Re-export for callers that want dataclass dumps.
__all__ = [
    "BenchmarkCase",
    "BenchmarkCaseResult",
    "BenchmarkQuestion",
    "BenchmarkRun",
    "BenchmarkTarget",
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
