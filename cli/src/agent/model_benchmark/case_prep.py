"""Case matrix expansion and response-content extraction helpers."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from agent.model_benchmark.models import (
    EFFORT_MATRIX_VALUES,
    BenchmarkCase,
    BenchmarkQuestion,
    BenchmarkTarget,
)


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


def extract_text(content: Any) -> str:
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


def usage_from_message(message: Any) -> dict[str, Any] | None:
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


def check_expectations(text: str, expects: list[str]) -> bool | None:
    if not expects:
        return None
    haystack = text.lower()
    return all(str(item).lower() in haystack for item in expects)
