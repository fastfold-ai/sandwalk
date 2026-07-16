"""Run a single benchmark case against a live (or injected) chat model."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from agent.model_benchmark.case_prep import (
    check_expectations,
    extract_text,
    usage_from_message,
)
from agent.model_benchmark.models import BenchmarkCase, BenchmarkCaseResult
from agent.model_catalog import REASONING_EFFORT_LEVELS


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
        text = extract_text(getattr(message, "content", message))
        expect_ok = check_expectations(text, question.expect_contains)
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
            usage=usage_from_message(message),
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
