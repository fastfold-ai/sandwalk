"""Legacy completion-only MMLU runner (Bench UI uses agent sessions via mcq_suites)."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

from agent_server.bench_service.grade import (
    build_result,
    extract_mc_letter,
    grade_mc_letter,
)
from agent_server.bench_service.mcq_suites import format_mcq_prompt, load_mcq_items
from agent_server.bench_service.results_store import new_run_id, save_result

logger = logging.getLogger(__name__)

ANSWER_MAP = {0: "A", 1: "B", 2: "C", 3: "D"}


def load_mmlu_items(sample_size: int = 30) -> list[dict[str, Any]]:
    return load_mcq_items("mmlu", sample_size)


def format_mmlu_prompt(item: dict[str, Any]) -> str:
    return format_mcq_prompt("mmlu", item)


def run_mmlu(
    *,
    model_id: str,
    provider: str | None,
    sample_size: int,
    thinking: bool,
    on_progress: Callable[[dict[str, Any]], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    from agent.config import Config
    from agent.deepagents_runtime.chat_model import build_chat_model
    from agent_server.models import UpdateRuntimeSettingsRequest
    from agent_server.settings_service import SettingsService

    run_id = new_run_id()
    items = load_mmlu_items(sample_size)
    settings = SettingsService.get()
    orig = (settings.provider, settings.model)
    if model_id:
        SettingsService.update(
            UpdateRuntimeSettingsRequest(
                provider=provider or settings.provider,
                model=model_id,
            )
        )
    start = time.time()
    questions: list[dict[str, Any]] = []
    try:
        config = Config.load()
        model = build_chat_model(config)
        total = len(items)
        for idx, item in enumerate(items):
            if cancel_check and cancel_check():
                break
            if on_progress:
                on_progress(
                    {
                        "type": "progress",
                        "phase": "eval",
                        "model_id": model_id or orig[1],
                        "benchmark": "mmlu",
                        "message": f"Evaluating mmlu ({idx}/{total})...",
                        "current": 0,
                        "total": 1,
                        "bench_current": idx,
                        "bench_total": total,
                    }
                )
            prompt = format_mmlu_prompt(item)
            t0 = time.time()
            try:
                resp = model.invoke(prompt)
                text = getattr(resp, "content", None) or str(resp)
                if isinstance(text, list):
                    text = "".join(
                        b.get("text", "") if isinstance(b, dict) else str(b) for b in text
                    )
                text = str(text)
            except Exception as exc:  # noqa: BLE001
                text = f"ERROR: {exc}"
            predicted = extract_mc_letter(text)
            expected = str(item["answer"])
            questions.append(
                {
                    "id": str(idx),
                    "correct": grade_mc_letter(expected, predicted),
                    "expected": expected,
                    "predicted": predicted,
                    "question": prompt,
                    "raw_response": text[:4000],
                    "category": item["subject"],
                    "time_s": round(time.time() - t0, 3),
                }
            )
    finally:
        SettingsService.update(
            UpdateRuntimeSettingsRequest(provider=orig[0], model=orig[1])
        )

    result = build_result(
        run_id=run_id,
        model_id=model_id or orig[1],
        benchmark="mmlu",
        questions=questions,
        time_s=time.time() - start,
        thinking_used=thinking,
    )
    save_result(result)
    return result
